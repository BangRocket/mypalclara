package memory

import (
	"context"
	"crypto/sha256"
	"fmt"
	"strings"
	"time"

	"github.com/BangRocket/mypalclara/go/internal/llm"
	"github.com/BangRocket/mypalclara/go/internal/memory/embeddings"
	"github.com/BangRocket/mypalclara/go/internal/memory/vector"
	"github.com/google/uuid"
)

// extractionPrompt is the system prompt used to extract facts from conversations.
const extractionPrompt = `Extract key facts, preferences, and information from this conversation.
Return one fact per line. Only include concrete, specific information.
Do not include greetings or pleasantries.
If there are no facts to extract, return "NONE".`

// Rook is the core memory system (Clara's memory).
// It coordinates vector storage, embeddings, and LLM-based memory extraction.
type Rook struct {
	vectorStore vector.VectorStore
	embedder    embeddings.Embedder
	provider    llm.Provider // For memory extraction
	config      *RookConfig
	collection  string
}

// AddOptions configures an Add operation.
type AddOptions struct {
	UserID   string
	AgentID  string
	Metadata map[string]any
}

// SearchOptions configures a Search or GetAll operation.
type SearchOptions struct {
	UserID  string
	AgentID string
	Limit   int // default 10
	Filters map[string]any
}

// NewRook creates a new Rook memory system.
func NewRook(vs vector.VectorStore, emb embeddings.Embedder, provider llm.Provider, config *RookConfig) *Rook {
	collection := "clara_memories"
	if config != nil && config.CollectionName != "" {
		collection = config.CollectionName
	}
	return &Rook{
		vectorStore: vs,
		embedder:    emb,
		provider:    provider,
		config:      config,
		collection:  collection,
	}
}

// Add extracts memories from messages and stores them.
// Messages should be in the format: [{"role": "user", "content": "..."}, ...].
func (r *Rook) Add(ctx context.Context, messages []map[string]string, opts AddOptions) (*MemoryResult, error) {
	// Format messages into conversation text for the LLM.
	var sb strings.Builder
	for _, msg := range messages {
		role := msg["role"]
		content := msg["content"]
		sb.WriteString(fmt.Sprintf("%s: %s\n", role, content))
	}
	conversationText := sb.String()

	// Call LLM to extract facts.
	llmMessages := []llm.Message{
		llm.SystemMessage{Content: extractionPrompt},
		llm.UserMessage{Content: fmt.Sprintf("Conversation:\n%s\nFacts:", conversationText)},
	}

	response, err := r.provider.Complete(ctx, llmMessages, &llm.LLMConfig{
		MaxTokens:   1024,
		Temperature: 0.0,
	})
	if err != nil {
		return nil, fmt.Errorf("rook: LLM extraction failed: %w", err)
	}

	// Parse extracted facts (one per line).
	facts := parseFacts(response)
	if len(facts) == 0 {
		return &MemoryResult{Results: []MemoryItem{}}, nil
	}

	// For each fact: embed, create MemoryItem, upsert to vector store.
	now := time.Now().UTC()
	items := make([]MemoryItem, 0, len(facts))

	for _, fact := range facts {
		vec, err := r.embedder.Embed(ctx, fact)
		if err != nil {
			return nil, fmt.Errorf("rook: embedding failed for fact %q: %w", fact, err)
		}

		id := uuid.New().String()
		hash := hashContent(fact)

		payload := map[string]any{
			"memory":     fact,
			"hash":       hash,
			"created_at": now.Format(time.RFC3339),
			"updated_at": now.Format(time.RFC3339),
		}
		if opts.UserID != "" {
			payload["user_id"] = opts.UserID
		}
		if opts.AgentID != "" {
			payload["agent_id"] = opts.AgentID
		}
		// Merge caller-supplied metadata.
		for k, v := range opts.Metadata {
			payload[k] = v
		}

		if err := r.vectorStore.Upsert(ctx, id, vec, payload); err != nil {
			return nil, fmt.Errorf("rook: upsert failed for memory %s: %w", id, err)
		}

		item := MemoryItem{
			ID:        id,
			Memory:    fact,
			Hash:      hash,
			Metadata:  payload,
			CreatedAt: &now,
			UpdatedAt: &now,
		}
		items = append(items, item)
	}

	return &MemoryResult{Results: items}, nil
}

// Search finds memories matching a query.
func (r *Rook) Search(ctx context.Context, query string, opts SearchOptions) ([]MemoryItem, error) {
	limit := opts.Limit
	if limit <= 0 {
		limit = 10
	}

	// Truncate query to avoid embedding overly long text.
	q := query
	if len(q) > MaxSearchQueryChars {
		q = q[:MaxSearchQueryChars]
	}

	vec, err := r.embedder.Embed(ctx, q)
	if err != nil {
		return nil, fmt.Errorf("rook: embedding query failed: %w", err)
	}

	filter := &vector.Filter{
		UserID:  opts.UserID,
		AgentID: opts.AgentID,
		Filters: opts.Filters,
	}

	results, err := r.vectorStore.Search(ctx, vec, limit, filter)
	if err != nil {
		return nil, fmt.Errorf("rook: vector search failed: %w", err)
	}

	items := make([]MemoryItem, 0, len(results))
	for _, res := range results {
		items = append(items, searchResultToMemoryItem(res))
	}
	return items, nil
}

