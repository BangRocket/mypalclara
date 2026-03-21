package db_test

import (
	"context"
	"database/sql"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/BangRocket/mypalclara/go/internal/db"
	_ "github.com/mattn/go-sqlite3"
)

// setupTestDB creates an in-memory SQLite database and runs the migration.
func setupTestDB(t *testing.T) *sql.DB {
	t.Helper()

	conn, err := sql.Open("sqlite3", ":memory:")
	if err != nil {
		t.Fatalf("open in-memory db: %v", err)
	}
	t.Cleanup(func() { conn.Close() })

	if _, err := conn.Exec("PRAGMA foreign_keys=ON"); err != nil {
		t.Fatalf("enable foreign keys: %v", err)
	}

	// Read migration SQL from the file on disk.
	migrationPath := filepath.Join("migrations", "001_initial.up.sql")
	ddl, err := os.ReadFile(migrationPath)
	if err != nil {
		t.Fatalf("read migration file: %v", err)
	}
	if _, err := conn.Exec(string(ddl)); err != nil {
		t.Fatalf("execute migration: %v", err)
	}

	return conn
}

func TestCreateAndGetProject(t *testing.T) {
	conn := setupTestDB(t)
	q := db.New(conn)
	ctx := context.Background()
	now := time.Now().UTC().Truncate(time.Second)

	created, err := q.CreateProject(ctx, db.CreateProjectParams{
		ID:      "proj-1",
		OwnerID: "user-1",
		Name:    "Test Project",
		CreatedAt: sql.NullTime{Time: now, Valid: true},
		UpdatedAt: sql.NullTime{Time: now, Valid: true},
	})
	if err != nil {
		t.Fatalf("CreateProject: %v", err)
	}
	if created.ID != "proj-1" {
		t.Errorf("expected id proj-1, got %s", created.ID)
	}
	if created.Name != "Test Project" {
		t.Errorf("expected name 'Test Project', got %s", created.Name)
	}

	got, err := q.GetProject(ctx, "proj-1")
	if err != nil {
		t.Fatalf("GetProject: %v", err)
	}
	if got.OwnerID != "user-1" {
		t.Errorf("expected owner_id user-1, got %s", got.OwnerID)
	}
	if got.Name != "Test Project" {
		t.Errorf("expected name 'Test Project', got %s", got.Name)
	}
}

func TestCreateAndGetActiveSession(t *testing.T) {
	conn := setupTestDB(t)
	q := db.New(conn)
	ctx := context.Background()
	now := time.Now().UTC().Truncate(time.Second)
	nowStr := now.Format(time.RFC3339)

	// Create prerequisite project.
	_, err := q.CreateProject(ctx, db.CreateProjectParams{
		ID:      "proj-1",
		OwnerID: "user-1",
		Name:    "Test Project",
		CreatedAt: sql.NullTime{Time: now, Valid: true},
		UpdatedAt: sql.NullTime{Time: now, Valid: true},
	})
	if err != nil {
		t.Fatalf("CreateProject: %v", err)
	}

	created, err := q.CreateSession(ctx, db.CreateSessionParams{
		ID:             "sess-1",
		ProjectID:      "proj-1",
		UserID:         "user-1",
		ContextID:      "default",
		Archived:       "false",
		StartedAt:      nowStr,
		LastActivityAt: nowStr,
	})
	if err != nil {
		t.Fatalf("CreateSession: %v", err)
	}
	if created.ID != "sess-1" {
		t.Errorf("expected id sess-1, got %s", created.ID)
	}

	active, err := q.GetActiveSession(ctx, db.GetActiveSessionParams{
		UserID:    "user-1",
		ContextID: "default",
		ProjectID: "proj-1",
	})
	if err != nil {
		t.Fatalf("GetActiveSession: %v", err)
	}
	if active.ID != "sess-1" {
		t.Errorf("expected active session sess-1, got %s", active.ID)
	}
	if active.Archived != "false" {
		t.Errorf("expected archived=false, got %s", active.Archived)
	}
}

func TestCreateAndGetRecentMessages(t *testing.T) {
	conn := setupTestDB(t)
	q := db.New(conn)
	ctx := context.Background()
	now := time.Now().UTC().Truncate(time.Second)
	nowStr := now.Format(time.RFC3339)

	// Create prerequisite project and session.
	_, err := q.CreateProject(ctx, db.CreateProjectParams{
		ID:      "proj-1",
		OwnerID: "user-1",
		Name:    "Test Project",
		CreatedAt: sql.NullTime{Time: now, Valid: true},
		UpdatedAt: sql.NullTime{Time: now, Valid: true},
	})
	if err != nil {
		t.Fatalf("CreateProject: %v", err)
	}
	_, err = q.CreateSession(ctx, db.CreateSessionParams{
		ID:             "sess-1",
		ProjectID:      "proj-1",
		UserID:         "user-1",
		ContextID:      "default",
		Archived:       "false",
		StartedAt:      nowStr,
		LastActivityAt: nowStr,
	})
	if err != nil {
		t.Fatalf("CreateSession: %v", err)
	}

	// Create two messages with different timestamps.
	t1 := now.Add(-time.Minute).Format(time.RFC3339)
	t2 := nowStr

	_, err = q.CreateMessage(ctx, db.CreateMessageParams{
		SessionID: "sess-1",
		UserID:    "user-1",
		Role:      "user",
		Content:   "Hello Clara",
		CreatedAt: t1,
	})
	if err != nil {
		t.Fatalf("CreateMessage 1: %v", err)
	}

	_, err = q.CreateMessage(ctx, db.CreateMessageParams{
		SessionID: "sess-1",
		UserID:    "assistant",
		Role:      "assistant",
		Content:   "Hi there!",
		CreatedAt: t2,
	})
	if err != nil {
		t.Fatalf("CreateMessage 2: %v", err)
	}

	msgs, err := q.GetRecentMessages(ctx, db.GetRecentMessagesParams{
		SessionID: "sess-1",
		Limit:     10,
	})
	if err != nil {
		t.Fatalf("GetRecentMessages: %v", err)
	}
	if len(msgs) != 2 {
		t.Fatalf("expected 2 messages, got %d", len(msgs))
	}
	// Most recent first (DESC order).
	if msgs[0].Content != "Hi there!" {
		t.Errorf("expected first message 'Hi there!', got %q", msgs[0].Content)
	}
	if msgs[1].Content != "Hello Clara" {
		t.Errorf("expected second message 'Hello Clara', got %q", msgs[1].Content)
	}
}
