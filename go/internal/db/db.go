// Package db provides database access for Clara's core tables.
//
// It wraps an *sql.DB with typed query methods matching the sqlc-style
// interface. When sqlc is available, this package can be regenerated;
// otherwise the hand-written code here is functionally equivalent.
package db

import (
	"context"
	"database/sql"
	"fmt"
	"os"

	_ "github.com/mattn/go-sqlite3"
)

// Open returns a configured *sql.DB. It reads DATABASE_URL from the
// environment and falls back to a local SQLite file "clara.db".
// For SQLite, it auto-creates the file and applies migrations.
func Open() (*sql.DB, error) {
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		dsn = "file:clara.db?_journal_mode=WAL&_foreign_keys=1"
	}

	db, err := sql.Open("sqlite3", dsn)
	if err != nil {
		return nil, fmt.Errorf("db.Open: %w", err)
	}

	if err := db.Ping(); err != nil {
		db.Close()
		return nil, fmt.Errorf("db.Open: ping: %w", err)
	}

	// Auto-apply migrations (all use IF NOT EXISTS, safe to re-run).
	if err := Migrate(db); err != nil {
		db.Close()
		return nil, fmt.Errorf("db.Open: migrate: %w", err)
	}

	return db, nil
}

// Migrate applies all embedded migration files to the database.
func Migrate(db *sql.DB) error {
	for _, migration := range migrations {
		if _, err := db.Exec(migration); err != nil {
			return fmt.Errorf("migration failed: %w", err)
		}
	}
	return nil
}

// migrations holds the SQL migration statements.
// Embedded directly rather than reading files so the binary is self-contained.
var migrations = []string{
	`CREATE TABLE IF NOT EXISTS projects (
		id TEXT PRIMARY KEY,
		owner_id TEXT NOT NULL,
		name TEXT NOT NULL,
		created_at DATETIME,
		updated_at DATETIME
	)`,
	`CREATE TABLE IF NOT EXISTS sessions (
		id TEXT PRIMARY KEY,
		project_id TEXT NOT NULL REFERENCES projects(id),
		user_id TEXT NOT NULL,
		context_id TEXT NOT NULL DEFAULT 'default',
		title TEXT,
		archived TEXT NOT NULL DEFAULT 'false',
		started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
		last_activity_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
		previous_session_id TEXT,
		context_snapshot TEXT,
		session_summary TEXT
	)`,
	`CREATE INDEX IF NOT EXISTS ix_session_user_context_project ON sessions (user_id, context_id, project_id)`,
	`CREATE TABLE IF NOT EXISTS messages (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		session_id TEXT NOT NULL REFERENCES sessions(id),
		user_id TEXT NOT NULL,
		role TEXT NOT NULL,
		content TEXT NOT NULL,
		created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
	)`,
	`CREATE INDEX IF NOT EXISTS ix_message_session_created ON messages (session_id, created_at)`,
	`CREATE TABLE IF NOT EXISTS channel_summaries (
		id TEXT PRIMARY KEY,
		channel_id TEXT NOT NULL UNIQUE,
		summary TEXT DEFAULT '',
		summary_cutoff_at DATETIME,
		last_updated_at DATETIME
	)`,
	`CREATE TABLE IF NOT EXISTS channel_configs (
		id TEXT PRIMARY KEY,
		channel_id TEXT NOT NULL UNIQUE,
		guild_id TEXT NOT NULL,
		mode TEXT NOT NULL DEFAULT 'mention',
		configured_by TEXT,
		configured_at DATETIME,
		updated_at DATETIME
	)`,
	`CREATE INDEX IF NOT EXISTS ix_channel_config_channel_id ON channel_configs (channel_id)`,
	`CREATE INDEX IF NOT EXISTS ix_channel_config_guild_id ON channel_configs (guild_id)`,
	`CREATE TABLE IF NOT EXISTS log_entries (
		id TEXT PRIMARY KEY,
		timestamp DATETIME NOT NULL,
		level TEXT NOT NULL,
		logger_name TEXT NOT NULL,
		message TEXT NOT NULL,
		module TEXT,
		function TEXT,
		line_number INTEGER,
		exception TEXT,
		extra_data TEXT,
		user_id TEXT,
		session_id TEXT
	)`,
	`CREATE INDEX IF NOT EXISTS ix_log_entry_timestamp ON log_entries (timestamp)`,
	`CREATE INDEX IF NOT EXISTS ix_log_entry_level ON log_entries (level)`,
	`CREATE INDEX IF NOT EXISTS ix_log_entry_logger_name ON log_entries (logger_name)`,
}

// Queries wraps an *sql.DB (or *sql.Tx) to provide typed query methods.
type Queries struct {
	db DBTX
}

// DBTX is the interface satisfied by both *sql.DB and *sql.Tx.
type DBTX interface {
	ExecContext(ctx context.Context, query string, args ...interface{}) (sql.Result, error)
	QueryContext(ctx context.Context, query string, args ...interface{}) (*sql.Rows, error)
	QueryRowContext(ctx context.Context, query string, args ...interface{}) *sql.Row
}

// New creates a Queries instance from a *sql.DB or *sql.Tx.
func New(db DBTX) *Queries {
	return &Queries{db: db}
}
