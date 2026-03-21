package memory

import "time"

// MemoryItem represents a single memory stored in Rook.
type MemoryItem struct {
	ID        string         `json:"id"`
	Memory    string         `json:"memory"`
	Hash      string         `json:"hash,omitempty"`
	Metadata  map[string]any `json:"metadata,omitempty"`
	Score     float32        `json:"score,omitempty"`
	CreatedAt *time.Time     `json:"created_at,omitempty"`
	UpdatedAt *time.Time     `json:"updated_at,omitempty"`
}

// MemoryType classifies memories.
type MemoryType string

const (
	MemoryTypeUser    MemoryType = "user"
	MemoryTypeProject MemoryType = "project"
)

// MemoryResult is returned from Add operations.
type MemoryResult struct {
	Results   []MemoryItem    `json:"results"`
	Relations []GraphRelation `json:"relations,omitempty"`
}

// GraphRelation represents a relationship from the graph store.
type GraphRelation struct {
	Source       string `json:"source"`
	Relationship string `json:"relationship"`
	Destination  string `json:"destination"`
}

// MemoryContext holds fetched context for prompt building.
type MemoryContext struct {
	UserMemories    []string
	ProjectMemories []string
	GraphRelations  []GraphRelation
}
