package llm

import (
	"testing"

	openai "github.com/sashabaranov/go-openai"
)

func TestMessagesToOpenAI(t *testing.T) {
	content := "Hello!"
	msgs := []Message{
		SystemMessage{Content: "You are Clara."},
		UserMessage{Content: "Hi there"},
		AssistantMessage{Content: &content, ToolCalls: nil},
		ToolResultMessage{ToolCallID: "call_1", Content: "result"},
	}

	got := messagesToOpenAI(msgs)

	if len(got) != 4 {
		t.Fatalf("expected 4 messages, got %d", len(got))
	}

	// System
	if got[0].Role != openai.ChatMessageRoleSystem {
		t.Errorf("msg[0] role = %q, want %q", got[0].Role, openai.ChatMessageRoleSystem)
	}
	if got[0].Content != "You are Clara." {
		t.Errorf("msg[0] content = %q, want %q", got[0].Content, "You are Clara.")
	}

	// User
	if got[1].Role != openai.ChatMessageRoleUser {
		t.Errorf("msg[1] role = %q, want %q", got[1].Role, openai.ChatMessageRoleUser)
	}
	if got[1].Content != "Hi there" {
		t.Errorf("msg[1] content = %q, want %q", got[1].Content, "Hi there")
	}

	// Assistant
	if got[2].Role != openai.ChatMessageRoleAssistant {
		t.Errorf("msg[2] role = %q, want %q", got[2].Role, openai.ChatMessageRoleAssistant)
	}
	if got[2].Content != "Hello!" {
		t.Errorf("msg[2] content = %q, want %q", got[2].Content, "Hello!")
	}

	// Tool result
	if got[3].Role != openai.ChatMessageRoleTool {
		t.Errorf("msg[3] role = %q, want %q", got[3].Role, openai.ChatMessageRoleTool)
	}
	if got[3].ToolCallID != "call_1" {
		t.Errorf("msg[3] tool_call_id = %q, want %q", got[3].ToolCallID, "call_1")
	}
	if got[3].Content != "result" {
		t.Errorf("msg[3] content = %q, want %q", got[3].Content, "result")
	}
}

func TestMessagesToOpenAI_Multimodal(t *testing.T) {
	msgs := []Message{
		UserMessage{
			Content: "Describe this",
			Parts: []ContentPart{
				{Type: ContentPartText, Text: "Describe this"},
				{Type: ContentPartImageURL, URL: "https://example.com/img.png"},
				{Type: ContentPartImageBase64, MediaType: "image/png", Data: "AAAA"},
			},
		},
	}

	got := messagesToOpenAI(msgs)
	if len(got) != 1 {
		t.Fatalf("expected 1 message, got %d", len(got))
	}

	if got[0].Content != "" {
		t.Errorf("multimodal message should have empty Content, got %q", got[0].Content)
	}
	if len(got[0].MultiContent) != 3 {
		t.Fatalf("expected 3 parts, got %d", len(got[0].MultiContent))
	}

	// Text part
	if got[0].MultiContent[0].Type != openai.ChatMessagePartTypeText {
		t.Errorf("part[0] type = %q, want text", got[0].MultiContent[0].Type)
	}
	if got[0].MultiContent[0].Text != "Describe this" {
		t.Errorf("part[0] text = %q, want %q", got[0].MultiContent[0].Text, "Describe this")
	}

	// Image URL part
	if got[0].MultiContent[1].Type != openai.ChatMessagePartTypeImageURL {
		t.Errorf("part[1] type = %q, want image_url", got[0].MultiContent[1].Type)
	}
	if got[0].MultiContent[1].ImageURL == nil || got[0].MultiContent[1].ImageURL.URL != "https://example.com/img.png" {
		t.Errorf("part[1] image URL mismatch")
	}

	// Base64 image part
	if got[0].MultiContent[2].Type != openai.ChatMessagePartTypeImageURL {
		t.Errorf("part[2] type = %q, want image_url", got[0].MultiContent[2].Type)
	}
	if got[0].MultiContent[2].ImageURL == nil || got[0].MultiContent[2].ImageURL.URL != "data:image/png;base64,AAAA" {
		t.Errorf("part[2] image URL = %q, want data URL", got[0].MultiContent[2].ImageURL.URL)
	}
}

