// Package gateway defines WebSocket protocol message types for the Clara Gateway.
//
// All messages are JSON-serializable for WebSocket transport. The protocol uses
// a flat message format where the "type" field is embedded directly in each message,
// matching the Python gateway protocol.
package gateway

import (
	"encoding/json"
	"fmt"
	"time"
)

// MessageType constants for the gateway protocol.
const (
	// Registration
	MsgTypeRegister   = "register"
	MsgTypeRegistered = "registered"
	MsgTypeUnregister = "unregister"

	// Heartbeat
	MsgTypePing = "ping"
	MsgTypePong = "pong"

	// Message flow
	MsgTypeMessage       = "message"
	MsgTypeResponseStart = "response_start"
	MsgTypeResponseChunk = "response_chunk"
	MsgTypeResponseEnd   = "response_end"

	// Tool execution
	MsgTypeToolStart  = "tool_start"
	MsgTypeToolResult = "tool_result"

	// Control
	MsgTypeCancel    = "cancel"
	MsgTypeCancelled = "cancelled"
	MsgTypeError     = "error"
	MsgTypeStatus    = "status"

	// Proactive (ORS)
	MsgTypeProactiveMessage = "proactive_message"

	// MCP Management
	MsgTypeMCPList              = "mcp_list"
	MsgTypeMCPListResponse      = "mcp_list_response"
	MsgTypeMCPInstall           = "mcp_install"
	MsgTypeMCPInstallResponse   = "mcp_install_response"
	MsgTypeMCPUninstall         = "mcp_uninstall"
	MsgTypeMCPUninstallResponse = "mcp_uninstall_response"
	MsgTypeMCPStatus            = "mcp_status"
	MsgTypeMCPStatusResponse    = "mcp_status_response"
	MsgTypeMCPRestart           = "mcp_restart"
	MsgTypeMCPRestartResponse   = "mcp_restart_response"
	MsgTypeMCPEnable            = "mcp_enable"
	MsgTypeMCPEnableResponse    = "mcp_enable_response"
)

// UserInfo identifies the message sender.
type UserInfo struct {
	ID          string `json:"id"`                        // Platform-prefixed user ID (e.g., discord-123)
	PlatformID  string `json:"platform_id"`               // Original platform user ID
	Name        string `json:"name,omitempty"`             // Username
	DisplayName string `json:"display_name,omitempty"`     // Display name
}

// ChannelInfo identifies the message channel.
type ChannelInfo struct {
	ID        string `json:"id"`                    // Channel ID
	Type      string `json:"type"`                  // "dm", "server", "group"
	Name      string `json:"name,omitempty"`        // Channel name
	GuildID   string `json:"guild_id,omitempty"`    // Server/guild ID if applicable
	GuildName string `json:"guild_name,omitempty"`  // Server/guild name if applicable
}

// AttachmentInfo for file/image attachments.
type AttachmentInfo struct {
	Type       string `json:"type"`                   // "image", "file", "text"
	Filename   string `json:"filename"`               // Original filename
	MediaType  string `json:"media_type,omitempty"`   // MIME type
	Base64Data string `json:"base64_data,omitempty"`  // Base64-encoded content
	Content    string `json:"content,omitempty"`      // Text content (for text files)
	Size       *int   `json:"size,omitempty"`         // File size in bytes
}

// NodeInfo contains information about a connected adapter node.
type NodeInfo struct {
	NodeID       string         `json:"node_id"`                // Unique node identifier
	Platform     string         `json:"platform"`               // Platform name (discord, cli, slack, etc.)
	Capabilities []string       `json:"capabilities,omitempty"` // Supported features
	ConnectedAt  time.Time      `json:"connected_at"`           // When the node connected
	Metadata     map[string]any `json:"metadata,omitempty"`     // Additional info
}

