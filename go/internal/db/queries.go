package db

import (
	"context"
	"database/sql"
)

// ---------------------------------------------------------------------------
// Projects
// ---------------------------------------------------------------------------

const getProject = `SELECT id, owner_id, name, created_at, updated_at FROM projects WHERE id = ? LIMIT 1`

func (q *Queries) GetProject(ctx context.Context, id string) (Project, error) {
	row := q.db.QueryRowContext(ctx, getProject, id)
	var p Project
	err := row.Scan(&p.ID, &p.OwnerID, &p.Name, &p.CreatedAt, &p.UpdatedAt)
	return p, err
}

const getProjectByOwner = `SELECT id, owner_id, name, created_at, updated_at FROM projects WHERE owner_id = ? LIMIT 1`

func (q *Queries) GetProjectByOwner(ctx context.Context, ownerID string) (Project, error) {
	row := q.db.QueryRowContext(ctx, getProjectByOwner, ownerID)
	var p Project
	err := row.Scan(&p.ID, &p.OwnerID, &p.Name, &p.CreatedAt, &p.UpdatedAt)
	return p, err
}

type CreateProjectParams struct {
	ID        string       `json:"id"`
	OwnerID   string       `json:"owner_id"`
	Name      string       `json:"name"`
	CreatedAt sql.NullTime `json:"created_at"`
	UpdatedAt sql.NullTime `json:"updated_at"`
}

const createProject = `INSERT INTO projects (id, owner_id, name, created_at, updated_at) VALUES (?, ?, ?, ?, ?) RETURNING id, owner_id, name, created_at, updated_at`

func (q *Queries) CreateProject(ctx context.Context, arg CreateProjectParams) (Project, error) {
	row := q.db.QueryRowContext(ctx, createProject, arg.ID, arg.OwnerID, arg.Name, arg.CreatedAt, arg.UpdatedAt)
	var p Project
	err := row.Scan(&p.ID, &p.OwnerID, &p.Name, &p.CreatedAt, &p.UpdatedAt)
	return p, err
}

// ---------------------------------------------------------------------------
// Sessions
// ---------------------------------------------------------------------------

const getSession = `SELECT id, project_id, user_id, context_id, title, archived, started_at, last_activity_at, previous_session_id, context_snapshot, session_summary FROM sessions WHERE id = ? LIMIT 1`

func (q *Queries) GetSession(ctx context.Context, id string) (Session, error) {
	row := q.db.QueryRowContext(ctx, getSession, id)
	var s Session
	err := row.Scan(&s.ID, &s.ProjectID, &s.UserID, &s.ContextID, &s.Title, &s.Archived, &s.StartedAt, &s.LastActivityAt, &s.PreviousSessionID, &s.ContextSnapshot, &s.SessionSummary)
	return s, err
}

const getActiveSession = `SELECT id, project_id, user_id, context_id, title, archived, started_at, last_activity_at, previous_session_id, context_snapshot, session_summary FROM sessions WHERE user_id = ? AND context_id = ? AND project_id = ? AND archived != 'true' ORDER BY last_activity_at DESC LIMIT 1`

type GetActiveSessionParams struct {
	UserID    string `json:"user_id"`
	ContextID string `json:"context_id"`
	ProjectID string `json:"project_id"`
}

func (q *Queries) GetActiveSession(ctx context.Context, arg GetActiveSessionParams) (Session, error) {
	row := q.db.QueryRowContext(ctx, getActiveSession, arg.UserID, arg.ContextID, arg.ProjectID)
	var s Session
	err := row.Scan(&s.ID, &s.ProjectID, &s.UserID, &s.ContextID, &s.Title, &s.Archived, &s.StartedAt, &s.LastActivityAt, &s.PreviousSessionID, &s.ContextSnapshot, &s.SessionSummary)
	return s, err
}

type CreateSessionParams struct {
	ID                string         `json:"id"`
	ProjectID         string         `json:"project_id"`
	UserID            string         `json:"user_id"`
	ContextID         string         `json:"context_id"`
	Title             sql.NullString `json:"title"`
	Archived          string         `json:"archived"`
	StartedAt         string         `json:"started_at"`
	LastActivityAt    string         `json:"last_activity_at"`
	PreviousSessionID sql.NullString `json:"previous_session_id"`
	ContextSnapshot   sql.NullString `json:"context_snapshot"`
	SessionSummary    sql.NullString `json:"session_summary"`
}

