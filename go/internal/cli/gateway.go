package cli

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/coder/websocket"
	"github.com/google/uuid"
	"github.com/rs/zerolog/log"

	gateway "github.com/BangRocket/mypalclara/go/internal/gateway"
)

// GatewayClient manages a WebSocket connection to the Clara gateway.
type GatewayClient struct {
	url    string
	conn   *websocket.Conn
	nodeID string
	mu     sync.Mutex
}

// NewGatewayClient creates a client that will connect to the given gateway URL.
func NewGatewayClient(url string) *GatewayClient {
	return &GatewayClient{
		url:    url,
		nodeID: "cli-" + uuid.New().String()[:8],
	}
}

// Connect dials the gateway WebSocket and performs the registration handshake.
func (c *GatewayClient) Connect(ctx context.Context) error {
	conn, _, err := websocket.Dial(ctx, c.url, nil)
	if err != nil {
		return fmt.Errorf("dial %s: %w", c.url, err)
	}
	// Set a large read limit for streaming responses.
	conn.SetReadLimit(4 * 1024 * 1024)

	c.mu.Lock()
	c.conn = conn
	c.mu.Unlock()

	// Send register message.
	reg := gateway.RegisterMessage{
		Type:         gateway.MsgTypeRegister,
		NodeID:       c.nodeID,
		Platform:     "cli",
		Capabilities: []string{"streaming", "markdown"},
	}
	if err := c.Send(gateway.MsgTypeRegister, reg); err != nil {
		conn.Close(websocket.StatusInternalError, "register failed")
		return fmt.Errorf("send register: %w", err)
	}

	// Wait for registered confirmation (5s timeout).
	regCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()

	_, data, err := conn.Read(regCtx)
	if err != nil {
		conn.Close(websocket.StatusProtocolError, "no registration response")
		return fmt.Errorf("read register response: %w", err)
	}

	msg, err := gateway.ParseMessage(data)
	if err != nil {
		conn.Close(websocket.StatusProtocolError, "invalid response")
		return fmt.Errorf("parse register response: %w", err)
	}

	if msg.Type == gateway.MsgTypeError {
		if errMsg, ok := msg.Payload.(gateway.ErrorMessage); ok {
			conn.Close(websocket.StatusPolicyViolation, "rejected")
			return fmt.Errorf("gateway rejected registration: %s", errMsg.Message)
		}
	}

	if msg.Type != gateway.MsgTypeRegistered {
		conn.Close(websocket.StatusProtocolError, "unexpected response")
		return fmt.Errorf("expected registered, got %s", msg.Type)
	}

	log.Debug().Str("node_id", c.nodeID).Msg("registered with gateway")
	return nil
}

// Send marshals and sends a typed message through the WebSocket.
func (c *GatewayClient) Send(msgType string, payload any) error {
	c.mu.Lock()
	conn := c.conn
	c.mu.Unlock()

	if conn == nil {
		return fmt.Errorf("not connected")
	}

	data, err := gateway.MarshalMessage(msgType, payload)
	if err != nil {
		return fmt.Errorf("marshal: %w", err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	return conn.Write(ctx, websocket.MessageText, data)
}

// SendMessage sends a user chat message to the gateway and returns the
// request ID used for correlation.
func (c *GatewayClient) SendMessage(content, userID string) (string, error) {
	reqID := uuid.New().String()
	req := gateway.MessageRequest{
		Type: gateway.MsgTypeMessage,
		ID:   reqID,
		User: gateway.UserInfo{
			ID:         "cli-" + userID,
			PlatformID: userID,
			Name:       userID,
		},
		Channel: gateway.ChannelInfo{
			ID:   "cli-dm",
			Type: "dm",
			Name: "CLI",
		},
		Content: content,
	}
	if err := c.Send(gateway.MsgTypeMessage, req); err != nil {
		return "", err
	}
	return reqID, nil
}

// CancelRequest sends a cancel message for an in-flight request.
func (c *GatewayClient) CancelRequest(requestID string) error {
	return c.Send(gateway.MsgTypeCancel, gateway.CancelMessage{
		Type:      gateway.MsgTypeCancel,
		RequestID: requestID,
	})
}

// ReadMessages returns a channel that emits parsed gateway messages. The
// channel is closed when the connection drops or the context is cancelled.
func (c *GatewayClient) ReadMessages(ctx context.Context) <-chan *gateway.GatewayMessage {
	ch := make(chan *gateway.GatewayMessage, 64)

	go func() {
		defer close(ch)

		c.mu.Lock()
		conn := c.conn
		c.mu.Unlock()

		if conn == nil {
			return
		}

		for {
			_, data, err := conn.Read(ctx)
			if err != nil {
				if ctx.Err() != nil {
					return
				}
				log.Debug().Err(err).Msg("gateway read error")
				return
			}

			msg, err := gateway.ParseMessage(data)
			if err != nil {
				log.Debug().Err(err).Msg("failed to parse gateway message")
				continue
			}

			// Handle pings internally.
			if msg.Type == gateway.MsgTypePing {
				pongData, _ := json.Marshal(gateway.GatewayMessage{
					Type: gateway.MsgTypePong,
					Payload: gateway.PongMessage{
						Type:      gateway.MsgTypePong,
						Timestamp: time.Now(),
					},
				})
				_ = conn.Write(ctx, websocket.MessageText, pongData)
				continue
			}

			select {
			case ch <- msg:
			case <-ctx.Done():
				return
			}
		}
	}()

	return ch
}

// Close gracefully closes the WebSocket connection.
func (c *GatewayClient) Close() error {
	c.mu.Lock()
	conn := c.conn
	c.conn = nil
	c.mu.Unlock()

	if conn == nil {
		return nil
	}
	return conn.Close(websocket.StatusNormalClosure, "bye")
}

// NodeID returns the client's registered node ID.
func (c *GatewayClient) NodeID() string {
	return c.nodeID
}