// ButtonInfo describes an interactive button component.
type ButtonInfo struct {
	Label    string `json:"label"`              // Button display text
	Style    string `json:"style,omitempty"`    // "primary", "secondary", "success", "danger"
	Action   string `json:"action,omitempty"`   // "dismiss" or "confirm"
	Disabled bool   `json:"disabled,omitempty"` // Whether button is disabled
}

// FileData represents file content for sending as attachment over WebSocket.
type FileData struct {
	Filename      string `json:"filename"`                         // Original filename
	ContentBase64 string `json:"content_base64"`                   // Base64-encoded file content
	MediaType     string `json:"media_type,omitempty"`             // MIME type
}

// --------------------------------------------------------------------------
// Registration Messages
// --------------------------------------------------------------------------

// RegisterMessage is sent from adapter to gateway to register a new adapter node.
type RegisterMessage struct {
	Type         string         `json:"type"`
	NodeID       string         `json:"node_id"`
	Platform     string         `json:"platform"`
	Capabilities []string       `json:"capabilities,omitempty"`
	Metadata     map[string]any `json:"metadata,omitempty"`
}

// RegisteredMessage is sent from gateway to adapter to confirm registration.
type RegisteredMessage struct {
	Type       string    `json:"type"`
	NodeID     string    `json:"node_id"`
	SessionID  string    `json:"session_id"`
	ServerTime time.Time `json:"server_time"`
}

// --------------------------------------------------------------------------
// Heartbeat Messages
// --------------------------------------------------------------------------

// PingMessage is a bidirectional heartbeat ping.
type PingMessage struct {
	Type      string    `json:"type"`
	Timestamp time.Time `json:"timestamp"`
}

// PongMessage is a bidirectional heartbeat pong.
type PongMessage struct {
	Type      string    `json:"type"`
	Timestamp time.Time `json:"timestamp"`
}

// --------------------------------------------------------------------------
// Message Request/Response
// --------------------------------------------------------------------------

// MessageRequest is sent from adapter to gateway to process a user message.
type MessageRequest struct {
	Type         string           `json:"type"`
	ID           string           `json:"id"`
	User         UserInfo         `json:"user"`
	Channel      ChannelInfo      `json:"channel"`
	Content      string           `json:"content"`
	Attachments  []AttachmentInfo `json:"attachments,omitempty"`
	ReplyChain   []map[string]any `json:"reply_chain,omitempty"`
	TierOverride string           `json:"tier_override,omitempty"`
	Metadata     map[string]any   `json:"metadata,omitempty"`
}

// ResponseStart is sent when response generation begins.
type ResponseStart struct {
	Type      string `json:"type"`
	ID        string `json:"id"`
	RequestID string `json:"request_id"`
	ModelTier string `json:"model_tier,omitempty"`
}

// ResponseChunk carries a streaming response chunk.
type ResponseChunk struct {
	Type        string `json:"type"`
	ID          string `json:"id"`
	RequestID   string `json:"request_id"`
	Chunk       string `json:"chunk"`
	Accumulated string `json:"accumulated,omitempty"`
}

// ResponseEnd is sent when response generation completes.
type ResponseEnd struct {
	Type       string       `json:"type"`
	ID         string       `json:"id"`
	RequestID  string       `json:"request_id"`
	FullText   string       `json:"full_text"`
	Files      []string     `json:"files,omitempty"`
	FileData   []FileData   `json:"file_data,omitempty"`
	ToolCount  int          `json:"tool_count,omitempty"`
	TokensUsed *int         `json:"tokens_used,omitempty"`
	EditTarget string       `json:"edit_target,omitempty"`
	Components []ButtonInfo `json:"components,omitempty"`
}

// --------------------------------------------------------------------------
// Tool Execution Messages
// --------------------------------------------------------------------------

// ToolStart is sent when tool execution begins.
type ToolStart struct {
	Type        string         `json:"type"`
	ID          string         `json:"id"`
	RequestID   string         `json:"request_id"`
	ToolName    string         `json:"tool_name"`
	Step        int            `json:"step"`
	Description string         `json:"description,omitempty"`
	Arguments   map[string]any `json:"arguments,omitempty"`
	Emoji       string         `json:"emoji,omitempty"`
}

