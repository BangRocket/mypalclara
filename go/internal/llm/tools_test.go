package llm

import (
	"encoding/json"
	"testing"
)

func TestToolCallToOpenAIFormat(t *testing.T) {
	tc := ToolCall{
		ID:        "call_123",
		Name:      "search",
		Arguments: map[string]any{"query": "hello"},
	}
	got := tc.ToOpenAIFormat()

	if got["id"] != "call_123" {
		t.Errorf("id = %v, want call_123", got["id"])
	}
	if got["type"] != "function" {
		t.Errorf("type = %v, want function", got["type"])
	}
	fn, ok := got["function"].(map[string]any)
	if !ok {
		t.Fatalf("function is not map, got %T", got["function"])
	}
	if fn["name"] != "search" {
		t.Errorf("name = %v, want search", fn["name"])
	}
	// arguments should be JSON string
	argsStr, ok := fn["arguments"].(string)
	if !ok {
		t.Fatalf("arguments is not string, got %T", fn["arguments"])
	}
	var parsed map[string]any
	if err := json.Unmarshal([]byte(argsStr), &parsed); err != nil {
		t.Fatalf("failed to parse arguments JSON: %v", err)
	}
	if parsed["query"] != "hello" {
		t.Errorf("parsed query = %v, want hello", parsed["query"])
	}
}

func TestToolCallToResultMessage(t *testing.T) {
	tc := ToolCall{ID: "call_1", Name: "search", Arguments: map[string]any{}}
	result := tc.ToResultMessage("found it")

	if result.ToolCallID != "call_1" {
		t.Errorf("ToolCallID = %v, want call_1", result.ToolCallID)
	}
	if result.Content != "found it" {
		t.Errorf("Content = %v, want 'found it'", result.Content)
	}
}

func TestToolCallFromOpenAIValid(t *testing.T) {
	d := map[string]any{
		"id":   "call_abc",
		"type": "function",
		"function": map[string]any{
			"name":      "get_weather",
			"arguments": `{"city":"NYC","units":"metric"}`,
		},
	}
	tc := ToolCallFromOpenAI(d)

	if tc.ID != "call_abc" {
		t.Errorf("ID = %v, want call_abc", tc.ID)
	}
	if tc.Name != "get_weather" {
		t.Errorf("Name = %v, want get_weather", tc.Name)
	}
	if tc.Arguments["city"] != "NYC" {
		t.Errorf("city = %v, want NYC", tc.Arguments["city"])
	}
	if tc.Arguments["units"] != "metric" {
		t.Errorf("units = %v, want metric", tc.Arguments["units"])
	}
	if tc.RawArguments != `{"city":"NYC","units":"metric"}` {
		t.Errorf("RawArguments = %v, want original JSON", tc.RawArguments)
	}
}

func TestToolCallFromOpenAIInvalidJSON(t *testing.T) {
	d := map[string]any{
		"id":   "call_bad",
		"type": "function",
		"function": map[string]any{
			"name":      "broken",
			"arguments": `{not valid json`,
		},
	}
	tc := ToolCallFromOpenAI(d)

	if tc.Name != "broken" {
		t.Errorf("Name = %v, want broken", tc.Name)
	}
	// Should fall back to empty map
	if len(tc.Arguments) != 0 {
		t.Errorf("Arguments should be empty map, got %v", tc.Arguments)
	}
	if tc.RawArguments != `{not valid json` {
		t.Errorf("RawArguments = %v, want original string", tc.RawArguments)
	}
}

func TestToolCallFromOpenAIEmptyArgs(t *testing.T) {
	d := map[string]any{
		"id":   "call_empty",
		"type": "function",
		"function": map[string]any{
			"name":      "no_args",
			"arguments": "",
		},
	}
	tc := ToolCallFromOpenAI(d)
	if len(tc.Arguments) != 0 {
		t.Errorf("Arguments should be empty map, got %v", tc.Arguments)
	}
}

func TestToolResponseHasToolCalls(t *testing.T) {
	tests := []struct {
		name string
		resp ToolResponse
		want bool
	}{
		{"no tool calls", ToolResponse{}, false},
		{"empty slice", ToolResponse{ToolCalls: []ToolCall{}}, false},
		{"with tool calls", ToolResponse{ToolCalls: []ToolCall{{ID: "1", Name: "x", Arguments: map[string]any{}}}}, true},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := tt.resp.HasToolCalls(); got != tt.want {
				t.Errorf("HasToolCalls() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestToolResponseToAssistantMessage(t *testing.T) {
	content := "I'll search for that."
	resp := ToolResponse{
		Content: &content,
		ToolCalls: []ToolCall{
			{ID: "call_1", Name: "search", Arguments: map[string]any{"q": "test"}},
		},
		StopReason: "tool_use",
	}
	msg := resp.ToAssistantMessage()

	if msg.Content == nil || *msg.Content != "I'll search for that." {
		t.Errorf("Content = %v, want 'I'll search for that.'", msg.Content)
	}
	if len(msg.ToolCalls) != 1 {
		t.Fatalf("len(ToolCalls) = %d, want 1", len(msg.ToolCalls))
	}
	if msg.ToolCalls[0].Name != "search" {
		t.Errorf("ToolCalls[0].Name = %v, want search", msg.ToolCalls[0].Name)
	}

	// Verify it's a copy (modifying original doesn't affect message)
	resp.ToolCalls[0].Name = "modified"
	if msg.ToolCalls[0].Name != "search" {
		t.Error("ToAssistantMessage should copy tool calls, not reference them")
	}
}

func TestToolResponseToAssistantMessageNilContent(t *testing.T) {
	resp := ToolResponse{
		Content:   nil,
		ToolCalls: []ToolCall{{ID: "c1", Name: "fn", Arguments: map[string]any{}}},
	}
	msg := resp.ToAssistantMessage()
	if msg.Content != nil {
		t.Errorf("Content = %v, want nil", msg.Content)
	}
}
