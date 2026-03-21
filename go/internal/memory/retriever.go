package memory

import (
	"context"
	"sync"

	"github.com/BangRocket/mypalclara/go/internal/memory/dynamics"
)

// Retriever fetches and ranks memories from Rook.
type Retriever struct {
	rook     *Rook
	dynamics *dynamics.DynamicsManager // can be nil
}

// NewRetriever creates a Retriever backed by the given Rook instance.
// dynamics may be nil to skip FSRS re-ranking.
func NewRetriever(rook *Rook, dyn *dynamics.DynamicsManager) *Retriever {
	return &Retriever{
		rook:     rook,
		dynamics: dyn,
	}
}

// FetchOptions configures what context to retrieve.
type FetchOptions struct {
	ProjectID    string
	Participants []string // Additional user IDs for cross-user context
	IsDM         bool
	PrivacyScope string // "full" or "public_only"
}

// FetchContext performs parallel searches for user memories, project memories,
// and key memories. Returns formatted strings ready for prompt injection.
func (r *Retriever) FetchContext(ctx context.Context, userID, query string, opts FetchOptions) (*MemoryContext, error) {
	type result struct {
		items []MemoryItem
		err   error
	}

	var (
		wg         sync.WaitGroup
		userRes    result
		projectRes result
		keyRes     result
	)

	// 1. Search user memories.
	wg.Add(1)
	go func() {
		defer wg.Done()
		items, err := r.rook.Search(ctx, query, SearchOptions{
			UserID: userID,
			Limit:  MaxMemoriesPerType,
		})
		userRes = result{items: items, err: err}
	}()

	// 2. Search project memories if ProjectID is set.
	if opts.ProjectID != "" {
		wg.Add(1)
		go func() {
			defer wg.Done()
			items, err := r.rook.Search(ctx, query, SearchOptions{
				Limit: MaxMemoriesPerType,
				Filters: map[string]any{
					"type":       string(MemoryTypeProject),
					"project_id": opts.ProjectID,
				},
			})
			projectRes = result{items: items, err: err}
		}()
	}

	// 3. Get key memories (always-included, high-importance memories).
	wg.Add(1)
	go func() {
		defer wg.Done()
		items, err := r.rook.GetAll(ctx, SearchOptions{
			UserID: userID,
			Limit:  MaxKeyMemories,
			Filters: map[string]any{
				"key_memory": true,
			},
		})
		keyRes = result{items: items, err: err}
	}()

	wg.Wait()

	// Check for errors — return the first encountered.
	if userRes.err != nil {
		return nil, userRes.err
	}
	if projectRes.err != nil {
		return nil, projectRes.err
	}
	if keyRes.err != nil {
		return nil, keyRes.err
	}

	// Merge and deduplicate by memory ID.
	allItems := make([]MemoryItem, 0, len(userRes.items)+len(projectRes.items)+len(keyRes.items))
	seen := make(map[string]bool)

	addUnique := func(items []MemoryItem) {
		for _, item := range items {
			if !seen[item.ID] {
				seen[item.ID] = true
				allItems = append(allItems, item)
			}
		}
	}

	// Key memories first (they're always included).
	addUnique(keyRes.items)
	addUnique(userRes.items)
	addUnique(projectRes.items)

	// Privacy filter: if scope="public_only", only keep public memories.
	if opts.PrivacyScope == "public_only" {
		filtered := make([]MemoryItem, 0, len(allItems))
		for _, item := range allItems {
			vis, _ := item.Metadata["visibility"].(string)
			if vis == "public" {
				filtered = append(filtered, item)
			}
		}
		allItems = filtered
	}

	// If dynamics manager is available, re-rank with FSRS scores.
	if r.dynamics != nil {
		for i := range allItems {
			score := r.dynamics.CalculateScore(allItems[i].ID, userID, float64(allItems[i].Score))
			allItems[i].Score = float32(score)
		}
		// Sort by descending score.
		sortMemoriesByScore(allItems)
	}

	// Build MemoryContext with formatted string lists.
	mc := &MemoryContext{
		UserMemories:    make([]string, 0),
		ProjectMemories: make([]string, 0),
	}

	for _, item := range allItems {
		memType, _ := item.Metadata["type"].(string)
		if memType == string(MemoryTypeProject) {
			mc.ProjectMemories = append(mc.ProjectMemories, item.Memory)
		} else {
			mc.UserMemories = append(mc.UserMemories, item.Memory)
		}
	}

	return mc, nil
}

// sortMemoriesByScore sorts memories by score descending (highest first).
func sortMemoriesByScore(items []MemoryItem) {
	// Simple insertion sort — memory slices are small (< 100 items).
	for i := 1; i < len(items); i++ {
		for j := i; j > 0 && items[j].Score > items[j-1].Score; j-- {
			items[j], items[j-1] = items[j-1], items[j]
		}
	}
}
