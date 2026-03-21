package memory

import (
	"context"
	"database/sql"
	"log"
	"sync"

	"github.com/BangRocket/mypalclara/go/internal/llm"
	"github.com/BangRocket/mypalclara/go/internal/memory/dynamics"
	"github.com/BangRocket/mypalclara/go/internal/memory/embeddings"
	"github.com/BangRocket/mypalclara/go/internal/memory/vector"
)

// Manager is the central facade for all memory operations.
// It ties together Rook (vector memory), session management,
// prompt building, and FSRS dynamics into a single entry point.
type Manager struct {
	rook      *Rook
	retriever *Retriever
	writer    *Writer
	session   *SessionManager
	prompt    *PromptBuilder
	dynamics  *dynamics.DynamicsManager
	config    *RookConfig

	mu sync.Mutex
}

var (
	globalManager *Manager
	managerMu     sync.Mutex
)

// Initialize creates and initializes the global MemoryManager.
//
// Steps:
//  1. Load config from env (RookConfigFromEnv)
//  2. Create embedder (NewOpenAIEmbedder)
//  3. Create vector store (NewQdrantStore or skip if unavailable)
//  4. Create Rook LLM provider (for memory extraction)
//  5. Create Rook instance
//  6. Create DynamicsManager (with db)
//  7. Create Retriever (with rook + dynamics)
//  8. Create Writer (with rook)
//  9. Create SessionManager (with db)
//  10. Create PromptBuilder
//  11. Store as singleton
//
// If Qdrant or embeddings are not available, the manager degrades
// gracefully — rook is nil, retriever returns empty context, and
// AddFromConversation is a no-op.
func Initialize(db *sql.DB, provider llm.Provider) (*Manager, error) {
	cfg := RookConfigFromEnv()

	var rook *Rook
	var retriever *Retriever
	var writer *Writer

	// Try to create embedder and vector store.
	// If either fails, degrade gracefully.
	emb, err := embeddings.NewOpenAIEmbedder(
		embeddings.WithModel(cfg.EmbeddingModel),
		embeddings.WithDims(cfg.EmbeddingDims),
		embeddings.WithAPIKey(cfg.OpenAIAPIKey),
	)
	if err != nil {
		log.Printf("memory: embedder unavailable, running without memory: %v", err)
	} else {
		// Try to connect to Qdrant.
		vs, vsErr := vector.NewQdrantStore(cfg.QdrantURL, cfg.QdrantAPIKey, cfg.CollectionName)
		if vsErr != nil {
			log.Printf("memory: Qdrant unavailable, running without memory: %v", vsErr)
		} else {
			rook = NewRook(vs, emb, provider, cfg)
		}
	}

	// Create dynamics manager (works with nil db).
	dyn := dynamics.NewDynamicsManager(db)

	// Create retriever and writer (nil-safe — checked in Manager methods).
	if rook != nil {
		retriever = NewRetriever(rook, dyn)
		writer = NewWriter(rook)
	}

	session := NewSessionManager(db)
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

	managerMu.Lock()
	globalManager = mgr
	managerMu.Unlock()

	if rook == nil {
		log.Println("memory: initialized in degraded mode (no vector memory)")
	} else {
		log.Println("memory: initialized successfully")
	}

	return mgr, nil
}

// GetManager returns the global MemoryManager instance.
// Returns nil if Initialize has not been called.
func GetManager() *Manager {
	managerMu.Lock()
	defer managerMu.Unlock()
	return globalManager
}

// FetchContext retrieves memory context for prompt building.
// If the retriever is nil (degraded mode), returns an empty MemoryContext.
func (m *Manager) FetchContext(ctx context.Context, userID, query string, opts FetchOptions) (*MemoryContext, error) {
	if m.retriever == nil {
		return &MemoryContext{
			UserMemories:    []string{},
			ProjectMemories: []string{},
		}, nil
	}
	return m.retriever.FetchContext(ctx, userID, query, opts)
}

// AddFromConversation stores memories from a conversation exchange.
// If the writer is nil (degraded mode), this is a no-op.
func (m *Manager) AddFromConversation(ctx context.Context, opts WriteOptions) error {
	if m.writer == nil {
		return nil
	}
	return m.writer.AddFromConversation(ctx, opts)
}

// BuildPrompt creates the full LLM prompt with persona, memories, and history.
func (m *Manager) BuildPrompt(ctx context.Context, memCtx *MemoryContext, opts PromptOptions) []llm.Message {
	// Merge MemoryContext into PromptOptions if not already populated.
	if memCtx != nil {
		if len(opts.UserMemories) == 0 {
			opts.UserMemories = memCtx.UserMemories
		}
		if len(opts.ProjectMemories) == 0 {
			opts.ProjectMemories = memCtx.ProjectMemories
		}
		if len(opts.GraphRelations) == 0 {
			opts.GraphRelations = memCtx.GraphRelations
		}
	}
	return m.prompt.BuildPrompt(opts)
}

// --- Session operations (delegated to SessionManager) ---

// GetOrCreateSession finds an active session or creates a new one.
func (m *Manager) GetOrCreateSession(ctx context.Context, userID, contextID, projectID string) (*Session, error) {
	return m.session.GetOrCreateSession(ctx, userID, contextID, projectID)
}

// GetRecentMessages returns the last N messages in a session.
func (m *Manager) GetRecentMessages(ctx context.Context, sessionID string, limit int) ([]SessionMessage, error) {
	return m.session.GetRecentMessages(ctx, sessionID, limit)
}

// StoreMessage persists a message to the database.
func (m *Manager) StoreMessage(ctx context.Context, sessionID, userID, role, content string) error {
	return m.session.StoreMessage(ctx, sessionID, userID, role, content)
}

// UpdateSummary sets the session summary.
func (m *Manager) UpdateSummary(ctx context.Context, sessionID, summary string) error {
	return m.session.UpdateSummary(ctx, sessionID, summary)
}

// Rook returns the underlying Rook instance (may be nil in degraded mode).
func (m *Manager) Rook() *Rook {
	return m.rook
}

// Dynamics returns the underlying DynamicsManager.
func (m *Manager) Dynamics() *dynamics.DynamicsManager {
	return m.dynamics
}

// Session returns the underlying SessionManager.
func (m *Manager) Session() *SessionManager {
	return m.session
}

// IsAvailable returns true if the memory system is fully operational
// (i.e., rook is not nil).
func (m *Manager) IsAvailable() bool {
	return m.rook != nil
}
