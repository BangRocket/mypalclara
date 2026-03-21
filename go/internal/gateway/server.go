package gateway

import (
	"context"
	"encoding/json"
	"fmt"
	"net"
	"net/http"
	"sync"
	"time"

	"github.com/coder/websocket"
	"github.com/google/uuid"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
)

// Processor handles incoming message requests from adapters.
type Processor interface {
	Process(ctx context.Context, req *MessageRequest, send func(msg any) error) error
}

// Server is the WebSocket gateway that accepts adapter connections and routes
// messages between adapters and the message processor.
type Server struct {
	host       string
	port       int
	secret     string
	nodes      *NodeRegistry
	processor  Processor
	httpServer *http.Server
	mu         sync.RWMutex

	// activeRequests tracks cancel functions keyed by request ID so that
	// incoming cancel messages can abort in-flight processing.
	activeRequests map[string]context.CancelFunc
	arMu           sync.Mutex
}

// NewServer creates a new gateway server.
func NewServer(host string, port int, secret string) *Server {
	return &Server{
		host:           host,
		port:           port,
		secret:         secret,
		nodes:          NewNodeRegistry(),
		activeRequests: make(map[string]context.CancelFunc),
	}
}

// SetProcessor sets the message processor for handling incoming messages.
func (s *Server) SetProcessor(p Processor) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.processor = p
}

// Nodes returns the node registry for inspection.
func (s *Server) Nodes() *NodeRegistry {
	return s.nodes
}

// Start begins accepting WebSocket connections. It blocks until the context is
// cancelled or the server encounters a fatal error.
func (s *Server) Start(ctx context.Context) error {
	mux := http.NewServeMux()
	mux.HandleFunc("/ws", func(w http.ResponseWriter, r *http.Request) {
		s.handleUpgrade(ctx, w, r)
	})
	// Health check endpoint.
	mux.HandleFunc("/health", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		fmt.Fprintf(w, `{"status":"ok","nodes":%d}`, s.nodes.Count())
	})

	addr := fmt.Sprintf("%s:%d", s.host, s.port)
	s.httpServer = &http.Server{
		Addr:    addr,
		Handler: mux,
		BaseContext: func(_ net.Listener) context.Context {
			return ctx
		},
	}

	log.Info().Str("addr", addr).Msg("gateway server starting")

	errCh := make(chan error, 1)
	go func() {
		if err := s.httpServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			errCh <- err
		}
		close(errCh)
	}()

	select {
	case <-ctx.Done():
		return s.Stop(context.Background())
	case err := <-errCh:
		return err
	}
}

// Stop gracefully shuts down the server.
func (s *Server) Stop(ctx context.Context) error {
	log.Info().Msg("gateway server stopping")

	// Close all connected nodes.
	for _, node := range s.nodes.List() {
		node.Conn.Close(websocket.StatusGoingAway, "server shutting down")
		s.nodes.Unregister(node.Info.NodeID)
	}

	if s.httpServer != nil {
		return s.httpServer.Shutdown(ctx)
	}
	return nil
}

// handleUpgrade upgrades an HTTP request to a WebSocket connection.
func (s *Server) handleUpgrade(ctx context.Context, w http.ResponseWriter, r *http.Request) {
	conn, err := websocket.Accept(w, r, &websocket.AcceptOptions{
		// Allow all origins in development; tighten for production.
		InsecureSkipVerify: true,
	})
	if err != nil {
		log.Error().Err(err).Msg("websocket accept failed")
		return
	}

	s.handleConnection(ctx, conn)
}

