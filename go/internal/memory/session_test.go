package memory_test

import (
	"context"
	"database/sql"
	"os"
	"path/filepath"
	"runtime"
	"testing"

	"github.com/BangRocket/mypalclara/go/internal/memory"
	_ "github.com/mattn/go-sqlite3"
)

// migrationPath returns the absolute path to the migration SQL file,
// relative to this test file's location on disk.
func migrationPath() string {
	_, thisFile, _, _ := runtime.Caller(0)
	return filepath.Join(filepath.Dir(thisFile), "..", "db", "migrations", "001_initial.up.sql")
}

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

	ddl, err := os.ReadFile(migrationPath())
	if err != nil {
		t.Fatalf("read migration file: %v", err)
	}
	if _, err := conn.Exec(string(ddl)); err != nil {
		t.Fatalf("execute migration: %v", err)
	}

	return conn
}

func TestSessionGetOrCreateSession(t *testing.T) {
	conn := setupTestDB(t)
	sm := memory.NewSessionManager(conn)
	ctx := context.Background()

	// First call creates a new session.
	sess1, err := sm.GetOrCreateSession(ctx, "user-1", "dm-user-1", "proj-1")
	if err != nil {
		t.Fatalf("GetOrCreateSession (create): %v", err)
	}
	if sess1.ID == "" {
		t.Fatal("expected non-empty session ID")
	}
	if sess1.UserID != "user-1" {
		t.Errorf("expected user_id 'user-1', got %q", sess1.UserID)
	}
	if sess1.ContextID != "dm-user-1" {
		t.Errorf("expected context_id 'dm-user-1', got %q", sess1.ContextID)
	}
	if sess1.ProjectID != "proj-1" {
		t.Errorf("expected project_id 'proj-1', got %q", sess1.ProjectID)
	}

	// Second call returns the same session.
	sess2, err := sm.GetOrCreateSession(ctx, "user-1", "dm-user-1", "proj-1")
	if err != nil {
		t.Fatalf("GetOrCreateSession (existing): %v", err)
	}
	if sess2.ID != sess1.ID {
		t.Errorf("expected same session ID %q, got %q", sess1.ID, sess2.ID)
	}

	// Different context creates a different session.
	sess3, err := sm.GetOrCreateSession(ctx, "user-1", "channel-general", "proj-1")
	if err != nil {
		t.Fatalf("GetOrCreateSession (different context): %v", err)
	}
	if sess3.ID == sess1.ID {
		t.Error("expected different session for different context_id")
	}
}

func TestSessionStoreAndGetMessages(t *testing.T) {
	conn := setupTestDB(t)
	sm := memory.NewSessionManager(conn)
	ctx := context.Background()

	sess, err := sm.GetOrCreateSession(ctx, "user-1", "dm-user-1", "proj-1")
	if err != nil {
		t.Fatalf("GetOrCreateSession: %v", err)
	}

	// Store 3 messages.
	msgs := []struct {
		role, content string
	}{
		{"user", "Hello Clara"},
		{"assistant", "Hi there!"},
		{"user", "How are you?"},
	}
	for _, m := range msgs {
		if err := sm.StoreMessage(ctx, sess.ID, "user-1", m.role, m.content); err != nil {
			t.Fatalf("StoreMessage(%q): %v", m.content, err)
		}
	}

	// Get recent 2 — should be the last two in chronological order.
	recent, err := sm.GetRecentMessages(ctx, sess.ID, 2)
	if err != nil {
		t.Fatalf("GetRecentMessages: %v", err)
	}
	if len(recent) != 2 {
		t.Fatalf("expected 2 messages, got %d", len(recent))
	}

	// Chronological order: "Hi there!" then "How are you?"
	if recent[0].Content != "Hi there!" {
		t.Errorf("expected first message 'Hi there!', got %q", recent[0].Content)
	}
	if recent[1].Content != "How are you?" {
		t.Errorf("expected second message 'How are you?', got %q", recent[1].Content)
	}

	// Verify role is preserved.
	if recent[0].Role != "assistant" {
		t.Errorf("expected role 'assistant', got %q", recent[0].Role)
	}
	if recent[1].Role != "user" {
		t.Errorf("expected role 'user', got %q", recent[1].Role)
	}
}

func TestSessionUpdateSummary(t *testing.T) {
	conn := setupTestDB(t)
	sm := memory.NewSessionManager(conn)
	ctx := context.Background()

	sess, err := sm.GetOrCreateSession(ctx, "user-1", "dm-user-1", "proj-1")
	if err != nil {
		t.Fatalf("GetOrCreateSession: %v", err)
	}

	// Initially no summary.
	if sess.SessionSummary != "" {
		t.Errorf("expected empty summary, got %q", sess.SessionSummary)
	}

	// Set a summary.
	summary := "User greeted Clara. Clara responded warmly."
	if err := sm.UpdateSummary(ctx, sess.ID, summary); err != nil {
		t.Fatalf("UpdateSummary: %v", err)
	}

	// Re-fetch session and verify summary persisted.
	sess2, err := sm.GetOrCreateSession(ctx, "user-1", "dm-user-1", "proj-1")
	if err != nil {
		t.Fatalf("GetOrCreateSession after summary: %v", err)
	}
	if sess2.SessionSummary != summary {
		t.Errorf("expected summary %q, got %q", summary, sess2.SessionSummary)
	}
}

func TestSessionShouldUpdateSummary(t *testing.T) {
	conn := setupTestDB(t)
	sm := memory.NewSessionManager(conn)
	ctx := context.Background()

	sess, err := sm.GetOrCreateSession(ctx, "user-1", "dm-user-1", "proj-1")
	if err != nil {
		t.Fatalf("GetOrCreateSession: %v", err)
	}

	// With no messages, should not update.
	if sm.ShouldUpdateSummary(ctx, sess.ID) {
		t.Error("expected ShouldUpdateSummary=false with 0 messages")
	}

	// Add 10 messages (the threshold).
	for i := range 10 {
		role := "user"
		if i%2 == 1 {
			role = "assistant"
		}
		if err := sm.StoreMessage(ctx, sess.ID, "user-1", role, "msg"); err != nil {
			t.Fatalf("StoreMessage %d: %v", i, err)
		}
	}

	// Should now want a summary (no summary exists yet, 10 messages).
	if !sm.ShouldUpdateSummary(ctx, sess.ID) {
		t.Error("expected ShouldUpdateSummary=true with 10 messages and no summary")
	}

	// Set a summary — should stop triggering until next threshold.
	if err := sm.UpdateSummary(ctx, sess.ID, "some summary"); err != nil {
		t.Fatalf("UpdateSummary: %v", err)
	}

	// At exactly 10 with a summary, count%10==0 so should still be true.
	if !sm.ShouldUpdateSummary(ctx, sess.ID) {
		t.Error("expected ShouldUpdateSummary=true at threshold multiple with summary")
	}

	// Add one more — 11 messages, 11%10!=0, should be false.
	if err := sm.StoreMessage(ctx, sess.ID, "user-1", "user", "extra"); err != nil {
		t.Fatalf("StoreMessage extra: %v", err)
	}
	if sm.ShouldUpdateSummary(ctx, sess.ID) {
		t.Error("expected ShouldUpdateSummary=false with 11 messages")
	}
}
