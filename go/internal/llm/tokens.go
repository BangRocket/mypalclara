// Token counting utilities for prompt budget management.
package llm

import (
	"strings"
	"sync"

	tiktoken "github.com/pkoukk/tiktoken-go"
)

var (
	encoder     *tiktoken.Tiktoken
	encoderOnce sync.Once
)

// getEncoder lazily initializes the cl100k_base encoder (same as Python).
func getEncoder() *tiktoken.Tiktoken {
	encoderOnce.Do(func() {
		enc, err := tiktoken.GetEncoding("cl100k_base")
		if err != nil {
			panic("tiktoken: failed to load cl100k_base: " + err.Error())
		}
		encoder = enc
	})
	return encoder
}

// CountTokens returns the number of tokens in a text string.
// Returns 0 for empty input.
func CountTokens(text string) int {
	if text == "" {
		return 0
	}
	return len(getEncoder().Encode(text, nil, nil))
}

// CountMessageTokens counts tokens across a slice of Messages.
// Each message costs its content tokens plus 4 tokens of role overhead.
// Handles nil Content on AssistantMessage.
func CountMessageTokens(msgs []Message) int {
	total := 0
	for _, msg := range msgs {
		content := messageContent(msg)
		total += CountTokens(content) + 4
	}
	return total
}

// messageContent extracts the text content from any Message type.
func messageContent(msg Message) string {
	switch m := msg.(type) {
	case SystemMessage:
		return m.Content
	case UserMessage:
		return m.Content
	case AssistantMessage:
		if m.Content != nil {
			return *m.Content
		}
		return ""
	case ToolResultMessage:
		return m.Content
	default:
		return ""
	}
}

// contextWindows maps model family substrings to context window sizes.
// Order matters: more specific patterns must come first (e.g. "gpt-4o" before "gpt-4").
var contextWindows = []struct {
	pattern string
	size    int
}{
	{"claude", 200_000},
	{"gpt-4o", 128_000},
	{"gpt-4", 128_000},
}

const defaultContextWindow = 128_000

// GetContextWindow returns the context window size for a model.
// Uses case-insensitive substring matching against known model families.
func GetContextWindow(model string) int {
	lower := strings.ToLower(model)
	for _, cw := range contextWindows {
		if strings.Contains(lower, cw.pattern) {
			return cw.size
		}
	}
	return defaultContextWindow
}
