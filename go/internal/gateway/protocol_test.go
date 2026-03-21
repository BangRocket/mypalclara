package gateway

import (
	"encoding/json"
	"testing"
	"time"
)

func TestParseMessage_Register(t *testing.T) {
	data := `{"type":"register","payload":{"node_id":"discord-1","platform":"discord","capabilities":["streaming","attachments"]}}`
	msg, err := ParseMessage([]byte(data))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if msg.Type != MsgTypeRegister {
		t.Errorf("expected type %q, got %q", MsgTypeRegister, msg.Type)
	}
	reg, ok := msg.Payload.(RegisterMessage)
	if !ok {
		t.Fatalf("expected RegisterMessage, got %T", msg.Payload)
	}
	if reg.NodeID != "discord-1" {
		t.Errorf("expected node_id %q, got %q", "discord-1", reg.NodeID)
	}
	if reg.Platform != "discord" {
		t.Errorf("expected platform %q, got %q", "discord", reg.Platform)
	}
	if len(reg.Capabilities) != 2 {
		t.Errorf("expected 2 capabilities, got %d", len(reg.Capabilities))
	}
}

func TestParseMessage_Ping(t *testing.T) {
	data := `{"type":"ping","payload":{"timestamp":"2026-03-21T12:00:00Z"}}`
	msg, err := ParseMessage([]byte(data))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if msg.Type != MsgTypePing {
		t.Errorf("expected type %q, got %q", MsgTypePing, msg.Type)
	}
	ping, ok := msg.Payload.(PingMessage)
	if !ok {
		t.Fatalf("expected PingMessage, got %T", msg.Payload)
	}
	expected := time.Date(2026, 3, 21, 12, 0, 0, 0, time.UTC)
	if !ping.Timestamp.Equal(expected) {
		t.Errorf("expected timestamp %v, got %v", expected, ping.Timestamp)
	}
}

func TestParseMessage_Message(t *testing.T) {
	data := `{"type":"message","payload":{"id":"msg-1","content":"hello","user":{"id":"discord-123","platform_id":"123","name":"testuser"},"channel":{"id":"ch-1","type":"dm"}}}`
	msg, err := ParseMessage([]byte(data))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if msg.Type != MsgTypeMessage {
		t.Errorf("expected type %q, got %q", MsgTypeMessage, msg.Type)
	}
	req, ok := msg.Payload.(MessageRequest)
	if !ok {
		t.Fatalf("expected MessageRequest, got %T", msg.Payload)
	}
	if req.ID != "msg-1" {
		t.Errorf("expected id %q, got %q", "msg-1", req.ID)
	}
	if req.Content != "hello" {
		t.Errorf("expected content %q, got %q", "hello", req.Content)
	}
	if req.User.ID != "discord-123" {
		t.Errorf("expected user.id %q, got %q", "discord-123", req.User.ID)
	}
	if req.Channel.Type != "dm" {
		t.Errorf("expected channel.type %q, got %q", "dm", req.Channel.Type)
	}
}

func TestParseMessage_ResponseStart(t *testing.T) {
	data := `{"type":"response_start","payload":{"id":"resp-1","request_id":"msg-1","model_tier":"high"}}`
	msg, err := ParseMessage([]byte(data))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	rs, ok := msg.Payload.(ResponseStart)
	if !ok {
		t.Fatalf("expected ResponseStart, got %T", msg.Payload)
	}
	if rs.RequestID != "msg-1" {
		t.Errorf("expected request_id %q, got %q", "msg-1", rs.RequestID)
	}
	if rs.ModelTier != "high" {
		t.Errorf("expected model_tier %q, got %q", "high", rs.ModelTier)
	}
}

func TestParseMessage_ResponseChunk(t *testing.T) {
	data := `{"type":"response_chunk","payload":{"id":"resp-1","request_id":"msg-1","chunk":"Hello","accumulated":"Hello"}}`
	msg, err := ParseMessage([]byte(data))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	rc, ok := msg.Payload.(ResponseChunk)
	if !ok {
		t.Fatalf("expected ResponseChunk, got %T", msg.Payload)
	}
	if rc.Chunk != "Hello" {
		t.Errorf("expected chunk %q, got %q", "Hello", rc.Chunk)
	}
}