const createSession = `INSERT INTO sessions (id, project_id, user_id, context_id, title, archived, started_at, last_activity_at, previous_session_id, context_snapshot, session_summary) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id, project_id, user_id, context_id, title, archived, started_at, last_activity_at, previous_session_id, context_snapshot, session_summary`

func (q *Queries) CreateSession(ctx context.Context, arg CreateSessionParams) (Session, error) {
	row := q.db.QueryRowContext(ctx, createSession,
		arg.ID, arg.ProjectID, arg.UserID, arg.ContextID, arg.Title, arg.Archived,
		arg.StartedAt, arg.LastActivityAt, arg.PreviousSessionID, arg.ContextSnapshot, arg.SessionSummary,
	)
	var s Session
	err := row.Scan(&s.ID, &s.ProjectID, &s.UserID, &s.ContextID, &s.Title, &s.Archived, &s.StartedAt, &s.LastActivityAt, &s.PreviousSessionID, &s.ContextSnapshot, &s.SessionSummary)
	return s, err
}

const updateSessionActivity = `UPDATE sessions SET last_activity_at = ? WHERE id = ?`

func (q *Queries) UpdateSessionActivity(ctx context.Context, lastActivityAt string, id string) error {
	_, err := q.db.ExecContext(ctx, updateSessionActivity, lastActivityAt, id)
	return err
}

const setSessionSummary = `UPDATE sessions SET session_summary = ? WHERE id = ?`

func (q *Queries) SetSessionSummary(ctx context.Context, summary string, id string) error {
	_, err := q.db.ExecContext(ctx, setSessionSummary, summary, id)
	return err
}

// ---------------------------------------------------------------------------
// Messages
// ---------------------------------------------------------------------------

type GetRecentMessagesParams struct {
	SessionID string `json:"session_id"`
	Limit     int64  `json:"limit"`
}

const getRecentMessages = `SELECT id, session_id, user_id, role, content, created_at FROM messages WHERE session_id = ? ORDER BY created_at DESC LIMIT ?`

func (q *Queries) GetRecentMessages(ctx context.Context, arg GetRecentMessagesParams) ([]Message, error) {
	rows, err := q.db.QueryContext(ctx, getRecentMessages, arg.SessionID, arg.Limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	items := []Message{}
	for rows.Next() {
		var m Message
		if err := rows.Scan(&m.ID, &m.SessionID, &m.UserID, &m.Role, &m.Content, &m.CreatedAt); err != nil {
			return nil, err
		}
		items = append(items, m)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	return items, nil
}

type CreateMessageParams struct {
	SessionID string `json:"session_id"`
	UserID    string `json:"user_id"`
	Role      string `json:"role"`
	Content   string `json:"content"`
	CreatedAt string `json:"created_at"`
}

const createMessage = `INSERT INTO messages (session_id, user_id, role, content, created_at) VALUES (?, ?, ?, ?, ?) RETURNING id, session_id, user_id, role, content, created_at`

func (q *Queries) CreateMessage(ctx context.Context, arg CreateMessageParams) (Message, error) {
	row := q.db.QueryRowContext(ctx, createMessage, arg.SessionID, arg.UserID, arg.Role, arg.Content, arg.CreatedAt)
	var m Message
	err := row.Scan(&m.ID, &m.SessionID, &m.UserID, &m.Role, &m.Content, &m.CreatedAt)
	return m, err
}

type GetChannelMessagesParams struct {
	ContextID string `json:"context_id"`
	Limit     int64  `json:"limit"`
}

const getChannelMessages = `SELECT m.id, m.session_id, m.user_id, m.role, m.content, m.created_at FROM messages m JOIN sessions s ON m.session_id = s.id WHERE s.context_id = ? ORDER BY m.created_at DESC LIMIT ?`

func (q *Queries) GetChannelMessages(ctx context.Context, arg GetChannelMessagesParams) ([]Message, error) {
	rows, err := q.db.QueryContext(ctx, getChannelMessages, arg.ContextID, arg.Limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	items := []Message{}
	for rows.Next() {
		var m Message
		if err := rows.Scan(&m.ID, &m.SessionID, &m.UserID, &m.Role, &m.Content, &m.CreatedAt); err != nil {
			return nil, err
		}
		items = append(items, m)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	return items, nil
}
