// Package gateway — api.go implements the HTTP REST API served on the API port (18790).
//
// Ported from mypalclara/gateway/api/.
package gateway

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/google/uuid"
	"github.com/rs/zerolog"
)

// API serves HTTP REST endpoints on the API port (default 18790).
type API struct {
	server    *Server
	processor Processor
	mux       *http.ServeMux
	httpSrv   *http.Server
	logger    zerolog.Logger
	startedAt time.Time
}

// NewAPI creates a new HTTP API server.
func NewAPI(host string, port int, server *Server, processor Processor) *API {
	a := &API{
		server:    server,
		processor: processor,
		mux:       http.NewServeMux(),
		logger:    zerolog.Nop(),
		startedAt: time.Now(),
	}

	a.registerRoutes()

	a.httpSrv = &http.Server{
		Addr:    fmt.Sprintf("%s:%d", host, port),
		Handler: a.mux,
	}

	return a
}

// SetLogger sets the logger for the API.
func (a *API) SetLogger(logger zerolog.Logger) {
	a.logger = logger
}

// Start begins serving HTTP requests. It blocks until the server is stopped.
func (a *API) Start() error {
	a.logger.Info().Str("addr", a.httpSrv.Addr).Msg("HTTP API starting")
	if err := a.httpSrv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		return err
	}
	return nil
}

// Stop gracefully shuts down the HTTP API server.
func (a *API) Stop(ctx context.Context) error {
	a.logger.Info().Msg("HTTP API stopping")
	return a.httpSrv.Shutdown(ctx)
}

// registerRoutes sets up HTTP endpoint handlers.
func (a *API) registerRoutes() {
	a.mux.HandleFunc("GET /v1/health", a.handleHealth)
	a.mux.HandleFunc("GET /v1/status", a.handleStatus)
	a.mux.HandleFunc("POST /v1/messages", a.handleMessages)
}

// --- Handlers ---

// handleHealth returns a simple health check response.
func (a *API) handleHealth(w http.ResponseWriter, _ *http.Request) {
	respondJSON(w, http.StatusOK, map[string]any{
		"status": "ok",
		"time":   time.Now().UTC().Format(time.RFC3339),
	})
}

// handleStatus returns server status information.
func (a *API) handleStatus(w http.ResponseWriter, _ *http.Request) {
	nodes := a.server.Nodes().List()
	nodeInfos := make([]map[string]any, 0, len(nodes))
	for _, n := range nodes {
		nodeInfos = append(nodeInfos, map[string]any{
			"node_id":      n.Info.NodeID,
			"platform":     n.Info.Platform,
			"connected_at": n.Info.ConnectedAt.UTC().Format(time.RFC3339),
			"last_ping":    n.LastPing.UTC().Format(time.RFC3339),
		})
	}

	uptime := time.Since(a.startedAt).Seconds()

	respondJSON(w, http.StatusOK, map[string]any{
		"status":         "running",
		"uptime_seconds": int(uptime),
		"nodes":          nodeInfos,
		"node_count":     len(nodes),
	})
}

// apiMessageRequest is the JSON body for POST /v1/messages.
type apiMessageRequest struct {
	UserID    string `json:"user_id"`
	Content   string `json:"content"`
	ChannelID string `json:"channel_id,omitempty"`
	ProjectID string `json:"project_id,omitempty"`
	Tier      string `json:"tier,omitempty"`
}

// handleMessages processes a synchronous message request.
func (a *API) handleMessages(w http.ResponseWriter, r *http.Request) {
	var body apiMessageRequest
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		respondJSON(w, http.StatusBadRequest, map[string]any{
			"error": "invalid JSON body",
		})
		return
	}

	if body.Content == "" {
		respondJSON(w, http.StatusBadRequest, map[string]any{
			"error": "content is required",
		})
		return
	}
	if body.UserID == "" {
		body.UserID = "api-user"
	}
	if body.ChannelID == "" {
		body.ChannelID = "api"
	}

	if a.processor == nil {
		respondJSON(w, http.StatusServiceUnavailable, map[string]any{
			"error": "no message processor configured",
		})
		return
	}

	// Build a MessageRequest from the API body.
	req := &MessageRequest{
		Type: MsgTypeMessage,
		ID:   uuid.New().String(),
		User: UserInfo{
			ID:   body.UserID,
			Name: body.UserID,
		},
		Channel: ChannelInfo{
			ID:   body.ChannelID,
			Type: "api",
		},
		Content:      body.Content,
		TierOverride: body.Tier,
	}

	// Collect the final response text from events.
	var responseText string
	var toolCount int

	send := func(msg any) error {
		// Inspect for ResponseEnd to capture the full text.
		data, merr := json.Marshal(msg)
		if merr != nil {
			return merr
		}
		var envelope struct {
			Type    string          `json:"type"`
			Payload json.RawMessage `json:"payload"`
		}
		if err := json.Unmarshal(data, &envelope); err == nil {
			if envelope.Type == MsgTypeResponseEnd {
				var end ResponseEnd
				if err := json.Unmarshal(envelope.Payload, &end); err == nil {
					responseText = end.FullText
					toolCount = end.ToolCount
				}
			}
		}
		return nil
	}

	if err := a.processor.Process(r.Context(), req, send); err != nil {
		a.logger.Error().Err(err).Str("request_id", req.ID).Msg("message processing failed")
		respondJSON(w, http.StatusInternalServerError, map[string]any{
			"error":      "processing failed",
			"request_id": req.ID,
		})
		return
	}

	respondJSON(w, http.StatusOK, map[string]any{
		"request_id": req.ID,
		"response":   responseText,
		"tool_count": toolCount,
	})
}

// --- Helpers ---

// respondJSON marshals v as JSON and writes it with the given status code.
func respondJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(v) //nolint:errcheck
}
