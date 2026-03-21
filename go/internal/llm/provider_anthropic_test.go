package llm

import (
	"encoding/json"
	"testing"

	anthropic "github.com/anthropics/anthropic-sdk-go"
)

func TestMessagesToAnthropic(t *testing.T) {
	content := "Hello!"
	msgs := []Message{
		SystemMessage{Content: "You are Clara."},
		UserMessage{Content: "Hi there"},
		AssistantMessage{Content: &content},
	}

	system, got := messagesToAnthropic(msgs)

	// System should be extracted separately.
	if system != "You are Clara." {
		t.Errorf("system = %q, want %q", system, "You are Clara.")
	}

	// Should have 2 messages (user + assistant), not system.
	if len(got) != 2 {
		t.Fatalf("expected 2 messages, got %d", len(got))
	}

	// User message
	if got[0].Role != "user" {
		t.Errorf("msg[0] role = %q, want %q", got[0].Role, "user")
	}

	// Assistant message
	if got[1].Role != "assistant" {
		t.Errorf("msg[1] role = %q, want %q", got[1].Role, "assistant")
	}
}

func TestMessagesToAnthropic_MultipleSystemMessages(t *testing.T) {
	msgs := []Message{
		SystemMessage{Content: "First instruction."},
		SystemMessage{Content: "Second instruction."},
		UserMessage{Content: "Hello"},
	}

	system, got := messagesToAnthropic(msgs)

	if system != "First instruction.\n\nSecond instruction." {
		t.Errorf("system = %q, want concatenated system messages", system)
	}

	if len(got) != 1 {
		t.Fatalf("expected 1 message, got %d", len(got))
	}
}

func TestMessagesToAnthropicToolResult(t *testing.T) {
	msgs := []Message{
		ToolResultMessage{ToolCallID: "toolu_123", Content: "42"},
	}

	system, got := messagesToAnthropic(msgs)

	if system != "" {
		t.Errorf("expected empty system, got %q", system)
	}

	if len(got) != 1 {
		t.Fatalf("expected 1 message, got %d", len(got))
	}

	// Tool results should be sent as user messages in Anthropic format.
	if got[0].Role != "user" {
		t.Errorf("tool result role = %q, want %q", got[0].Role, "user")
	}

	// Verify the content block is a tool_result by marshaling to JSON.
	data, err := json.Marshal(got[0])
	if err != nil {
		t.Fatalf("failed to marshal message: %v", err)
	}

	var parsed map[string]any
	if err := json.Unmarshal(data, &parsed); err != nil {
		t.Fatalf("failed to unmarshal: %v", err)
	}

	content, ok := parsed["content"].([]any)
	if !ok || len(content) == 0 {
		t.Fatal("expected content array with at least one element")
	}

	block, ok := content[0].(map[string]any)
	if !ok {
		t.Fatal("expected content block to be a map")
	}

	if block["type"] != "tool_result" {
		t.Errorf("content block type = %v, want %q", block["type"], "tool_result")
	}
	if block["tool_use_id"] != "toolu_123" {
		t.Errorf("tool_use_id = %v, want %q", block["tool_use_id"], "toolu_123")
	}
}

func TestToolSchemasToAnthropic(t *testing.T) {
	schemas := []ToolSchema{
		{
			Name:        "get_weather",
			Description: "Get weather for a city",
			Parameters: map[string]any{
				"type": "object",
				"properties": map[string]any{
					"city": map[string]any{
						"type":        "string",
						"description": "City name",
					},
				},
				"required": []string{"city"},
			},
		},
	}

	got := toolSchemasToAnthropic(schemas)

	if len(got) != 1 {
		t.Fatalf("expected 1 tool, got %d", len(got))
	}

	tool := got[0]
	if tool.OfTool == nil {
		t.Fatal("expected OfTool to be set")
	}
	if tool.OfTool.Name != "get_weather" {
		t.Errorf("tool name = %q, want %q", tool.OfTool.Name, "get_weather")
	}

	desc := tool.OfTool.Description
	if desc.Value != "Get weather for a city" {
		t.Errorf("tool description = %q, want %q", desc.Value, "Get weather for a city")
	}

	if len(tool.OfTool.InputSchema.Required) != 1 || tool.OfTool.InputSchema.Required[0] != "city" {
		t.Errorf("tool required = %v, want [city]", tool.OfTool.InputSchema.Required)
	}
}

func TestToolSchemasToAnthropic_RequiredAsAny(t *testing.T) {
	// Simulate JSON-unmarshaled required field (comes as []any, not []string).
	schemas := []ToolSchema{
		{
			Name:        "search",
			Description: "Search for something",
			Parameters: map[string]any{
				"type":       "object",
				"properties": map[string]any{},
				"required":   []any{"query"},
			},
		},
	}

	got := toolSchemasToAnthropic(schemas)

	if len(got) != 1 {
		t.Fatalf("expected 1 tool, got %d", len(got))
	}

	if len(got[0].OfTool.InputSchema.Required) != 1 || got[0].OfTool.InputSchema.Required[0] != "query" {
		t.Errorf("required = %v, want [query]", got[0].OfTool.InputSchema.Required)
	}
}