func TestParseMessage_ResponseEnd(t *testing.T) {
	data := `{"type":"response_end","payload":{"id":"resp-1","request_id":"msg-1","full_text":"Hello world","tool_count":2,"files":["a.txt"]}}`
	msg, err := ParseMessage([]byte(data))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	re, ok := msg.Payload.(ResponseEnd)
	if !ok {
		t.Fatalf("expected ResponseEnd, got %T", msg.Payload)
	}
	if re.FullText != "Hello world" {
		t.Errorf("expected full_text %q, got %q", "Hello world", re.FullText)
	}
	if re.ToolCount != 2 {
		t.Errorf("expected tool_count 2, got %d", re.ToolCount)
	}
	if len(re.Files) != 1 || re.Files[0] != "a.txt" {
		t.Errorf("expected files [a.txt], got %v", re.Files)
	}
}

func TestParseMessage_ToolStart(t *testing.T) {
	data := `{"type":"tool_start","payload":{"id":"resp-1","request_id":"msg-1","tool_name":"web_search","step":1,"emoji":"🔍"}}`
	msg, err := ParseMessage([]byte(data))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	ts, ok := msg.Payload.(ToolStart)
	if !ok {
		t.Fatalf("expected ToolStart, got %T", msg.Payload)
	}
	if ts.ToolName != "web_search" {
		t.Errorf("expected tool_name %q, got %q", "web_search", ts.ToolName)
	}
	if ts.Step != 1 {
		t.Errorf("expected step 1, got %d", ts.Step)
	}
}

func TestParseMessage_ToolResult(t *testing.T) {
	dur := 150
	data := `{"type":"tool_result","payload":{"id":"resp-1","request_id":"msg-1","tool_name":"web_search","success":true,"output_preview":"found 5 results","duration_ms":150}}`
	msg, err := ParseMessage([]byte(data))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	tr, ok := msg.Payload.(ToolResult)
	if !ok {
		t.Fatalf("expected ToolResult, got %T", msg.Payload)
	}
	if !tr.Success {
		t.Error("expected success=true")
	}
	if tr.OutputPreview != "found 5 results" {
		t.Errorf("expected output_preview %q, got %q", "found 5 results", tr.OutputPreview)
	}
	if tr.DurationMs == nil || *tr.DurationMs != dur {
		t.Errorf("expected duration_ms %d, got %v", dur, tr.DurationMs)
	}
}

func TestParseMessage_Cancel(t *testing.T) {
	data := `{"type":"cancel","payload":{"request_id":"msg-1","reason":"user requested"}}`
	msg, err := ParseMessage([]byte(data))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	c, ok := msg.Payload.(CancelMessage)
	if !ok {
		t.Fatalf("expected CancelMessage, got %T", msg.Payload)
	}
	if c.RequestID != "msg-1" {
		t.Errorf("expected request_id %q, got %q", "msg-1", c.RequestID)
	}
	if c.Reason != "user requested" {
		t.Errorf("expected reason %q, got %q", "user requested", c.Reason)
	}
}

func TestParseMessage_Cancelled(t *testing.T) {
	data := `{"type":"cancelled","payload":{"request_id":"msg-1"}}`
	msg, err := ParseMessage([]byte(data))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	c, ok := msg.Payload.(CancelledMessage)
	if !ok {
		t.Fatalf("expected CancelledMessage, got %T", msg.Payload)
	}
	if c.RequestID != "msg-1" {
		t.Errorf("expected request_id %q, got %q", "msg-1", c.RequestID)
	}
}

func TestParseMessage_Error(t *testing.T) {
	data := `{"type":"error","payload":{"code":"rate_limited","message":"Too many requests","recoverable":true}}`
	msg, err := ParseMessage([]byte(data))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	e, ok := msg.Payload.(ErrorMessage)
	if !ok {
		t.Fatalf("expected ErrorMessage, got %T", msg.Payload)
	}
	if e.Code != "rate_limited" {
		t.Errorf("expected code %q, got %q", "rate_limited", e.Code)
	}
	if e.Message != "Too many requests" {
		t.Errorf("expected message %q, got %q", "Too many requests", e.Message)
	}
	if !e.Recoverable {
		t.Error("expected recoverable=true")
	}
}

func TestParseMessage_Status(t *testing.T) {
	data := `{"type":"status","payload":{"node_id":"discord-1","active_requests":3,"queue_length":1}}`
	msg, err := ParseMessage([]byte(data))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	s, ok := msg.Payload.(StatusMessage)
	if !ok {
		t.Fatalf("expected StatusMessage, got %T", msg.Payload)
	}
	if s.NodeID != "discord-1" {
		t.Errorf("expected node_id %q, got %q", "discord-1", s.NodeID)
	}
	if s.ActiveRequests != 3 {
		t.Errorf("expected active_requests 3, got %d", s.ActiveRequests)
	}
}

