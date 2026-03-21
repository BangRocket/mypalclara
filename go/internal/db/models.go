package db

import (
	"database/sql"
	"time"
)

// Project matches the Python Project model.
type Project struct {
	ID        string       `json:"id"`
	OwnerID   string       `json:"owner_id"`
	Name      string       `json:"name"`
	CreatedAt sql.NullTime `json:"created_at"`
	UpdatedAt sql.NullTime `json:"updated_at"`
}

// Session matches the Python Session model.
type Session struct {
	ID                string         `json:"id"`
	ProjectID         string         `json:"project_id"`
	UserID            string         `json:"user_id"`
	ContextID         string         `json:"context_id"`
	Title             sql.NullString `json:"title"`
	Archived          string         `json:"archived"`
	StartedAt         time.Time      `json:"started_at"`
	LastActivityAt    time.Time      `json:"last_activity_at"`
	PreviousSessionID sql.NullString `json:"previous_session_id"`
	ContextSnapshot   sql.NullString `json:"context_snapshot"`
	SessionSummary    sql.NullString `json:"session_summary"`
}

// Message matches the Python Message model.
type Message struct {
	ID        int64     `json:"id"`
	SessionID string    `json:"session_id"`
	UserID    string    `json:"user_id"`
	Role      string    `json:"role"`
	Content   string    `json:"content"`
	CreatedAt time.Time `json:"created_at"`
}

// ChannelSummary matches the Python ChannelSummary model.
type ChannelSummary struct {
	ID              string         `json:"id"`
	ChannelID       string         `json:"channel_id"`
	Summary         sql.NullString `json:"summary"`
	SummaryCutoffAt sql.NullTime   `json:"summary_cutoff_at"`
	LastUpdatedAt   sql.NullTime   `json:"last_updated_at"`
}

// ChannelConfig matches the Python ChannelConfig model.
type ChannelConfig struct {
	ID           string         `json:"id"`
	ChannelID    string         `json:"channel_id"`
	GuildID      string         `json:"guild_id"`
	Mode         string         `json:"mode"`
	ConfiguredBy sql.NullString `json:"configured_by"`
	ConfiguredAt sql.NullTime   `json:"configured_at"`
	UpdatedAt    sql.NullTime   `json:"updated_at"`
}

// LogEntry matches the Python LogEntry model.
type LogEntry struct {
	ID         string         `json:"id"`
	Timestamp  time.Time      `json:"timestamp"`
	Level      string         `json:"level"`
	LoggerName string         `json:"logger_name"`
	Message    string         `json:"message"`
	Module     sql.NullString `json:"module"`
	Function   sql.NullString `json:"function"`
	LineNumber sql.NullInt64  `json:"line_number"`
	Exception  sql.NullString `json:"exception"`
	ExtraData  sql.NullString `json:"extra_data"`
	UserID     sql.NullString `json:"user_id"`
	SessionID  sql.NullString `json:"session_id"`
}
