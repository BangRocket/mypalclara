package memory

import (
	"context"
	"fmt"
	"math/rand"
	"strings"
	"testing"

	"github.com/BangRocket/mypalclara/go/internal/llm"
	"github.com/BangRocket/mypalclara/go/internal/memory/vector"
)

// --- Mocks ---

// mockVectorStore is an in-memory VectorStore for testing.
type mockVectorStore struct {
	data map[string]vector.SearchResult
}

func newMockVectorStore() *mockVectorStore {
	return &mockVectorStore{data: make(map[string]vector.SearchResult)}
}

func (m *mockVectorStore) CreateCollection(_ context.Context, _ string, _ int) error {
	return nil
}

func (m *mockVectorStore) Upsert(_ context.Context, id string, vec []float32, payload map[string]any) error {
	m.data[id] = vector.SearchResult{ID: id, Vector: vec, Payload: payload, Score: 1.0}
	return nil
}

func (m *mockVectorStore) Search(_ context.Context, _ []float32, limit int, filter *vector.Filter) ([]vector.SearchResult, error) {
	results := make([]vector.SearchResult, 0)
	for _, res := range m.data {
		if filter != nil && filter.UserID != "" {
			uid, _ := res.Payload["user_id"].(string)
			if uid != filter.UserID {
				continue
			}
		}
		results = append(results, res)
		if len(results) >= limit {
			break
		}
	}
	return results, nil
}

func (m *mockVectorStore) Get(_ context.Context, id string) (*vector.SearchResult, error) {
	res, ok := m.data[id]
	if !ok {
		return nil, fmt.Errorf("not found: %s", id)
	}
	return &res, nil
}

func (m *mockVectorStore) Delete(_ context.Context, id string) error {
	delete(m.data, id)
	return nil
}

func (m *mockVectorStore) Update(_ context.Context, id string, vec []float32, payload map[string]any) error {
	if _, ok := m.data[id]; !ok {
		return fmt.Errorf("not found: %s", id)
	}
	m.data[id] = vector.SearchResult{ID: id, Vector: vec, Payload: payload, Score: 1.0}
	return nil
}

func (m *mockVectorStore) List(_ context.Context, filter *vector.Filter, limit int) ([]vector.SearchResult, error) {
	return m.Search(context.Background(), nil, limit, filter)
}

// mockEmbedder returns deterministic fixed-length vectors.
type mockEmbedder struct {
	dims int
}

func newMockEmbedder() *mockEmbedder {
	return &mockEmbedder{dims: 8}
}

func (m *mockEmbedder) Embed(_ context.Context, text string) ([]float32, error) {
	// Deterministic: seed from text length so same text => same vector.
	rng := rand.New(rand.NewSource(int64(len(text))))
	vec := make([]float32, m.dims)
	for i := range vec {
		vec[i] = rng.Float32()
	}
	return vec, nil
}

func (m *mockEmbedder) Dims() int     { return m.dims }
func (m *mockEmbedder) Model() string { return "mock-embedding" }

// mockProvider returns a canned LLM response.
type mockProvider struct {
	response string
}

func (m *mockProvider) Complete(_ context.Context, _ []llm.Message, _ *llm.LLMConfig) (string, error) {
	return m.response, nil
}

func (m *mockProvider) CompleteWithTools(_ context.Context, _ []llm.Message, _ []llm.ToolSchema, _ *llm.LLMConfig) (*llm.ToolResponse, error) {
	return nil, fmt.Errorf("not implemented")
}

func (m *mockProvider) Name() string { return "mock" }

// --- Tests ---

func TestRookAdd(t *testing.T) {
	vs := newMockVectorStore()
	emb := newMockEmbedder()
	provider := &mockProvider{
		response: "Joshua prefers Go over Python\nJoshua lives in the US\nJoshua uses Clara as an AI assistant",
	}

	rook := NewRook(vs, emb, provider, &RookConfig{CollectionName: "test_memories"})

	messages := []map[string]string{
		{"role": "user", "content": "Hi Clara, I really prefer Go over Python these days."},
		{"role": "assistant", "content": "That's great! Go is a wonderful language."},
		{"role": "user", "content": "I live in the US and use you as my AI assistant."},
	}

	result, err := rook.Add(context.Background(), messages, AddOptions{UserID: "user-1"})
	if err != nil {
		t.Fatalf("Add failed: %v", err)
	}

	if len(result.Results) != 3 {
		t.Fatalf("expected 3 results, got %d", len(result.Results))
	}

	// Verify items were stored in vector store.
	if len(vs.data) != 3 {
		t.Fatalf("expected 3 items in vector store, got %d", len(vs.data))
	}

	// Verify each item has correct metadata.
	for _, item := range result.Results {
		if item.UserID() != "user-1" {
			// Check via metadata since MemoryItem doesn't have UserID field directly.
			uid, _ := item.Metadata["user_id"].(string)
			if uid != "user-1" {
				t.Errorf("expected user_id 'user-1', got %q", uid)
			}
		}
		if item.Memory == "" {
			t.Error("expected non-empty memory text")
		}
		if item.Hash == "" {
			t.Error("expected non-empty hash")
		}
		if item.ID == "" {
			t.Error("expected non-empty ID")
		}
	}
}

func TestRookAddNone(t *testing.T) {
	vs := newMockVectorStore()
	emb := newMockEmbedder()
	provider := &mockProvider{response: "NONE"}

	rook := NewRook(vs, emb, provider, nil)

	result, err := rook.Add(context.Background(), []map[string]string{
		{"role": "user", "content": "Hello!"},
	}, AddOptions{UserID: "user-1"})
	if err != nil {
		t.Fatalf("Add failed: %v", err)
	}

	if len(result.Results) != 0 {
		t.Fatalf("expected 0 results for NONE response, got %d", len(result.Results))
	}
}