func TestParseMessage_ProactiveMessage(t *testing.T) {
	data := `{"type":"proactive_message","payload":{"user":{"id":"discord-123","platform_id":"123"},"channel":{"id":"ch-1","type":"dm"},"content":"Hey!","priority":"high"}}`
	msg, err := ParseMessage([]byte(data))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	pm, ok := msg.Payload.(ProactiveMessage)
	if !ok {
		t.Fatalf("expected ProactiveMessage, got %T", msg.Payload)
	}
	if pm.Content != "Hey!" {
		t.Errorf("expected content %q, got %q", "Hey!", pm.Content)
	}
	if pm.Priority != "high" {
		t.Errorf("expected priority %q, got %q", "high", pm.Priority)
	}
}

func TestParseMessage_NullPayload(t *testing.T) {
	data := `{"type":"ping","payload":null}`
	msg, err := ParseMessage([]byte(data))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if msg.Type != MsgTypePing {
		t.Errorf("expected type %q, got %q", MsgTypePing, msg.Type)
	}
	if msg.Payload != nil {
		t.Errorf("expected nil payload, got %v", msg.Payload)
	}
}

func TestParseMessage_MissingType(t *testing.T) {
	data := `{"payload":{"id":"123"}}`
	_, err := ParseMessage([]byte(data))
	if err == nil {
		t.Fatal("expected error for missing type")
	}
}

func TestParseMessage_InvalidJSON(t *testing.T) {
	_, err := ParseMessage([]byte(`not json`))
	if err == nil {
		t.Fatal("expected error for invalid JSON")
	}
}

func TestParseMessage_UnknownType(t *testing.T) {
	data := `{"type":"unknown_future_type","payload":{"foo":"bar"}}`
	msg, err := ParseMessage([]byte(data))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if msg.Type != "unknown_future_type" {
		t.Errorf("expected type %q, got %q", "unknown_future_type", msg.Type)
	}
	// Should be stored as map[string]any
	m, ok := msg.Payload.(map[string]any)
	if !ok {
		t.Fatalf("expected map[string]any for unknown type, got %T", msg.Payload)
	}
	if m["foo"] != "bar" {
		t.Errorf("expected foo=bar, got %v", m["foo"])
	}
}

func TestMarshalMessage_RoundTrip(t *testing.T) {
	original := ResponseChunk{
		ID:          "resp-1",
		RequestID:   "msg-1",
		Chunk:       "Hello ",
		Accumulated: "Hello ",
	}

	data, err := MarshalMessage(MsgTypeResponseChunk, original)
	if err != nil {
		t.Fatalf("MarshalMessage error: %v", err)
	}

	msg, err := ParseMessage(data)
	if err != nil {
		t.Fatalf("ParseMessage error: %v", err)
	}

	if msg.Type != MsgTypeResponseChunk {
		t.Errorf("expected type %q, got %q", MsgTypeResponseChunk, msg.Type)
	}

	rc, ok := msg.Payload.(ResponseChunk)
	if !ok {
		t.Fatalf("expected ResponseChunk, got %T", msg.Payload)
	}
	if rc.Chunk != "Hello " {
		t.Errorf("expected chunk %q, got %q", "Hello ", rc.Chunk)
	}
	if rc.Accumulated != "Hello " {
		t.Errorf("expected accumulated %q, got %q", "Hello ", rc.Accumulated)
	}
}

func TestMarshalMessage_ErrorRoundTrip(t *testing.T) {
	original := ErrorMessage{
		Code:        "internal",
		Message:     "something broke",
		Recoverable: false,
		RequestID:   "req-42",
	}

	data, err := MarshalMessage(MsgTypeError, original)
	if err != nil {
		t.Fatalf("MarshalMessage error: %v", err)
	}

	msg, err := ParseMessage(data)
	if err != nil {
		t.Fatalf("ParseMessage error: %v", err)
	}

	e, ok := msg.Payload.(ErrorMessage)
	if !ok {
		t.Fatalf("expected ErrorMessage, got %T", msg.Payload)
	}
	if e.Code != "internal" {
		t.Errorf("expected code %q, got %q", "internal", e.Code)
	}
	if e.Recoverable {
		t.Error("expected recoverable=false")
	}
}

