// Package memory provides Clara's memory and session management.
package memory

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	"github.com/BangRocket/mypalclara/go/internal/db"
	"github.com/google/uuid"
)

// summaryThreshold is the number of messages since the last summary
// update before ShouldUpdateSummary returns true.
const summaryThreshold = 10

// Session is the domain-level session representation exposed to callers.
type Session struct {
	ID             string
	ProjectID      string
	UserID         string
	ContextID      string
	Title          string
	SessionSummary string
	LastActivityAt time.Time
}

// SessionMessage is the domain-level message representation.
type SessionMessage struct {
	ID        int
	SessionID string
	UserID    string
	Role      string
	Content   string
	CreatedAt time.Time
}

// SessionManager handles conversation thread lifecycle.
type SessionManager struct {
	db *sql.DB
}

// NewSessionManager creates a SessionManager backed by the given database.
func NewSessionManager(database *sql.DB) *SessionManager {
	return &SessionManager{db: database}
}

// GetOrCreateSession finds an active session or creates a new one.
// contextID is typically "dm-{user_id}" for DMs or "channel-{channel_id}" for groups.
func (m *SessionManager) GetOrCreateSession(ctx context.Context, userID, contextID, projectID string) (*Session, error) {
	q := db.New(m.db)

	// Try to find an existing active session.
	existing, err := q.GetActiveSession(ctx, db.GetActiveSessionParams{
		UserID:    userID,
		ContextID: contextID,
		ProjectID: projectID,
	})
	if err == nil {
		// Update last activity timestamp.
		now := time.Now().UTC().Format(time.RFC3339)
		if uerr := q.UpdateSessionActivity(ctx, now, existing.ID); uerr != nil {
			return nil, fmt.Errorf("update session activity: %w", uerr)
		}
		return dbSessionToDomain(&existing), nil
	}
	if err != sql.ErrNoRows {
		return nil, fmt.Errorf("get active session: %w", err)
	}

	// Ensure the project exists, creating it if necessary.
	if err := m.ensureProject(ctx, q, projectID, userID); err != nil {
		return nil, err
	}

	// No active session found — create one.
	now := time.Now().UTC().Format(time.RFC3339)
	created, err := q.CreateSession(ctx, db.CreateSessionParams{
		ID:             uuid.New().String(),
		ProjectID:      projectID,
		UserID:         userID,
		ContextID:      contextID,
		Archived:       "false",
		StartedAt:      now,
		LastActivityAt: now,
	})
	if err != nil {
		return nil, fmt.Errorf("create session: %w", err)
	}
	return dbSessionToDomain(&created), nil
}

// GetRecentMessages returns the last N messages in a session in chronological order.
func (m *SessionManager) GetRecentMessages(ctx context.Context, sessionID string, limit int) ([]SessionMessage, error) {
	q := db.New(m.db)

	msgs, err := q.GetRecentMessages(ctx, db.GetRecentMessagesParams{
		SessionID: sessionID,
		Limit:     int64(limit),
	})
	if err != nil {
		return nil, fmt.Errorf("get recent messages: %w", err)
	}

	// DB returns DESC order; reverse to chronological.
	result := make([]SessionMessage, len(msgs))
	for i, msg := range msgs {
		result[len(msgs)-1-i] = dbMessageToDomain(&msg)
	}
	return result, nil
}

// StoreMessage persists a message to the database and updates session activity.
func (m *SessionManager) StoreMessage(ctx context.Context, sessionID, userID, role, content string) error {
	q := db.New(m.db)
	now := time.Now().UTC().Format(time.RFC3339)

	if _, err := q.CreateMessage(ctx, db.CreateMessageParams{
		SessionID: sessionID,
		UserID:    userID,
		Role:      role,
		Content:   content,
		CreatedAt: now,
	}); err != nil {
		return fmt.Errorf("create message: %w", err)
	}

	if err := q.UpdateSessionActivity(ctx, now, sessionID); err != nil {
		return fmt.Errorf("update session activity: %w", err)
	}
	return nil
}

// UpdateSummary sets the session summary.
func (m *SessionManager) UpdateSummary(ctx context.Context, sessionID, summary string) error {
	q := db.New(m.db)
	if err := q.SetSessionSummary(ctx, summary, sessionID); err != nil {
		return fmt.Errorf("set session summary: %w", err)
	}
	return nil
}

// ShouldUpdateSummary checks if enough messages have accumulated since the
// last summary. Returns true when the message count exceeds summaryThreshold
// and either no summary exists or the count is a multiple of the threshold.
func (m *SessionManager) ShouldUpdateSummary(ctx context.Context, sessionID string) bool {
	var count int
	err := m.db.QueryRowContext(ctx,
		`SELECT COUNT(*) FROM messages WHERE session_id = ?`, sessionID,
	).Scan(&count)
	if err != nil {
		return false
	}

	if count < summaryThreshold {
		return false
	}

	// Check if a summary already exists.
	var summary sql.NullString
	err = m.db.QueryRowContext(ctx,
		`SELECT session_summary FROM sessions WHERE id = ?`, sessionID,
	).Scan(&summary)
	if err != nil {
		return false
	}

	// No summary yet and we have enough messages.
	if !summary.Valid || summary.String == "" {
		return true
	}

	// Summary exists — trigger again at each threshold multiple.
	return count%summaryThreshold == 0
}

// ensureProject creates the project if it doesn't exist.
func (m *SessionManager) ensureProject(ctx context.Context, q *db.Queries, projectID, ownerID string) error {
	_, err := q.GetProject(ctx, projectID)
	if err == nil {
		return nil
	}
	if err != sql.ErrNoRows {
		return fmt.Errorf("get project: %w", err)
	}

	now := time.Now().UTC()
	_, err = q.CreateProject(ctx, db.CreateProjectParams{
		ID:        projectID,
		OwnerID:   ownerID,
		Name:      projectID,
		CreatedAt: sql.NullTime{Time: now, Valid: true},
		UpdatedAt: sql.NullTime{Time: now, Valid: true},
	})
	if err != nil {
		return fmt.Errorf("create project: %w", err)
	}
	return nil
}

func dbSessionToDomain(s *db.Session) *Session {
	return &Session{
		ID:             s.ID,
		ProjectID:      s.ProjectID,
		UserID:         s.UserID,
		ContextID:      s.ContextID,
		Title:          s.Title.String,
		SessionSummary: s.SessionSummary.String,
		LastActivityAt: s.LastActivityAt,
	}
}

func dbMessageToDomain(m *db.Message) SessionMessage {
	return SessionMessage{
		ID:        int(m.ID),
		SessionID: m.SessionID,
		UserID:    m.UserID,
		Role:      m.Role,
		Content:   m.Content,
		CreatedAt: m.CreatedAt,
	}
}
