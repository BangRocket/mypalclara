package llm

import (
	"testing"
)

func strPtr(s string) *string { return &s }

func TestSystemMessageToOpenAI(t *testing.T) {
	msg := SystemMessage{Content: "You are a helpful assistant."}
	got := msg.ToOpenAI()

	if got["role"] != "system" {
		t.Errorf("role = %v, want system", got["role"])
	}
	if got["content"] != "You are a helpful assistant." {
		t.Errorf("content = %v, want 'You are a helpful assistant.'", got["content"])
	}
}

func TestSystemMessageRole(t *testing.T) {
	msg := SystemMessage{Content: "x"}
	if msg.Role() != "system" {
		t.Errorf("Role() = %v, want system", msg.Role())
	}
}

func TestUserMessageToOpenAIPlainText(t *testing.T) {
	msg := UserMessage{Content: "Hello!"}
	got := msg.ToOpenAI()

	if got["role"] != "user" {
		t.Errorf("role = %v, want user", got["role"])
	}
	if got["content"] != "Hello!" {
		t.Errorf("content = %v, want 'Hello!'", got["content"])
	}
}

func TestUserMessageToOpenAIWithParts(t *testing.T) {
	msg := UserMessage{
		Content: "Describe this image",
		Parts: []ContentPart{
			{Type: ContentPartText, Text: "Describe this image"},
			{Type: ContentPartImageURL, URL: "https://example.com/img.png"},
		},
	}
	got := msg.ToOpenAI()

	if got["role"] != "user" {
		t.Errorf("role = %v, want user", got["role"])
	}
	parts, ok := got["content"].([]map[string]any)
	if !ok {
		t.Fatalf("content is not []map[string]any, got %T", got["content"])
	}
	if len(parts) != 2 {
		t.Fatalf("len(parts) = %d, want 2", len(parts))
	}
	if parts[0]["type"] != "text" {
		t.Errorf("parts[0].type = %v, want text", parts[0]["type"])
	}
	if parts[1]["type"] != "image_url" {
		t.Errorf("parts[1].type = %v, want image_url", parts[1]["type"])
	}
	imgURL, ok := parts[1]["image_url"].(map[string]any)
	if !ok {
		t.Fatalf("image_url is not map, got %T", parts[1]["image_url"])
	}
	if imgURL["url"] != "https://example.com/img.png" {
		t.Errorf("image url = %v, want https://example.com/img.png", imgURL["url"])
	}
}

func TestUserMessageRole(t *testing.T) {
	msg := UserMessage{Content: "x"}
	if msg.Role() != "user" {
		t.Errorf("Role() = %v, want user", msg.Role())
	}
}

func TestAssistantMessageToOpenAITextOnly(t *testing.T) {
	content := "Hello there!"
	msg := AssistantMessage{Content: &content}
	got := msg.ToOpenAI()

	if got["role"] != "assistant" {
		t.Errorf("role = %v, want assistant", got["role"])
	}
	if *(got["content"].(*string)) != "Hello there!" {
		t.Errorf("content = %v, want 'Hello there!'", got["content"])
	}
	if _, exists := got["tool_calls"]; exists {
		t.Error("tool_calls should not be present when empty")
	}
}

func TestAssistantMessageToOpenAIWithToolCalls(t *testing.T) {
	msg := AssistantMessage{
		Content: nil,
		ToolCalls: []ToolCall{
			{ID: "call_1", Name: "search", Arguments: map[string]any{"query": "test"}},
		},
	}
	got := msg.ToOpenAI()

	if got["content"] != nil {
		t.Errorf("content = %v, want nil", got["content"])
	}
	tcs, ok := got["tool_calls"].([]map[string]any)
	if !ok {
		t.Fatalf("tool_calls is not []map[string]any, got %T", got["tool_calls"])
	}
	if len(tcs) != 1 {
		t.Fatalf("len(tool_calls) = %d, want 1", len(tcs))
	}
	if tcs[0]["id"] != "call_1" {
		t.Errorf("tool_calls[0].id = %v, want call_1", tcs[0]["id"])
	}
}

