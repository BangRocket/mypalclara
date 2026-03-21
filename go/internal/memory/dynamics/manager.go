package dynamics

import (
	"database/sql"
	"encoding/json"
	"time"
)

// DynamicsManager blends semantic similarity with FSRS-6 retrievability
// to produce a unified memory relevance score.
type DynamicsManager struct {
	db        *sql.DB
	params    *FsrsParams
	semWeight float64 // Weight for semantic similarity (default 0.6)
	dynWeight float64 // Weight for FSRS dynamics (default 0.4)
}

// NewDynamicsManager creates a DynamicsManager with default weights.
func NewDynamicsManager(db *sql.DB) *DynamicsManager {
	params := DefaultParams()
	return &DynamicsManager{
		db:        db,
		params:    &params,
		semWeight: 0.6,
		dynWeight: 0.4,
	}
}

// CalculateScore blends semantic similarity with FSRS retrievability.
// Returns semWeight*semanticScore + dynWeight*retrievability.
// If no FSRS state exists for the memory, retrievability defaults to 0.5.
func (m *DynamicsManager) CalculateScore(memoryID, userID string, semanticScore float64) float64 {
	state := m.loadState(memoryID, userID)
	now := time.Now()

	var r float64
	if state == nil || state.ReviewCount == 0 {
		r = 0.5 // default retrievability for unseen memories
	} else {
		r = Retrievability(state, now, m.params)
	}

	return m.semWeight*semanticScore + m.dynWeight*r
}

// Promote records a successful retrieval (the memory was useful).
func (m *DynamicsManager) Promote(memoryID, userID string, grade Grade) error {
	state := m.loadOrCreateState(memoryID, userID)
	now := time.Now()
	newState := Review(state, grade, m.params, now)
	return m.saveState(memoryID, userID, newState)
}

// Demote records a failed retrieval (the memory was not useful or wrong).
func (m *DynamicsManager) Demote(memoryID, userID string, reason string) error {
	state := m.loadOrCreateState(memoryID, userID)
	now := time.Now()
	newState := Review(state, GradeAgain, m.params, now)
	return m.saveState(memoryID, userID, newState)
}

// loadState retrieves the FSRS state for a memory+user pair.
// Returns nil if no state exists or db is nil.
func (m *DynamicsManager) loadState(memoryID, userID string) *MemoryState {
	if m.db == nil {
		return nil
	}

	var stateJSON string
	err := m.db.QueryRow(
		`SELECT state_json FROM memory_dynamics WHERE memory_id = ? AND user_id = ?`,
		memoryID, userID,
	).Scan(&stateJSON)
	if err != nil {
		return nil
	}

	var state MemoryState
	if err := json.Unmarshal([]byte(stateJSON), &state); err != nil {
		return nil
	}
	return &state
}

// loadOrCreateState returns an existing state or a new default state.
func (m *DynamicsManager) loadOrCreateState(memoryID, userID string) *MemoryState {
	if state := m.loadState(memoryID, userID); state != nil {
		return state
	}
	return &MemoryState{}
}

// saveState persists the FSRS state for a memory+user pair.
func (m *DynamicsManager) saveState(memoryID, userID string, state *MemoryState) error {
	if m.db == nil {
		return nil
	}

	data, err := json.Marshal(state)
	if err != nil {
		return err
	}

	_, err = m.db.Exec(
		`INSERT OR REPLACE INTO memory_dynamics (memory_id, user_id, state_json, updated_at)
		 VALUES (?, ?, ?, ?)`,
		memoryID, userID, string(data), time.Now().UTC(),
	)
	return err
}
