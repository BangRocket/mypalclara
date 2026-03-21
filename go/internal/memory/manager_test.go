package memory

import (
	"context"
	"testing"

	"github.com/BangRocket/mypalclara/go/internal/llm"
	"github.com/BangRocket/mypalclara/go/internal/memory/dynamics"
	"github.com/BangRocket/mypalclara/go/internal/memory/embeddings"
	"github.com/BangRocket/mypalclara/go/internal/memory/vector"
)

// --- Mock implementations for manager tests ---

type mgrMockEmbedder struct{}

func (m *mgrMockEmbedder) Embed(_ context.Context, _ string) ([]float32, error) {
	return make([]float32, 8), nil
}
func (m *mgrMockEmbedder) Dims() int     { return 8 }
func (m *mgrMockEmbedder) Model() string { return "mock-model" }

type mgrMockVectorStore struct {
	upserted []string
	searched bool
}

func (m *mgrMockVectorStore) CreateCollection(_ context.Context, _ string, _ int) error { return nil }
func (m *mgrMockVectorStore) Upsert(_ context.Context, id string, _ []float32, _ map[string]any) error {
	m.upserted = append(m.upserted, id)
	return nil
}
func (m *mgrMockVectorStore) Search(_ context.Context, _ []float32, _ int, _ *vector.Filter) ([]vector.SearchResult, error) {
	m.searched = true
	return []vector.SearchResult{
		{ID: "mem-1", Score: 0.9, Payload: map[string]any{"memory": "test fact"}},
	}, nil
}
func (m *mgrMockVectorStore) Get(_ context.Context, id string) (*vector.SearchResult, error) {
	return &vector.SearchResult{ID: id, Payload: map[string]any{"memory": "test"}}, nil
}
func (m *mgrMockVectorStore) Delete(_ context.Context, _ string) error                         { return nil }
func (m *mgrMockVectorStore) Update(_ context.Context, _ string, _ []float32, _ map[string]any) error { return nil }
func (m *mgrMockVectorStore) List(_ context.Context, _ *vector.Filter, _ int) ([]vector.SearchResult, error) {
	return nil, nil
}

type mgrMockProvider struct {
	response string
}

func (m *mgrMockProvider) Complete(_ context.Context, _ []llm.Message, _ *llm.LLMConfig) (string, error) {
	if m.response != "" {
		return m.response, nil
	}
	return "User likes Go programming", nil
}
func (m *mgrMockProvider) CompleteWithTools(_ context.Context, _ []llm.Message, _ []llm.ToolSchema, _ *llm.LLMConfig) (*llm.ToolResponse, error) {
	return nil, nil
}
func (m *mgrMockProvider) Name() string { return "mock" }

// --- Helper to build a Manager with mocks ---

func newTestManager(t *testing.T) (*Manager, *mgrMockVectorStore, *mgrMockProvider) {
	t.Helper()

	vs := &mgrMockVectorStore{}
	emb := &mgrMockEmbedder{}
	prov := &mgrMockProvider{}
	cfg := &RookConfig{CollectionName: "test_memories"}

	rook := NewRook(vs, emb, prov, cfg)
	dyn := dynamics.NewDynamicsManager(nil) // nil db is fine for tests
	retriever := NewRetriever(rook, dyn)
	writer := NewWriter(rook)
	session := NewSessionManager(nil) // nil db — we won't call real db methods
	prompt := NewPromptBuilder("Clara")

	mgr := &Manager{
		rook:      rook,
		retriever: retriever,
		writer:    writer,
		session:   session,
		prompt:    prompt,
		dynamics:  dyn,
		config:    cfg,
	}
	return mgr, vs, prov
}

// --- Verify interfaces at compile time ---

var _ embeddings.Embedder = (*mgrMockEmbedder)(nil)
var _ vector.VectorStore = (*mgrMockVectorStore)(nil)
var _ llm.Provider = (*mgrMockProvider)(nil)

// --- Tests ---

func TestManagerInitializeWithMocks(t *testing.T) {
	mgr, _, _ := newTestManager(t)

	if mgr.rook == nil {
		t.Fatal("expected rook to be set")
	}
	if mgr.retriever == nil {
		t.Fatal("expected retriever to be set")
	}
	if mgr.writer == nil {
		t.Fatal("expected writer to be set")
	}
	if mgr.session == nil {
		t.Fatal("expected session to be set")
	}
	if mgr.prompt == nil {
		t.Fatal("expected prompt to be set")
	}
	if mgr.dynamics == nil {
		t.Fatal("expected dynamics to be set")
	}
	if mgr.config == nil {
		t.Fatal("expected config to be set")
	}
}