func TestAssistantMessageRole(t *testing.T) {
	msg := AssistantMessage{}
	if msg.Role() != "assistant" {
		t.Errorf("Role() = %v, want assistant", msg.Role())
	}
}

func TestToolResultMessageToOpenAI(t *testing.T) {
	msg := ToolResultMessage{ToolCallID: "call_1", Content: "result data"}
	got := msg.ToOpenAI()

	if got["role"] != "tool" {
		t.Errorf("role = %v, want tool", got["role"])
	}
	if got["tool_call_id"] != "call_1" {
		t.Errorf("tool_call_id = %v, want call_1", got["tool_call_id"])
	}
	if got["content"] != "result data" {
		t.Errorf("content = %v, want 'result data'", got["content"])
	}
}

func TestToolResultMessageRole(t *testing.T) {
	msg := ToolResultMessage{ToolCallID: "x", Content: "y"}
	if msg.Role() != "tool" {
		t.Errorf("Role() = %v, want tool", msg.Role())
	}
}

func TestMessageFromDictSystem(t *testing.T) {
	msg, err := MessageFromDict(map[string]any{"role": "system", "content": "Be helpful."})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	sm, ok := msg.(SystemMessage)
	if !ok {
		t.Fatalf("expected SystemMessage, got %T", msg)
	}
	if sm.Content != "Be helpful." {
		t.Errorf("content = %v, want 'Be helpful.'", sm.Content)
	}
}

func TestMessageFromDictUser(t *testing.T) {
	msg, err := MessageFromDict(map[string]any{"role": "user", "content": "Hi"})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	um, ok := msg.(UserMessage)
	if !ok {
		t.Fatalf("expected UserMessage, got %T", msg)
	}
	if um.Content != "Hi" {
		t.Errorf("content = %v, want 'Hi'", um.Content)
	}
}