func TestRookSearch(t *testing.T) {
	vs := newMockVectorStore()
	emb := newMockEmbedder()
	provider := &mockProvider{}

	rook := NewRook(vs, emb, provider, nil)

	// Pre-populate the vector store with some items.
	vec1, _ := emb.Embed(context.Background(), "likes Go")
	vs.Upsert(context.Background(), "mem-1", vec1, map[string]any{
		"memory":  "Joshua likes Go",
		"hash":    hashContent("Joshua likes Go"),
		"user_id": "user-1",
	})

	vec2, _ := emb.Embed(context.Background(), "lives in US")
	vs.Upsert(context.Background(), "mem-2", vec2, map[string]any{
		"memory":  "Joshua lives in the US",
		"hash":    hashContent("Joshua lives in the US"),
		"user_id": "user-1",
	})

	vec3, _ := emb.Embed(context.Background(), "other user")
	vs.Upsert(context.Background(), "mem-3", vec3, map[string]any{
		"memory":  "Other user fact",
		"hash":    hashContent("Other user fact"),
		"user_id": "user-2",
	})

	// Search for user-1's memories.
	results, err := rook.Search(context.Background(), "Go programming", SearchOptions{
		UserID: "user-1",
		Limit:  10,
	})
	if err != nil {
		t.Fatalf("Search failed: %v", err)
	}

	if len(results) != 2 {
		t.Fatalf("expected 2 results for user-1, got %d", len(results))
	}

	// Verify memories are populated.
	for _, item := range results {
		if item.Memory == "" {
			t.Error("expected non-empty memory text")
		}
	}
}

func TestRookGet(t *testing.T) {
	vs := newMockVectorStore()
	emb := newMockEmbedder()
	provider := &mockProvider{}

	rook := NewRook(vs, emb, provider, nil)

	// Store an item.
	vec, _ := emb.Embed(context.Background(), "test fact")
	vs.Upsert(context.Background(), "mem-42", vec, map[string]any{
		"memory": "Joshua's favorite number is 42",
		"hash":   hashContent("Joshua's favorite number is 42"),
	})

	// Get it back.
	item, err := rook.Get(context.Background(), "mem-42")
	if err != nil {
		t.Fatalf("Get failed: %v", err)
	}
	if item == nil {
		t.Fatal("expected non-nil item")
	}
	if item.ID != "mem-42" {
		t.Errorf("expected ID 'mem-42', got %q", item.ID)
	}
	if item.Memory != "Joshua's favorite number is 42" {
		t.Errorf("unexpected memory: %q", item.Memory)
	}

	// Get non-existent.
	_, err = rook.Get(context.Background(), "non-existent")
	if err == nil {
		t.Error("expected error for non-existent memory")
	}
}

func TestRookDelete(t *testing.T) {
	vs := newMockVectorStore()
	emb := newMockEmbedder()
	provider := &mockProvider{}

	rook := NewRook(vs, emb, provider, nil)

	// Store an item.
	vec, _ := emb.Embed(context.Background(), "to delete")
	vs.Upsert(context.Background(), "mem-del", vec, map[string]any{
		"memory": "This should be deleted",
	})

	// Verify it exists.
	if _, ok := vs.data["mem-del"]; !ok {
		t.Fatal("expected item to exist before delete")
	}

	// Delete it.
	err := rook.Delete(context.Background(), "mem-del")
	if err != nil {
		t.Fatalf("Delete failed: %v", err)
	}

	// Verify it's gone.
	if _, ok := vs.data["mem-del"]; ok {
		t.Error("expected item to be deleted")
	}
}

func TestRookUpdate(t *testing.T) {
	vs := newMockVectorStore()
	emb := newMockEmbedder()
	provider := &mockProvider{}

	rook := NewRook(vs, emb, provider, nil)

	// Store an item.
	vec, _ := emb.Embed(context.Background(), "old fact")
	vs.Upsert(context.Background(), "mem-upd", vec, map[string]any{
		"memory":  "Old content",
		"user_id": "user-1",
	})

	// Update it.
	err := rook.Update(context.Background(), "mem-upd", "New content", AddOptions{UserID: "user-1"})
	if err != nil {
		t.Fatalf("Update failed: %v", err)
	}

	// Verify the update.
	res, _ := vs.Get(context.Background(), "mem-upd")
	if res == nil {
		t.Fatal("expected item to still exist after update")
	}
	mem, _ := res.Payload["memory"].(string)
	if mem != "New content" {
		t.Errorf("expected updated memory 'New content', got %q", mem)
	}
}

func TestParseFacts(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		expected int
	}{
		{"simple lines", "Fact one\nFact two\nFact three", 3},
		{"with bullets", "- Fact one\n- Fact two", 2},
		{"with numbers", "1. Fact one\n2. Fact two", 2},
		{"with NONE", "NONE", 0},
		{"with blanks", "Fact one\n\n\nFact two\n", 2},
		{"mixed markers", "- Fact one\n* Fact two\n3) Fact three", 3},
		{"empty", "", 0},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			facts := parseFacts(tt.input)
			if len(facts) != tt.expected {
				t.Errorf("expected %d facts, got %d: %v", tt.expected, len(facts), facts)
			}
			// Verify no markers remain.
			for _, f := range facts {
				if strings.HasPrefix(f, "- ") || strings.HasPrefix(f, "* ") {
					t.Errorf("fact still has list marker: %q", f)
				}
			}
		})
	}
}

// UserID is a helper for tests to extract user_id from metadata.
func (m MemoryItem) UserID() string {
	uid, _ := m.Metadata["user_id"].(string)
	return uid
}
