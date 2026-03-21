// Package vector defines the VectorStore interface for similarity search
// backends and provides a Qdrant implementation.
package vector

import "context"

// SearchResult represents a single result from a vector similarity search.
type SearchResult struct {
	ID      string
	Score   float32
	Payload map[string]any
	Vector  []float32
}

// Filter specifies conditions for filtering vector search results.
type Filter struct {
	UserID  string
	AgentID string
	Filters map[string]any
}

// VectorStore is the interface for vector similarity search backends.
type VectorStore interface {
	// CreateCollection creates a new collection with the given vector size.
	CreateCollection(ctx context.Context, name string, vectorSize int) error

	// Upsert inserts or updates a vector with the given ID and payload.
	Upsert(ctx context.Context, id string, vector []float32, payload map[string]any) error

	// Search finds the closest vectors to the query vector, limited by count
	// and optionally filtered. Results are sorted by score descending.
	Search(ctx context.Context, vector []float32, limit int, filter *Filter) ([]SearchResult, error)

	// Get retrieves a single vector by ID.
	Get(ctx context.Context, id string) (*SearchResult, error)

	// Delete removes a vector by ID.
	Delete(ctx context.Context, id string) error

	// Update replaces the vector and payload for an existing ID.
	Update(ctx context.Context, id string, vector []float32, payload map[string]any) error

	// List returns vectors matching the filter, up to limit.
	List(ctx context.Context, filter *Filter, limit int) ([]SearchResult, error)
}