func TestMessagesToOpenAI_AssistantWithToolCalls(t *testing.T) {
	msgs := []Message{
		AssistantMessage{
			Content: nil,
			ToolCalls: []ToolCall{
				{
					ID:        "call_abc",
					Name:      "get_weather",
					Arguments: map[string]any{"city": "Portland"},
				},
			},
		},
	}

	got := messagesToOpenAI(msgs)
	if len(got) != 1 {
		t.Fatalf("expected 1 message, got %d", len(got))
	}

	if got[0].Content != "" {
		t.Errorf("expected empty content for nil Content, got %q", got[0].Content)
	}
	if len(got[0].ToolCalls) != 1 {
		t.Fatalf("expected 1 tool call, got %d", len(got[0].ToolCalls))
	}

	tc := got[0].ToolCalls[0]
	if tc.ID != "call_abc" {
		t.Errorf("tool call ID = %q, want %q", tc.ID, "call_abc")
	}
	if tc.Function.Name != "get_weather" {
		t.Errorf("tool call name = %q, want %q", tc.Function.Name, "get_weather")
	}
	if tc.Function.Arguments != `{"city":"Portland"}` {
		t.Errorf("tool call arguments = %q, want %q", tc.Function.Arguments, `{"city":"Portland"}`)
	}
}

func TestToolSchemasToOpenAI(t *testing.T) {
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

	got := toolSchemasToOpenAI(schemas)

	if len(got) != 1 {
		t.Fatalf("expected 1 tool, got %d", len(got))
	}

	if got[0].Type != openai.ToolTypeFunction {
		t.Errorf("tool type = %q, want %q", got[0].Type, openai.ToolTypeFunction)
	}
	if got[0].Function == nil {
		t.Fatal("tool function is nil")
	}
	if got[0].Function.Name != "get_weather" {
		t.Errorf("function name = %q, want %q", got[0].Function.Name, "get_weather")
	}
	if got[0].Function.Description != "Get weather for a city" {
		t.Errorf("function description = %q, want %q", got[0].Function.Description, "Get weather for a city")
	}
	if got[0].Function.Parameters == nil {
		t.Error("function parameters should not be nil")
	}
}

func TestToolResponseFromOpenAI_WithContent(t *testing.T) {
	resp := openai.ChatCompletionResponse{
		Choices: []openai.ChatCompletionChoice{
			{
				Message: openai.ChatCompletionMessage{
					Role:    openai.ChatMessageRoleAssistant,
					Content: "The weather is sunny.",
				},
				FinishReason: openai.FinishReasonStop,
			},
		},
	}

	got := toolResponseFromOpenAI(resp)

	if got.Content == nil {
		t.Fatal("expected content to be non-nil")
	}
	if *got.Content != "The weather is sunny." {
		t.Errorf("content = %q, want %q", *got.Content, "The weather is sunny.")
	}
	if got.HasToolCalls() {
		t.Error("expected no tool calls")
	}
	if got.StopReason != "stop" {
		t.Errorf("stop reason = %q, want %q", got.StopReason, "stop")
	}
}