func TestMarshalMessage_RegisterRoundTrip(t *testing.T) {
	original := RegisterMessage{
		NodeID:       "slack-node-1",
		Platform:     "slack",
		Capabilities: []string{"streaming", "reactions"},
		Metadata:     map[string]any{"version": "1.0"},
	}

	data, err := MarshalMessage(MsgTypeRegister, original)
	if err != nil {
		t.Fatalf("MarshalMessage error: %v", err)
	}

	msg, err := ParseMessage(data)
	if err != nil {
		t.Fatalf("ParseMessage error: %v", err)
	}

	reg, ok := msg.Payload.(RegisterMessage)
	if !ok {
		t.Fatalf("expected RegisterMessage, got %T", msg.Payload)
	}
	if reg.NodeID != "slack-node-1" {
		t.Errorf("expected node_id %q, got %q", "slack-node-1", reg.NodeID)
	}
	if len(reg.Capabilities) != 2 {
		t.Errorf("expected 2 capabilities, got %d", len(reg.Capabilities))
	}
}

func TestMessageRequestDeserialization(t *testing.T) {
	raw := `{
		"type": "message",
		"payload": {
			"id": "msg-abc-123",
			"content": "What's the weather like?",
			"user": {
				"id": "discord-456",
				"platform_id": "456",
				"name": "weatherfan",
				"display_name": "Weather Fan"
			},
			"channel": {
				"id": "general-789",
				"type": "server",
				"name": "general",
				"guild_id": "guild-100",
				"guild_name": "My Server"
			},
			"tier_override": "high",
			"attachments": [
				{
					"type": "image",
					"filename": "screenshot.png",
					"media_type": "image/png",
					"base64_data": "iVBORw0KGgo=",
					"size": 1024
				},
				{
					"type": "text",
					"filename": "notes.txt",
					"content": "some notes here"
				}
			],
			"reply_chain": [
				{"role": "user", "content": "previous message"},
				{"role": "assistant", "content": "previous reply"}
			],
			"metadata": {
				"source": "slash_command",
				"guild_locale": "en-US"
			}
		}
	}`

	msg, err := ParseMessage([]byte(raw))
	if err != nil {
		t.Fatalf("ParseMessage error: %v", err)
	}

	if msg.Type != MsgTypeMessage {
		t.Fatalf("expected type %q, got %q", MsgTypeMessage, msg.Type)
	}

	req, ok := msg.Payload.(MessageRequest)
	if !ok {
		t.Fatalf("expected MessageRequest, got %T", msg.Payload)
	}

	// Verify top-level fields
	if req.ID != "msg-abc-123" {
		t.Errorf("expected id %q, got %q", "msg-abc-123", req.ID)
	}
	if req.Content != "What's the weather like?" {
		t.Errorf("expected content %q, got %q", "What's the weather like?", req.Content)
	}
	if req.TierOverride != "high" {
		t.Errorf("expected tier_override %q, got %q", "high", req.TierOverride)
	}

	// Verify user info
	if req.User.ID != "discord-456" {
		t.Errorf("expected user.id %q, got %q", "discord-456", req.User.ID)
	}
	if req.User.PlatformID != "456" {
		t.Errorf("expected user.platform_id %q, got %q", "456", req.User.PlatformID)
	}
	if req.User.Name != "weatherfan" {
		t.Errorf("expected user.name %q, got %q", "weatherfan", req.User.Name)
	}
	if req.User.DisplayName != "Weather Fan" {
		t.Errorf("expected user.display_name %q, got %q", "Weather Fan", req.User.DisplayName)
	}

	// Verify channel info
	if req.Channel.ID != "general-789" {
		t.Errorf("expected channel.id %q, got %q", "general-789", req.Channel.ID)
	}
	if req.Channel.Type != "server" {
		t.Errorf("expected channel.type %q, got %q", "server", req.Channel.Type)
	}
	if req.Channel.Name != "general" {
		t.Errorf("expected channel.name %q, got %q", "general", req.Channel.Name)
	}
	if req.Channel.GuildID != "guild-100" {
		t.Errorf("expected channel.guild_id %q, got %q", "guild-100", req.Channel.GuildID)
	}
	if req.Channel.GuildName != "My Server" {
		t.Errorf("expected channel.guild_name %q, got %q", "My Server", req.Channel.GuildName)
	}

	// Verify attachments
	if len(req.Attachments) != 2 {
		t.Fatalf("expected 2 attachments, got %d", len(req.Attachments))
	}

	img := req.Attachments[0]
	if img.Type != "image" {
		t.Errorf("expected attachment[0].type %q, got %q", "image", img.Type)
	}
	if img.Filename != "screenshot.png" {
		t.Errorf("expected attachment[0].filename %q, got %q", "screenshot.png", img.Filename)
	}
	if img.MediaType != "image/png" {
		t.Errorf("expected attachment[0].media_type %q, got %q", "image/png", img.MediaType)
	}
	if img.Base64Data != "iVBORw0KGgo=" {
		t.Errorf("expected attachment[0].base64_data %q, got %q", "iVBORw0KGgo=", img.Base64Data)
	}
	if img.Size == nil || *img.Size != 1024 {
		t.Errorf("expected attachment[0].size 1024, got %v", img.Size)
	}

	txt := req.Attachments[1]
	if txt.Type != "text" {
		t.Errorf("expected attachment[1].type %q, got %q", "text", txt.Type)
	}
	if txt.Content != "some notes here" {
		t.Errorf("expected attachment[1].content %q, got %q", "some notes here", txt.Content)
	}

	// Verify reply chain
	if len(req.ReplyChain) != 2 {
		t.Fatalf("expected 2 reply chain entries, got %d", len(req.ReplyChain))
	}
	if req.ReplyChain[0]["role"] != "user" {
		t.Errorf("expected reply_chain[0].role %q, got %v", "user", req.ReplyChain[0]["role"])
	}

	// Verify metadata
	if req.Metadata["source"] != "slash_command" {
		t.Errorf("expected metadata.source %q, got %v", "slash_command", req.Metadata["source"])
	}
}

