// Package llm — provider.go defines the Provider interface that all LLM backends implement.
package llm

import "context"

// Provider is the interface all LLM providers implement.
type Provider interface {
	// Complete sends messages and returns the text response.
	Complete(ctx context.Context, messages []Message, config *LLMConfig) (string, error)

	// CompleteWithTools sends messages with available tools and returns a structured response.
	CompleteWithTools(ctx context.Context, messages []Message, tools []ToolSchema, config *LLMConfig) (*ToolResponse, error)

	// Name returns the provider identifier (e.g. "openrouter", "openai", "nanogpt").
	Name() string
}