// handleConnection manages a single WebSocket connection lifecycle:
// 1. Wait for register message
// 2. Verify secret if required
// 3. Send registered confirmation
// 4. Read loop: dispatch messages by type
// 5. On disconnect: unregister
func (s *Server) handleConnection(ctx context.Context, conn *websocket.Conn) {
	connLog := log.With().Str("remote", "ws-client").Logger()

	// --- Step 1: Wait for registration (5 second timeout) ---
	regCtx, regCancel := context.WithTimeout(ctx, 5*time.Second)
	defer regCancel()

	_, data, err := conn.Read(regCtx)
	if err != nil {
		connLog.Error().Err(err).Msg("failed to read register message")
		conn.Close(websocket.StatusProtocolError, "expected register message")
		return
	}

	msg, err := ParseMessage(data)
	if err != nil {
		connLog.Error().Err(err).Msg("failed to parse register message")
		conn.Close(websocket.StatusProtocolError, "invalid message format")
		return
	}

	if msg.Type != MsgTypeRegister {
		connLog.Error().Str("type", msg.Type).Msg("first message must be register")
		conn.Close(websocket.StatusProtocolError, "expected register message")
		return
	}

	reg, ok := msg.Payload.(RegisterMessage)
	if !ok {
		connLog.Error().Msg("invalid register payload")
		conn.Close(websocket.StatusProtocolError, "invalid register payload")
		return
	}

	// --- Step 2: Verify secret ---
	if s.secret != "" {
		secret, _ := reg.Metadata["secret"].(string)
		if secret != s.secret {
			connLog.Warn().Str("node_id", reg.NodeID).Msg("authentication failed")
			sendJSON(ctx, conn, MsgTypeError, ErrorMessage{
				Code:        "auth_failed",
				Message:     "invalid or missing secret",
				Recoverable: false,
			})
			conn.Close(websocket.StatusPolicyViolation, "authentication failed")
			return
		}
	}

	// --- Step 3: Build send function and register node ---
	connLog = connLog.With().
		Str("node_id", reg.NodeID).
		Str("platform", reg.Platform).
		Logger()

	sendFn := func(msg any) error {
		return writeJSON(ctx, conn, msg)
	}

	node := &ConnectedNode{
		Info: NodeInfo{
			NodeID:       reg.NodeID,
			Platform:     reg.Platform,
			Capabilities: reg.Capabilities,
			ConnectedAt:  time.Now(),
			Metadata:     reg.Metadata,
		},
		Conn:         conn,
		RegisteredAt: time.Now(),
		LastPing:     time.Now(),
		Send:         sendFn,
	}

	if err := s.nodes.Register(node); err != nil {
		connLog.Error().Err(err).Msg("registration failed")
		sendJSON(ctx, conn, MsgTypeError, ErrorMessage{
			Code:        "registration_failed",
			Message:     err.Error(),
			Recoverable: false,
		})
		conn.Close(websocket.StatusPolicyViolation, "registration failed")
		return
	}

	// --- Step 4: Send registered confirmation ---
	sendJSON(ctx, conn, MsgTypeRegistered, RegisteredMessage{
		Type:      MsgTypeRegistered,
		NodeID:    reg.NodeID,
		SessionID: uuid.New().String(),
		ServerTime: time.Now(),
	})

	connLog.Info().Strs("capabilities", reg.Capabilities).Msg("node registered")

	// --- Step 5: Read loop ---
	defer func() {
		s.nodes.Unregister(reg.NodeID)
		conn.Close(websocket.StatusNormalClosure, "disconnected")
		connLog.Info().Msg("node disconnected")
	}()

	for {
		_, data, err := conn.Read(ctx)
		if err != nil {
			// Normal closure or context cancellation are not errors.
			if websocket.CloseStatus(err) == websocket.StatusNormalClosure ||
				ctx.Err() != nil {
				return
			}
			connLog.Debug().Err(err).Msg("read error")
			return
		}

		inMsg, err := ParseMessage(data)
		if err != nil {
			connLog.Warn().Err(err).Msg("failed to parse message")
			continue
		}

		s.handleMessage(ctx, &node.Info, inMsg, sendFn, connLog)
	}
}

