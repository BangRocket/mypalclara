// Package embeddings provides text embedding generation for the Rook memory system.
package embeddings

import "context"

// Embedder generates embeddings for text.
type Embedder interface {
	Embed(ctx context.Context, text string) ([]float32, error)
	Dims() int
	Model() string
}