// Get retrieves a single memory by ID.
func (r *Rook) Get(ctx context.Context, memoryID string) (*MemoryItem, error) {
	res, err := r.vectorStore.Get(ctx, memoryID)
	if err != nil {
		return nil, fmt.Errorf("rook: get memory %s failed: %w", memoryID, err)
	}
	if res == nil {
		return nil, nil
	}
	item := searchResultToMemoryItem(*res)
	return &item, nil
}

// GetAll retrieves all memories matching the given options.
func (r *Rook) GetAll(ctx context.Context, opts SearchOptions) ([]MemoryItem, error) {
	limit := opts.Limit
	if limit <= 0 {
		limit = 100
	}

	filter := &vector.Filter{
		UserID:  opts.UserID,
		AgentID: opts.AgentID,
		Filters: opts.Filters,
	}

	results, err := r.vectorStore.List(ctx, filter, limit)
	if err != nil {
		return nil, fmt.Errorf("rook: list memories failed: %w", err)
	}

	items := make([]MemoryItem, 0, len(results))
	for _, res := range results {
		items = append(items, searchResultToMemoryItem(res))
	}
	return items, nil
}

// Delete removes a memory by ID.
func (r *Rook) Delete(ctx context.Context, memoryID string) error {
	if err := r.vectorStore.Delete(ctx, memoryID); err != nil {
		return fmt.Errorf("rook: delete memory %s failed: %w", memoryID, err)
	}
	return nil
}

// Update updates a memory's content, re-embedding and replacing in the vector store.
func (r *Rook) Update(ctx context.Context, memoryID string, content string, opts AddOptions) error {
	vec, err := r.embedder.Embed(ctx, content)
	if err != nil {
		return fmt.Errorf("rook: embedding update content failed: %w", err)
	}

	now := time.Now().UTC()
	hash := hashContent(content)

	payload := map[string]any{
		"memory":     content,
		"hash":       hash,
		"updated_at": now.Format(time.RFC3339),
	}
	if opts.UserID != "" {
		payload["user_id"] = opts.UserID
	}
	if opts.AgentID != "" {
		payload["agent_id"] = opts.AgentID
	}
	for k, v := range opts.Metadata {
		payload[k] = v
	}

	if err := r.vectorStore.Update(ctx, memoryID, vec, payload); err != nil {
		return fmt.Errorf("rook: update memory %s failed: %w", memoryID, err)
	}
	return nil
}

// parseFacts splits LLM output into individual facts, filtering blanks and "NONE".
func parseFacts(response string) []string {
	lines := strings.Split(strings.TrimSpace(response), "\n")
	facts := make([]string, 0, len(lines))
	for _, line := range lines {
		line = strings.TrimSpace(line)
		// Strip leading list markers like "- ", "* ", "1. ", "2) "
		line = stripListMarker(line)
		if line == "" || strings.EqualFold(line, "NONE") {
			continue
		}
		facts = append(facts, line)
	}
	return facts
}

// stripListMarker removes common list prefixes from a line.
func stripListMarker(s string) string {
	s = strings.TrimSpace(s)
	// Bullet markers: "- " or "* "
	if len(s) >= 2 && (s[0] == '-' || s[0] == '*') && s[1] == ' ' {
		return strings.TrimSpace(s[2:])
	}
	// Numbered markers: "1. " or "1) "
	i := 0
	for i < len(s) && s[i] >= '0' && s[i] <= '9' {
		i++
	}
	if i > 0 && i < len(s) && (s[i] == '.' || s[i] == ')') {
		rest := s[i+1:]
		if len(rest) > 0 && rest[0] == ' ' {
			return strings.TrimSpace(rest[1:])
		}
	}
	return s
}

// hashContent returns a hex-encoded SHA-256 hash of the content.
func hashContent(content string) string {
	h := sha256.Sum256([]byte(content))
	return fmt.Sprintf("%x", h)
}

// searchResultToMemoryItem converts a vector.SearchResult to a MemoryItem.
func searchResultToMemoryItem(res vector.SearchResult) MemoryItem {
	item := MemoryItem{
		ID:       res.ID,
		Score:    res.Score,
		Metadata: res.Payload,
	}
	if mem, ok := res.Payload["memory"].(string); ok {
		item.Memory = mem
	}
	if h, ok := res.Payload["hash"].(string); ok {
		item.Hash = h
	}
	if ts, ok := res.Payload["created_at"].(string); ok {
		if t, err := time.Parse(time.RFC3339, ts); err == nil {
			item.CreatedAt = &t
		}
	}
	if ts, ok := res.Payload["updated_at"].(string); ok {
		if t, err := time.Parse(time.RFC3339, ts); err == nil {
			item.UpdatedAt = &t
		}
	}
	return item
}
