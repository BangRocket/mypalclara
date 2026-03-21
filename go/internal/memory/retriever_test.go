package memory

import (
	"context"
	"sync/atomic"
	"testing"
	"time"

	"github.com/BangRocket/mypalclara/go/internal/memory/vector"
)

// populateStore is a test helper that seeds the mock vector store with memories.
func populateStore(t *testing.T, vs *mockVectorStore, emb *mockEmbedder, items []struct {
	id      string
	memory  string
	userID  string
	meta    map[string]any
}) {
	t.Helper()
	for _, item := range items {
		vec, err := emb.Embed(context.Background(), item.memory)
		if err != nil {
			t.Fatalf("embed failed: %v", err)
		}
		payload := map[string]any{
			"memory":  item.memory,
			"hash":    hashContent(item.memory),
			"user_id": item.userID,
		}
		for k, v := range item.meta {
			payload[k] = v
		}
		if err := vs.Upsert(context.Background(), item.id, vec, payload); err != nil {
			t.Fatalf("upsert failed: %v", err)
		}
	}
}

func TestFetchContextBasic(t *testing.T) {
	vs := newMockVectorStore()
	emb := newMockEmbedder()
	provider := &mockProvider{}
	rook := NewRook(vs, emb, provider, nil)
	retriever := NewRetriever(rook, nil)

	// Seed some user memories.
	populateStore(t, vs, emb, []struct {
		id     string
		memory string
		userID string
		meta   map[string]any
	}{
		{"mem-1", "Joshua likes Go", "user-1", nil},
		{"mem-2", "Joshua lives in the US", "user-1", nil},
		{"mem-3", "Other user fact", "user-2", nil},
	})

	mc, err := retriever.FetchContext(context.Background(), "user-1", "Go programming", FetchOptions{
		PrivacyScope: "full",
	})
	if err != nil {
		t.Fatalf("FetchContext failed: %v", err)
	}

	// Should get user-1's memories only.
	if len(mc.UserMemories) != 2 {
		t.Errorf("expected 2 user memories, got %d: %v", len(mc.UserMemories), mc.UserMemories)
	}

	// Verify the memories contain expected text.
	found := map[string]bool{}
	for _, m := range mc.UserMemories {
		found[m] = true
	}
	if !found["Joshua likes Go"] {
		t.Error("expected 'Joshua likes Go' in user memories")
	}
	if !found["Joshua lives in the US"] {
		t.Error("expected 'Joshua lives in the US' in user memories")
	}
}

func TestFetchContextParallel(t *testing.T) {
	// Use a tracking vector store that records call times to verify concurrency.
	vs := &trackingVectorStore{
		mockVectorStore: newMockVectorStore(),
	}
	emb := newMockEmbedder()
	provider := &mockProvider{}
	rook := NewRook(vs, emb, provider, nil)
	retriever := NewRetriever(rook, nil)

	// Seed a user memory.
	vec, _ := emb.Embed(context.Background(), "test fact")
	vs.Upsert(context.Background(), "mem-1", vec, map[string]any{
		"memory":  "test fact",
		"user_id": "user-1",
	})

	mc, err := retriever.FetchContext(context.Background(), "user-1", "test", FetchOptions{
		PrivacyScope: "full",
	})
	if err != nil {
		t.Fatalf("FetchContext failed: %v", err)
	}

	// At minimum, 2 goroutines should have run (user search + key memories).
	if vs.searchCount.Load() < 2 {
		t.Errorf("expected at least 2 search/list calls for parallel execution, got %d", vs.searchCount.Load())
	}

	// Sanity: result should not be nil.
	if mc == nil {
		t.Fatal("expected non-nil MemoryContext")
	}
}

func TestFetchContextEmpty(t *testing.T) {
	vs := newMockVectorStore()
	emb := newMockEmbedder()
	provider := &mockProvider{}
	rook := NewRook(vs, emb, provider, nil)
	retriever := NewRetriever(rook, nil)

	mc, err := retriever.FetchContext(context.Background(), "user-1", "anything", FetchOptions{
		PrivacyScope: "full",
	})
	if err != nil {
		t.Fatalf("FetchContext failed: %v", err)
	}

	if len(mc.UserMemories) != 0 {
		t.Errorf("expected 0 user memories, got %d", len(mc.UserMemories))
	}
	if len(mc.ProjectMemories) != 0 {
		t.Errorf("expected 0 project memories, got %d", len(mc.ProjectMemories))
	}
}

func TestFetchContextPrivacy(t *testing.T) {
	vs := newMockVectorStore()
	emb := newMockEmbedder()
	provider := &mockProvider{}
	rook := NewRook(vs, emb, provider, nil)
	retriever := NewRetriever(rook, nil)

	// Seed memories with different visibility.
	populateStore(t, vs, emb, []struct {
		id     string
		memory string
		userID string
		meta   map[string]any
	}{
		{"mem-pub", "Public fact", "user-1", map[string]any{"visibility": "public"}},
		{"mem-priv", "Private fact", "user-1", map[string]any{"visibility": "private"}},
		{"mem-none", "No visibility set", "user-1", nil},
	})

	// Fetch with public_only scope.
	mc, err := retriever.FetchContext(context.Background(), "user-1", "facts", FetchOptions{
		PrivacyScope: "public_only",
	})
	if err != nil {
		t.Fatalf("FetchContext failed: %v", err)
	}

	if len(mc.UserMemories) != 1 {
		t.Errorf("expected 1 public memory, got %d: %v", len(mc.UserMemories), mc.UserMemories)
	}
	if len(mc.UserMemories) == 1 && mc.UserMemories[0] != "Public fact" {
		t.Errorf("expected 'Public fact', got %q", mc.UserMemories[0])
	}

	// Fetch with full scope — should get all.
	mc2, err := retriever.FetchContext(context.Background(), "user-1", "facts", FetchOptions{
		PrivacyScope: "full",
	})
	if err != nil {
		t.Fatalf("FetchContext (full) failed: %v", err)
	}

	if len(mc2.UserMemories) != 3 {
		t.Errorf("expected 3 memories with full scope, got %d: %v", len(mc2.UserMemories), mc2.UserMemories)
	}
}

// trackingVectorStore wraps mockVectorStore to count search/list calls.
type trackingVectorStore struct {
	*mockVectorStore
	searchCount atomic.Int64
}

func (t *trackingVectorStore) Search(ctx context.Context, vec []float32, limit int, filter *vector.Filter) ([]vector.SearchResult, error) {
	t.searchCount.Add(1)
	// Small sleep to make concurrency observable.
	time.Sleep(time.Millisecond)
	return t.mockVectorStore.Search(ctx, vec, limit, filter)
}

func (t *trackingVectorStore) List(ctx context.Context, filter *vector.Filter, limit int) ([]vector.SearchResult, error) {
	t.searchCount.Add(1)
	time.Sleep(time.Millisecond)
	return t.mockVectorStore.List(ctx, filter, limit)
}