func TestToolResponseFromOpenAI_WithToolCalls(t *testing.T) {
	resp := openai.ChatCompletionResponse{
		Choices: []openai.ChatCompletionChoice{
			{
				Message: openai.ChatCompletionMessage{
					Role: openai.ChatMessageRoleAssistant,
					ToolCalls: []openai.ToolCall{
						{
							ID:   "call_123",
							Type: openai.ToolTypeFunction,
							Function: openai.FunctionCall{
								Name:      "get_weather",
								Arguments: `{"city":"Portland"}`,
							},
						},
					},
				},
				FinishReason: openai.FinishReasonToolCalls,
			},
		},
	}

	got := toolResponseFromOpenAI(resp)

	if got.Content != nil {
		t.Errorf("expected nil content, got %q", *got.Content)
	}
	if !got.HasToolCalls() {
		t.Fatal("expected tool calls")
	}
	if len(got.ToolCalls) != 1 {
		t.Fatalf("expected 1 tool call, got %d", len(got.ToolCalls))
	}

	tc := got.ToolCalls[0]
	if tc.ID != "call_123" {
		t.Errorf("tool call ID = %q, want %q", tc.ID, "call_123")
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
	if got.StopReason != "tool_calls" {
		t.Errorf("stop reason = %q, want %q", got.StopReason, "tool_calls")
	}
}

func TestToolResponseFromOpenAI_EmptyContent(t *testing.T) {
	resp := openai.ChatCompletionResponse{
		Choices: []openai.ChatCompletionChoice{
			{
				Message: openai.ChatCompletionMessage{
					Role:    openai.ChatMessageRoleAssistant,
					Content: "",
				},
				FinishReason: openai.FinishReasonStop,
			},
		},
	}

	got := toolResponseFromOpenAI(resp)

	// Empty string content should result in nil Content (no meaningful content).
	if got.Content != nil {
		t.Errorf("expected nil content for empty string, got %q", *got.Content)
	}
}

func TestNewOpenAIProvider_BaseURL(t *testing.T) {
	tests := []struct {
		name       string
		config     *LLMConfig
		wantURL    string
		wantName   string
		wantErr    bool
	}{
		{
			name: "openrouter",
			config: &LLMConfig{
				Provider: "openrouter",
				APIKey:   "test-key",
				BaseURL:  "https://openrouter.ai/api/v1",
			},
			wantURL:  "https://openrouter.ai/api/v1",
			wantName: "openrouter",
		},
		{
			name: "nanogpt",
			config: &LLMConfig{
				Provider: "nanogpt",
				APIKey:   "test-key",
				BaseURL:  "https://nano-gpt.com/api/v1",
			},
			wantURL:  "https://nano-gpt.com/api/v1",
			wantName: "nanogpt",
		},
		{
			name: "custom openai",
			config: &LLMConfig{
				Provider: "openai",
				APIKey:   "test-key",
				BaseURL:  "https://my-custom-endpoint.com/v1",
			},
			wantURL:  "https://my-custom-endpoint.com/v1",
			wantName: "openai",
		},
		{
			name: "default openai base URL",
			config: &LLMConfig{
				Provider: "openai",
				APIKey:   "test-key",
				BaseURL:  "",
			},
			wantURL:  "https://api.openai.com/v1",
			wantName: "openai",
		},
		{
			name:    "nil config",
			config:  nil,
			wantErr: true,
		},
		{
			name: "missing API key",
			config: &LLMConfig{
				Provider: "openai",
				APIKey:   "",
			},
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			provider, err := NewOpenAIProvider(tt.config)

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
			if provider.Name() != tt.wantName {
				t.Errorf("Name() = %q, want %q", provider.Name(), tt.wantName)
			}
		})
	}
}

func TestNewOpenAIProvider_ExtraHeaders(t *testing.T) {
	config := &LLMConfig{
		Provider: "openrouter",
		APIKey:   "test-key",
		BaseURL:  "https://openrouter.ai/api/v1",
		ExtraHeaders: map[string]string{
			"HTTP-Referer": "http://localhost:3000",
			"X-Title":      "MyPalClara",
		},
	}

	provider, err := NewOpenAIProvider(config)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if provider == nil {
		t.Fatal("provider is nil")
	}
	// We can't easily inspect the transport headers without making a request,
	// but we verify the provider was created without error.
	if provider.Name() != "openrouter" {
		t.Errorf("Name() = %q, want %q", provider.Name(), "openrouter")
	}
}

func TestOpenAIProvider_ImplementsProvider(t *testing.T) {
	// Compile-time check that OpenAIProvider implements Provider.
	var _ Provider = (*OpenAIProvider)(nil)
}