func TestMessageFromDictUserMultimodal(t *testing.T) {
	msg, err := MessageFromDict(map[string]any{
		"role": "user",
		"content": []any{
			map[string]any{"type": "text", "text": "Look at this"},
			map[string]any{"type": "image_url", "image_url": map[string]any{"url": "https://example.com/img.png"}},
		},
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	um, ok := msg.(UserMessage)
	if !ok {
		t.Fatalf("expected UserMessage, got %T", msg)
	}
	if um.Content != "Look at this" {
		t.Errorf("content = %v, want 'Look at this'", um.Content)
	}
	if len(um.Parts) != 2 {
		t.Fatalf("len(parts) = %d, want 2", len(um.Parts))
	}
	if um.Parts[0].Type != ContentPartText {
		t.Errorf("parts[0].type = %v, want text", um.Parts[0].Type)
	}
	if um.Parts[1].Type != ContentPartImageURL {
		t.Errorf("parts[1].type = %v, want image_url", um.Parts[1].Type)
	}
}

func TestMessageFromDictAssistant(t *testing.T) {
	msg, err := MessageFromDict(map[string]any{"role": "assistant", "content": "Sure!"})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	am, ok := msg.(AssistantMessage)
	if !ok {
		t.Fatalf("expected AssistantMessage, got %T", msg)
	}
	if am.Content == nil || *am.Content != "Sure!" {
		t.Errorf("content = %v, want 'Sure!'", am.Content)
	}
}

func TestMessageFromDictAssistantWithToolCalls(t *testing.T) {
	msg, err := MessageFromDict(map[string]any{
		"role":    "assistant",
		"content": nil,
		"tool_calls": []any{
			map[string]any{
				"id":   "call_abc",
				"type": "function",
				"function": map[string]any{
					"name":      "search",
					"arguments": `{"query":"test"}`,
				},
			},
		},
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	am, ok := msg.(AssistantMessage)
	if !ok {
		t.Fatalf("expected AssistantMessage, got %T", msg)
	}
	if am.Content != nil {
		t.Errorf("content = %v, want nil", am.Content)
	}
	if len(am.ToolCalls) != 1 {
		t.Fatalf("len(tool_calls) = %d, want 1", len(am.ToolCalls))
	}
	if am.ToolCalls[0].Name != "search" {
		t.Errorf("tool name = %v, want search", am.ToolCalls[0].Name)
	}
}

func TestMessageFromDictTool(t *testing.T) {
	msg, err := MessageFromDict(map[string]any{
		"role": "tool", "tool_call_id": "call_1", "content": "42",
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	tm, ok := msg.(ToolResultMessage)
	if !ok {
		t.Fatalf("expected ToolResultMessage, got %T", msg)
	}
	if tm.ToolCallID != "call_1" {
		t.Errorf("tool_call_id = %v, want call_1", tm.ToolCallID)
	}
	if tm.Content != "42" {
		t.Errorf("content = %v, want '42'", tm.Content)
	}
}

func TestMessageFromDictUnknownRole(t *testing.T) {
	_, err := MessageFromDict(map[string]any{"role": "banana", "content": "x"})
	if err == nil {
		t.Fatal("expected error for unknown role, got nil")
	}
}

func TestMessagesFromDicts(t *testing.T) {
	ds := []map[string]any{
		{"role": "system", "content": "Be helpful."},
		{"role": "user", "content": "Hi"},
		{"role": "assistant", "content": "Hello!"},
	}
	msgs, err := MessagesFromDicts(ds)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(msgs) != 3 {
		t.Fatalf("len(msgs) = %d, want 3", len(msgs))
	}
	if msgs[0].Role() != "system" {
		t.Errorf("msgs[0].Role() = %v, want system", msgs[0].Role())
	}
	if msgs[1].Role() != "user" {
		t.Errorf("msgs[1].Role() = %v, want user", msgs[1].Role())
	}
	if msgs[2].Role() != "assistant" {
		t.Errorf("msgs[2].Role() = %v, want assistant", msgs[2].Role())
	}
}

func TestMessagesFromDictsError(t *testing.T) {
	ds := []map[string]any{
		{"role": "system", "content": "ok"},
		{"role": "unknown"},
	}
	_, err := MessagesFromDicts(ds)
	if err == nil {
		t.Fatal("expected error, got nil")
	}
}

func TestContentPartToOpenAIBase64(t *testing.T) {
	p := ContentPart{
		Type:      ContentPartImageBase64,
		MediaType: "image/png",
		Data:      "AAAA",
	}
	got := p.ToOpenAI()
	if got["type"] != "image_url" {
		t.Errorf("type = %v, want image_url", got["type"])
	}
	imgURL, ok := got["image_url"].(map[string]any)
	if !ok {
		t.Fatalf("image_url not map")
	}
	expected := "data:image/png;base64,AAAA"
	if imgURL["url"] != expected {
		t.Errorf("url = %v, want %v", imgURL["url"], expected)
	}
}

func TestContentPartToOpenAIBase64DefaultMediaType(t *testing.T) {
	p := ContentPart{Type: ContentPartImageBase64, Data: "BBBB"}
	got := p.ToOpenAI()
	imgURL := got["image_url"].(map[string]any)
	expected := "data:image/jpeg;base64,BBBB"
	if imgURL["url"] != expected {
		t.Errorf("url = %v, want %v", imgURL["url"], expected)
	}
}

func TestContentPartFromDictBase64DataURL(t *testing.T) {
	d := map[string]any{
		"type": "image_url",
		"image_url": map[string]any{
			"url": "data:image/png;base64,AAAA",
		},
	}
	got := contentPartFromDict(d)
	if got.Type != ContentPartImageBase64 {
		t.Errorf("type = %v, want image_base64", got.Type)
	}
	if got.MediaType != "image/png" {
		t.Errorf("media_type = %v, want image/png", got.MediaType)
	}
	if got.Data != "AAAA" {
		t.Errorf("data = %v, want AAAA", got.Data)
	}
}