// ToolResult is sent when tool execution completes.
type ToolResult struct {
	Type          string `json:"type"`
	ID            string `json:"id"`
	RequestID     string `json:"request_id"`
	ToolName      string `json:"tool_name"`
	Success       bool   `json:"success"`
	OutputPreview string `json:"output_preview,omitempty"`
	DurationMs    *int   `json:"duration_ms,omitempty"`
}

// --------------------------------------------------------------------------
// Control Messages
// --------------------------------------------------------------------------

// CancelMessage is sent from adapter to gateway to cancel an in-flight request.
type CancelMessage struct {
	Type      string `json:"type"`
	RequestID string `json:"request_id"`
	Reason    string `json:"reason,omitempty"`
}

// CancelledMessage is sent from gateway to adapter confirming cancellation.
type CancelledMessage struct {
	Type      string `json:"type"`
	RequestID string `json:"request_id"`
}

// ErrorMessage is sent from gateway to adapter when an error occurs.
type ErrorMessage struct {
	Type        string `json:"type"`
	RequestID   string `json:"request_id,omitempty"`
	Code        string `json:"code"`
	Message     string `json:"message"`
	Recoverable bool   `json:"recoverable"`
}

// StatusMessage carries bidirectional status information.
type StatusMessage struct {
	Type           string `json:"type"`
	NodeID         string `json:"node_id,omitempty"`
	ActiveRequests int    `json:"active_requests,omitempty"`
	QueueLength    int    `json:"queue_length,omitempty"`
	UptimeSeconds  *int   `json:"uptime_seconds,omitempty"`
}

// --------------------------------------------------------------------------
// Proactive Messages (ORS)
// --------------------------------------------------------------------------

// ProactiveMessage is sent from gateway to adapter for proactive outreach.
type ProactiveMessage struct {
	Type     string      `json:"type"`
	User     UserInfo    `json:"user"`
	Channel  ChannelInfo `json:"channel"`
	Content  string      `json:"content"`
	Priority string      `json:"priority,omitempty"`
}

// --------------------------------------------------------------------------
// MCP Management Messages
// --------------------------------------------------------------------------

// MCPServerInfo describes a registered MCP server.
type MCPServerInfo struct {
	Name       string   `json:"name"`
	Status     string   `json:"status"`       // "running", "stopped", "error"
	Enabled    bool     `json:"enabled"`
	Connected  bool     `json:"connected"`
	ToolCount  int      `json:"tool_count,omitempty"`
	SourceType string   `json:"source_type,omitempty"` // "npm", "smithery", "github", etc.
	Transport  string   `json:"transport,omitempty"`   // "stdio", "http"
	Tools      []string `json:"tools,omitempty"`
	LastError  string   `json:"last_error,omitempty"`
}

// MCPListRequest requests a list of all MCP servers.
type MCPListRequest struct {
	Type      string `json:"type"`
	RequestID string `json:"request_id"`
}

// MCPListResponse returns the list of MCP servers.
type MCPListResponse struct {
	Type      string          `json:"type"`
	RequestID string          `json:"request_id"`
	Success   bool            `json:"success"`
	Servers   []MCPServerInfo `json:"servers,omitempty"`
	Error     string          `json:"error,omitempty"`
}

// MCPInstallRequest asks to install an MCP server.
type MCPInstallRequest struct {
	Type        string `json:"type"`
	RequestID   string `json:"request_id"`
	Source      string `json:"source"`
	Name        string `json:"name,omitempty"`
	RequestedBy string `json:"requested_by,omitempty"`
}

// MCPInstallResponse returns the installation result.
type MCPInstallResponse struct {
	Type            string `json:"type"`
	RequestID       string `json:"request_id"`
	Success         bool   `json:"success"`
	ServerName      string `json:"server_name,omitempty"`
	ToolsDiscovered int    `json:"tools_discovered,omitempty"`
	Error           string `json:"error,omitempty"`
}