// handleMessage processes a single incoming message by type.
func (s *Server) handleMessage(
	ctx context.Context,
	node *NodeInfo,
	msg *GatewayMessage,
	send func(any) error,
	logger zerolog.Logger,
) {
	switch msg.Type {
	case MsgTypePing:
		s.nodes.UpdatePing(node.NodeID)
		pongData, err := MarshalMessage(MsgTypePong, PongMessage{
			Type:      MsgTypePong,
			Timestamp: time.Now(),
		})
		if err == nil {
			_ = send(json.RawMessage(pongData))
		}

	case MsgTypeMessage:
		req, ok := msg.Payload.(MessageRequest)
		if !ok {
			logger.Warn().Msg("invalid message payload")
			return
		}

		s.mu.RLock()
		proc := s.processor
		s.mu.RUnlock()

		if proc == nil {
			logger.Warn().Str("request_id", req.ID).Msg("no processor configured")
			_ = send(errorEnvelope(req.ID, "no_processor", "no message processor configured", true))
			return
		}

		// Create cancellable context for this request.
		reqCtx, cancel := context.WithCancel(ctx)

		s.arMu.Lock()
		s.activeRequests[req.ID] = cancel
		s.arMu.Unlock()

		// Process asynchronously so the read loop continues.
		go func() {
			defer func() {
				cancel()
				s.arMu.Lock()
				delete(s.activeRequests, req.ID)
				s.arMu.Unlock()
			}()

			wrappedSend := func(msg any) error {
				data, err := json.Marshal(msg)
				if err != nil {
					return err
				}
				return send(json.RawMessage(data))
			}

			if err := proc.Process(reqCtx, &req, wrappedSend); err != nil {
				logger.Error().Err(err).Str("request_id", req.ID).Msg("processing failed")
				_ = send(errorEnvelope(req.ID, "processing_error", err.Error(), true))
			}
		}()

	case MsgTypeCancel:
		cancel, ok := msg.Payload.(CancelMessage)
		if !ok {
			logger.Warn().Msg("invalid cancel payload")
			return
		}

		s.arMu.Lock()
		cancelFn, exists := s.activeRequests[cancel.RequestID]
		s.arMu.Unlock()

		if exists {
			cancelFn()
			logger.Info().Str("request_id", cancel.RequestID).Msg("request cancelled")
			_ = send(cancelledEnvelope(cancel.RequestID))
		}

	default:
		logger.Debug().Str("type", msg.Type).Msg("unhandled message type")
	}
}

// --- helpers ---

// sendJSON marshals a payload into a GatewayMessage envelope and writes it to
// the WebSocket connection. If conn is nil, it's a no-op (use send func instead).
func sendJSON(ctx context.Context, conn *websocket.Conn, msgType string, payload any) {
	if conn == nil {
		return
	}
	data, err := MarshalMessage(msgType, payload)
	if err != nil {
		log.Error().Err(err).Str("type", msgType).Msg("failed to marshal message")
		return
	}
	if err := conn.Write(ctx, websocket.MessageText, data); err != nil {
		log.Debug().Err(err).Str("type", msgType).Msg("failed to write message")
	}
}

// writeJSON marshals any value and writes it as a text WebSocket message.
func writeJSON(ctx context.Context, conn *websocket.Conn, msg any) error {
	data, err := json.Marshal(msg)
	if err != nil {
		return fmt.Errorf("marshal: %w", err)
	}
	return conn.Write(ctx, websocket.MessageText, data)
}

// errorEnvelope creates a marshaled error GatewayMessage.
func errorEnvelope(requestID, code, message string, recoverable bool) json.RawMessage {
	data, _ := MarshalMessage(MsgTypeError, ErrorMessage{
		Type:        MsgTypeError,
		RequestID:   requestID,
		Code:        code,
		Message:     message,
		Recoverable: recoverable,
	})
	return data
}

// cancelledEnvelope creates a marshaled cancelled GatewayMessage.
func cancelledEnvelope(requestID string) json.RawMessage {
	data, _ := MarshalMessage(MsgTypeCancelled, CancelledMessage{
		Type:      MsgTypeCancelled,
		RequestID: requestID,
	})
	return data
}
