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
func Open() (*sql.DB, error) {
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		dsn = "clara.db"
	}

	db, err := sql.Open("sqlite3", dsn)
	if err != nil {
		return nil, fmt.Errorf("db.Open: %w", err)
	}

	// Enable WAL mode and foreign keys for SQLite.
	if _, err := db.Exec("PRAGMA journal_mode=WAL"); err != nil {
		db.Close()
		return nil, fmt.Errorf("db.Open: set WAL: %w", err)
	}
	if _, err := db.Exec("PRAGMA foreign_keys=ON"); err != nil {
		db.Close()
		return nil, fmt.Errorf("db.Open: enable foreign keys: %w", err)
	}

	return db, nil
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