// MCPUninstallRequest asks to uninstall an MCP server.
type MCPUninstallRequest struct {
	Type       string `json:"type"`
	RequestID  string `json:"request_id"`
	ServerName string `json:"server_name"`
}

// MCPUninstallResponse returns the uninstall result.
type MCPUninstallResponse struct {
	Type      string `json:"type"`
	RequestID string `json:"request_id"`
	Success   bool   `json:"success"`
	Error     string `json:"error,omitempty"`
}

// MCPStatusRequest asks for MCP server status.
type MCPStatusRequest struct {
	Type       string `json:"type"`
	RequestID  string `json:"request_id"`
	ServerName string `json:"server_name,omitempty"`
}

// MCPStatusResponse returns MCP server status.
type MCPStatusResponse struct {
	Type             string         `json:"type"`
	RequestID        string         `json:"request_id"`
	Success          bool           `json:"success"`
	Server           *MCPServerInfo `json:"server,omitempty"`
	TotalServers     int            `json:"total_servers,omitempty"`
	ConnectedServers int            `json:"connected_servers,omitempty"`
	EnabledServers   int            `json:"enabled_servers,omitempty"`
	Error            string         `json:"error,omitempty"`
}

// MCPRestartRequest asks to restart an MCP server.
type MCPRestartRequest struct {
	Type       string `json:"type"`
	RequestID  string `json:"request_id"`
	ServerName string `json:"server_name"`
}

// MCPRestartResponse returns the restart result.
type MCPRestartResponse struct {
	Type      string `json:"type"`
	RequestID string `json:"request_id"`
	Success   bool   `json:"success"`
	Error     string `json:"error,omitempty"`
}

// MCPEnableRequest asks to enable or disable an MCP server.
type MCPEnableRequest struct {
	Type       string `json:"type"`
	RequestID  string `json:"request_id"`
	ServerName string `json:"server_name"`
	Enabled    bool   `json:"enabled"`
}

// MCPEnableResponse returns the enable/disable result.
type MCPEnableResponse struct {
	Type      string `json:"type"`
	RequestID string `json:"request_id"`
	Success   bool   `json:"success"`
	Enabled   bool   `json:"enabled"`
	Error     string `json:"error,omitempty"`
}

// --------------------------------------------------------------------------
// GatewayMessage envelope and helpers
// --------------------------------------------------------------------------

// GatewayMessage is the envelope for all WebSocket messages.
// It wraps a typed payload for JSON serialization.
type GatewayMessage struct {
	Type    string `json:"type"`
	Payload any    `json:"payload"`
}