func TestToolResponseFromAnthropic_TextOnly(t *testing.T) {
	msg := &anthropic.Message{
		StopReason: "end_turn",
		Content: []anthropic.ContentBlockUnion{
			{Type: "text", Text: "The weather is sunny."},
		},
	}

	got := toolResponseFromAnthropic(msg)

	if got.Content == nil {
		t.Fatal("expected content to be non-nil")
	}
	if *got.Content != "The weather is sunny." {
		t.Errorf("content = %q, want %q", *got.Content, "The weather is sunny.")
	}
	if got.HasToolCalls() {
		t.Error("expected no tool calls")
	}
	if got.StopReason != "end_turn" {
		t.Errorf("stop reason = %q, want %q", got.StopReason, "end_turn")
	}
}

func TestToolResponseFromAnthropic_ToolUse(t *testing.T) {
	msg := &anthropic.Message{
		StopReason: "tool_use",
		Content: []anthropic.ContentBlockUnion{
			{Type: "text", Text: "Let me check the weather."},
			{
				Type:  "tool_use",
				ID:    "toolu_abc123",
				Name:  "get_weather",
				Input: json.RawMessage(`{"city":"Portland"}`),
			},
		},
	}

	got := toolResponseFromAnthropic(msg)

	// Should have both text and tool calls.
	if got.Content == nil {
		t.Fatal("expected content to be non-nil")
	}
	if *got.Content != "Let me check the weather." {
		t.Errorf("content = %q, want %q", *got.Content, "Let me check the weather.")
	}

	if !got.HasToolCalls() {
		t.Fatal("expected tool calls")
	}
	if len(got.ToolCalls) != 1 {
		t.Fatalf("expected 1 tool call, got %d", len(got.ToolCalls))
	}

	tc := got.ToolCalls[0]
	if tc.ID != "toolu_abc123" {
		t.Errorf("tool call ID = %q, want %q", tc.ID, "toolu_abc123")
	}
	if tc.Name != "get_weather" {
		t.Errorf("tool call name = %q, want %q", tc.Name, "get_weather")
	}
	if tc.Arguments["city"] != "Portland" {
		t.Errorf("tool call args[city] = %v, want %q", tc.Arguments["city"], "Portland")
	}
	if tc.RawArguments != `{"city":"Portland"}` {
		t.Errorf("raw arguments = %q, want %q", tc.RawArguments, `{"city":"Portland"}`)
	}
	if got.StopReason != "tool_use" {
		t.Errorf("stop reason = %q, want %q", got.StopReason, "tool_use")
	}
}

func TestToolResponseFromAnthropic_NoContent(t *testing.T) {
	msg := &anthropic.Message{
		StopReason: "tool_use",
		Content: []anthropic.ContentBlockUnion{
			{
				Type:  "tool_use",
				ID:    "toolu_xyz",
				Name:  "search",
				Input: json.RawMessage(`{"query":"test"}`),
			},
		},
	}

	got := toolResponseFromAnthropic(msg)

	// No text blocks means nil content.
	if got.Content != nil {
		t.Errorf("expected nil content, got %q", *got.Content)
	}
	if !got.HasToolCalls() {
		t.Fatal("expected tool calls")
	}
}

func TestNewAnthropicProviderBaseURL(t *testing.T) {
	tests := []struct {
		name    string
		config  *LLMConfig
		wantURL string
		wantErr bool
	}{
		{
			name: "default (no base URL)",
			config: &LLMConfig{
				Provider: "anthropic",
				APIKey:   "test-key",
			},
			wantURL: "",
		},
		{
			name: "custom base URL for proxy",
			config: &LLMConfig{
				Provider: "anthropic",
				APIKey:   "test-key",
				BaseURL:  "https://my-clewdr-proxy.example.com",
			},
			wantURL: "https://my-clewdr-proxy.example.com",
		},
		{
			name:    "nil config",
			config:  nil,
			wantErr: true,
		},
		{
			name: "missing API key",
			config: &LLMConfig{
				Provider: "anthropic",
				APIKey:   "",
			},
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			provider, err := NewAnthropicProvider(tt.config)

			if tt.wantErr {
				if err == nil {
					t.Fatal("expected error, got nil")
				}
				return
			}

			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}

			if provider.baseURL != tt.wantURL {
				t.Errorf("baseURL = %q, want %q", provider.baseURL, tt.wantURL)
			}
			if provider.Name() != "anthropic" {
				t.Errorf("Name() = %q, want %q", provider.Name(), "anthropic")
			}
		})
	}
}

func TestAnthropicProvider_ImplementsProvider(t *testing.T) {
	// Compile-time check that AnthropicProvider implements Provider.
	var _ Provider = (*AnthropicProvider)(nil)
}
