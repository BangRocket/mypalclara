package embeddings

import (
	"testing"
)

func TestOpenAIEmbedderDefaults(t *testing.T) {
	e, err := NewOpenAIEmbedder(WithAPIKey("test-key"))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got := e.Model(); got != "text-embedding-3-small" {
		t.Errorf("Model() = %q, want %q", got, "text-embedding-3-small")
	}
	if got := e.Dims(); got != 1536 {
		t.Errorf("Dims() = %d, want %d", got, 1536)
	}
}

func TestOpenAIEmbedderOptions(t *testing.T) {
	e, err := NewOpenAIEmbedder(
		WithAPIKey("test-key"),
		WithModel("text-embedding-3-large"),
		WithDims(3072),
		WithBaseURL("https://custom.example.com/v1"),
	)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got := e.Model(); got != "text-embedding-3-large" {
		t.Errorf("Model() = %q, want %q", got, "text-embedding-3-large")
	}
	if got := e.Dims(); got != 3072 {
		t.Errorf("Dims() = %d, want %d", got, 3072)
	}
}

func TestOpenAIEmbedderMissingKey(t *testing.T) {
	// Ensure env var is not set for this test.
	t.Setenv("OPENAI_API_KEY", "")

	_, err := NewOpenAIEmbedder()
	if err == nil {
		t.Fatal("expected error when no API key provided, got nil")
	}
}

func TestEmbedderInterface(t *testing.T) {
	e, err := NewOpenAIEmbedder(WithAPIKey("test-key"))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	// Compile-time interface check.
	var _ Embedder = e
}