func TestManagerFetchContextDelegates(t *testing.T) {
	mgr, vs, _ := newTestManager(t)
	ctx := context.Background()

	memCtx, err := mgr.FetchContext(ctx, "user-1", "hello", FetchOptions{})
	if err != nil {
		t.Fatalf("FetchContext: %v", err)
	}
	if !vs.searched {
		t.Error("expected vector store Search to be called")
	}
	if memCtx == nil {
		t.Fatal("expected non-nil MemoryContext")
	}
	if len(memCtx.UserMemories) == 0 {
		t.Error("expected at least one user memory from mock")
	}
}

func TestManagerBuildPromptDelegates(t *testing.T) {
	mgr, _, _ := newTestManager(t)
	ctx := context.Background()

	memCtx := &MemoryContext{
		UserMemories:    []string{"likes Go"},
		ProjectMemories: []string{"project fact"},
	}

	messages := mgr.BuildPrompt(ctx, memCtx, PromptOptions{
		UserMemories:    memCtx.UserMemories,
		ProjectMemories: memCtx.ProjectMemories,
		UserMessage:     "Hello Clara",
		UserID:          "user-1",
	})

	if len(messages) == 0 {
		t.Fatal("expected non-empty messages from BuildPrompt")
	}

	// Should have at least: system (persona), system (context), user message.
	if len(messages) < 3 {
		t.Errorf("expected at least 3 messages, got %d", len(messages))
	}

	// Last message should be the user message.
	last := messages[len(messages)-1]
	if um, ok := last.(llm.UserMessage); !ok {
		t.Errorf("expected last message to be UserMessage, got %T", last)
	} else if um.Content != "Hello Clara" {
		t.Errorf("expected user message content 'Hello Clara', got %q", um.Content)
	}
}

func TestManagerAddFromConversationDelegates(t *testing.T) {
	mgr, vs, _ := newTestManager(t)
	ctx := context.Background()

	err := mgr.AddFromConversation(ctx, WriteOptions{
		UserID:         "user-1",
		UserMessage:    "I love Go",
		AssistantReply: "Go is great!",
		IsDM:           true,
	})
	if err != nil {
		t.Fatalf("AddFromConversation: %v", err)
	}
	if len(vs.upserted) == 0 {
		t.Error("expected at least one upsert from memory extraction")
	}
}

func TestManagerGracefulDegradation(t *testing.T) {
	// Manager with nil rook should return empty context, not error.
	mgr := &Manager{
		rook:      nil,
		retriever: nil,
		writer:    nil,
		session:   nil,
		prompt:    NewPromptBuilder("Clara"),
		dynamics:  nil,
		config:    &RookConfig{},
	}

	ctx := context.Background()

	// FetchContext with nil rook should return empty context.
	memCtx, err := mgr.FetchContext(ctx, "user-1", "hello", FetchOptions{})
	if err != nil {
		t.Fatalf("FetchContext with nil rook should not error: %v", err)
	}
	if memCtx == nil {
		t.Fatal("expected non-nil empty MemoryContext")
	}
	if len(memCtx.UserMemories) != 0 {
		t.Errorf("expected empty user memories, got %d", len(memCtx.UserMemories))
	}

	// AddFromConversation with nil writer should be a no-op.
	err = mgr.AddFromConversation(ctx, WriteOptions{
		UserID:      "user-1",
		UserMessage: "test",
	})
	if err != nil {
		t.Fatalf("AddFromConversation with nil writer should not error: %v", err)
	}

	// BuildPrompt should still work with empty context.
	messages := mgr.BuildPrompt(ctx, memCtx, PromptOptions{
		UserMessage: "Hello",
		UserID:      "user-1",
	})
	if len(messages) == 0 {
		t.Fatal("expected non-empty messages even with degraded manager")
	}
}

func TestManagerGetManagerSingleton(t *testing.T) {
	// Reset global state for test isolation.
	globalManager = nil

	// Before initialization, GetManager returns nil.
	if m := GetManager(); m != nil {
		t.Error("expected nil before initialization")
	}

	// Set a manager manually.
	mgr, _, _ := newTestManager(t)
	globalManager = mgr

	got := GetManager()
	if got != mgr {
		t.Error("expected GetManager to return the global manager")
	}

	// Clean up.
	globalManager = nil
}