// ParseMessage deserializes a JSON byte slice into a GatewayMessage.
// The Payload is left as json.RawMessage for type-specific decoding.
func ParseMessage(data []byte) (*GatewayMessage, error) {
	var raw struct {
		Type    string          `json:"type"`
		Payload json.RawMessage `json:"payload"`
	}
	if err := json.Unmarshal(data, &raw); err != nil {
		return nil, fmt.Errorf("invalid JSON: %w", err)
	}
	if raw.Type == "" {
		return nil, fmt.Errorf("message missing 'type' field")
	}

	msg := &GatewayMessage{Type: raw.Type}

	// If there's no payload, return with nil payload.
	if len(raw.Payload) == 0 || string(raw.Payload) == "null" {
		return msg, nil
	}

	// Unmarshal payload into the appropriate typed struct.
	var payload any
	var err error

	switch raw.Type {
	case MsgTypeRegister:
		var p RegisterMessage
		err = json.Unmarshal(raw.Payload, &p)
		payload = p
	case MsgTypeRegistered:
		var p RegisteredMessage
		err = json.Unmarshal(raw.Payload, &p)
		payload = p
	case MsgTypePing:
		var p PingMessage
		err = json.Unmarshal(raw.Payload, &p)
		payload = p
	case MsgTypePong:
		var p PongMessage
		err = json.Unmarshal(raw.Payload, &p)
		payload = p
	case MsgTypeMessage:
		var p MessageRequest
		err = json.Unmarshal(raw.Payload, &p)
		payload = p
	case MsgTypeResponseStart:
		var p ResponseStart
		err = json.Unmarshal(raw.Payload, &p)
		payload = p
	case MsgTypeResponseChunk:
		var p ResponseChunk
		err = json.Unmarshal(raw.Payload, &p)
		payload = p
	case MsgTypeResponseEnd:
		var p ResponseEnd
		err = json.Unmarshal(raw.Payload, &p)
		payload = p
	case MsgTypeToolStart:
		var p ToolStart
		err = json.Unmarshal(raw.Payload, &p)
		payload = p
	case MsgTypeToolResult:
		var p ToolResult
		err = json.Unmarshal(raw.Payload, &p)
		payload = p
	case MsgTypeCancel:
		var p CancelMessage
		err = json.Unmarshal(raw.Payload, &p)
		payload = p
	case MsgTypeCancelled:
		var p CancelledMessage
		err = json.Unmarshal(raw.Payload, &p)
		payload = p
	case MsgTypeError:
		var p ErrorMessage
		err = json.Unmarshal(raw.Payload, &p)
		payload = p
	case MsgTypeStatus:
		var p StatusMessage
		err = json.Unmarshal(raw.Payload, &p)
		payload = p
	case MsgTypeProactiveMessage:
		var p ProactiveMessage
		err = json.Unmarshal(raw.Payload, &p)
		payload = p
	case MsgTypeMCPList:
		var p MCPListRequest
		err = json.Unmarshal(raw.Payload, &p)
		payload = p
	case MsgTypeMCPListResponse:
		var p MCPListResponse
		err = json.Unmarshal(raw.Payload, &p)
		payload = p
	case MsgTypeMCPInstall:
		var p MCPInstallRequest
		err = json.Unmarshal(raw.Payload, &p)
		payload = p
	case MsgTypeMCPInstallResponse:
		var p MCPInstallResponse
		err = json.Unmarshal(raw.Payload, &p)
		payload = p
	case MsgTypeMCPUninstall:
		var p MCPUninstallRequest
		err = json.Unmarshal(raw.Payload, &p)
		payload = p
	case MsgTypeMCPUninstallResponse:
		var p MCPUninstallResponse
		err = json.Unmarshal(raw.Payload, &p)
		payload = p
	case MsgTypeMCPStatus:
		var p MCPStatusRequest
		err = json.Unmarshal(raw.Payload, &p)
		payload = p
	case MsgTypeMCPStatusResponse:
		var p MCPStatusResponse
		err = json.Unmarshal(raw.Payload, &p)
		payload = p
	case MsgTypeMCPRestart:
		var p MCPRestartRequest
		err = json.Unmarshal(raw.Payload, &p)
		payload = p
	case MsgTypeMCPRestartResponse:
		var p MCPRestartResponse
		err = json.Unmarshal(raw.Payload, &p)
		payload = p
	case MsgTypeMCPEnable:
		var p MCPEnableRequest
		err = json.Unmarshal(raw.Payload, &p)
		payload = p
	case MsgTypeMCPEnableResponse:
		var p MCPEnableResponse
		err = json.Unmarshal(raw.Payload, &p)
		payload = p
	default:
		// Unknown type: store raw JSON as-is
		var p map[string]any
		err = json.Unmarshal(raw.Payload, &p)
		payload = p
	}

	if err != nil {
		return nil, fmt.Errorf("failed to parse %s payload: %w", raw.Type, err)
	}
	msg.Payload = payload
	return msg, nil
}

// MarshalMessage creates a JSON-encoded GatewayMessage with the given type and payload.
func MarshalMessage(msgType string, payload any) ([]byte, error) {
	msg := GatewayMessage{
		Type:    msgType,
		Payload: payload,
	}
	return json.Marshal(msg)
}
