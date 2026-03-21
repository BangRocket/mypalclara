package llm

import "testing"

func TestCountTokens_NonEmpty(t *testing.T) {
	n := CountTokens("Hello, world!")
	if n <= 0 {
		t.Errorf("expected positive token count, got %d", n)
	}
}

func TestCountTokens_Empty(t *testing.T) {
	n := CountTokens("")
	if n != 0 {
		t.Errorf("expected 0 tokens for empty string, got %d", n)
	}
}

func TestCountMessageTokens(t *testing.T) {
	content := "Hello"
	msgs := []Message{
		SystemMessage{Content: "You are helpful."},
		UserMessage{Content: "Hi there"},
		AssistantMessage{Content: &content},
	}
	total := CountMessageTokens(msgs)

	// Each message adds content tokens + 4 overhead; total must exceed 3*4 = 12
	if total <= 12 {
		t.Errorf("expected total > 12 (3 msgs * 4 overhead), got %d", total)
	}
}

func TestCountMessageTokens_NilContent(t *testing.T) {
	msgs := []Message{
		AssistantMessage{Content: nil},
	}
	total := CountMessageTokens(msgs)
	// nil content = 0 content tokens + 4 overhead
	if total != 4 {
		t.Errorf("expected 4 for nil-content assistant message, got %d", total)
	}
}

func TestGetContextWindow(t *testing.T) {
	tests := []struct {
		model string
		want  int
	}{
		{"claude-sonnet-4-5", 200_000},
		{"Claude-3-Opus", 200_000},
		{"gpt-4o-mini", 128_000},
		{"GPT-4O", 128_000},
		{"gpt-4-turbo", 128_000},
		{"some-unknown-model", 128_000},
	}
	for _, tt := range tests {
		t.Run(tt.model, func(t *testing.T) {
			got := GetContextWindow(tt.model)
			if got != tt.want {
				t.Errorf("GetContextWindow(%q) = %d, want %d", tt.model, got, tt.want)
			}
		})
	}
}