func TestMarshalMessage_JSONStructure(t *testing.T) {
	payload := PingMessage{
		Timestamp: time.Date(2026, 3, 21, 12, 0, 0, 0, time.UTC),
	}

	data, err := MarshalMessage(MsgTypePing, payload)
	if err != nil {
		t.Fatalf("MarshalMessage error: %v", err)
	}

	// Verify the JSON structure has type and payload at top level
	var raw map[string]json.RawMessage
	if err := json.Unmarshal(data, &raw); err != nil {
		t.Fatalf("failed to unmarshal output: %v", err)
	}

	if _, ok := raw["type"]; !ok {
		t.Error("missing 'type' key in output")
	}
	if _, ok := raw["payload"]; !ok {
		t.Error("missing 'payload' key in output")
	}

	var msgType string
	if err := json.Unmarshal(raw["type"], &msgType); err != nil {
		t.Fatalf("failed to unmarshal type: %v", err)
	}
	if msgType != MsgTypePing {
		t.Errorf("expected type %q, got %q", MsgTypePing, msgType)
	}
}

func TestMarshalMessage_ResponseEndWithComponents(t *testing.T) {
	payload := ResponseEnd{
		ID:        "resp-1",
		RequestID: "msg-1",
		FullText:  "Done!",
		ToolCount: 1,
		Components: []ButtonInfo{
			{Label: "OK", Style: "primary", Action: "dismiss"},
		},
		FileData: []FileData{
			{Filename: "output.csv", ContentBase64: "YSxiLGM=", MediaType: "text/csv"},
		},
	}

	data, err := MarshalMessage(MsgTypeResponseEnd, payload)
	if err != nil {
		t.Fatalf("MarshalMessage error: %v", err)
	}

	msg, err := ParseMessage(data)
	if err != nil {
		t.Fatalf("ParseMessage error: %v", err)
	}

	re, ok := msg.Payload.(ResponseEnd)
	if !ok {
		t.Fatalf("expected ResponseEnd, got %T", msg.Payload)
	}
	if len(re.Components) != 1 {
		t.Fatalf("expected 1 component, got %d", len(re.Components))
	}
	if re.Components[0].Label != "OK" {
		t.Errorf("expected component label %q, got %q", "OK", re.Components[0].Label)
	}
	if len(re.FileData) != 1 {
		t.Fatalf("expected 1 file_data, got %d", len(re.FileData))
	}
	if re.FileData[0].Filename != "output.csv" {
		t.Errorf("expected file_data filename %q, got %q", "output.csv", re.FileData[0].Filename)
	}
}
