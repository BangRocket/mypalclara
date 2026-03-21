package gateway

import (
	"context"
	"database/sql"
	"encoding/json"
	"os"
	"path/filepath"
	"runtime"
	"testing"

	_ "github.com/mattn/go-sqlite3"

	"github.com/BangRocket/mypalclara/go/internal/llm"
	"github.com/BangRocket/mypalclara/go/internal/memory"
)

// newSimpleMockProvider creates a mockProvider that returns a fixed response.
func newSimpleMockProvider(response string) *mockProvider {
	content := response
	return &mockProvider{
		responses: []*llm.ToolResponse{
			{Content: &content, StopReason: "end_turn"},
		},
		completeResult: response,
	}
}

func TestProcessorProcess(t *testing.T) {
	// Create an in-memory SQLite database for session management.
	database := setupTestDB(t)
	defer database.Close()

	provider := newSimpleMockProvider("Hello from Clara!")

	mm, err := memory.Initialize(database, provider)
	if err != nil {
		t.Fatalf("failed to initialize memory manager: %v", err)
	}

	processor := NewMessageProcessor(mm, provider)

	req := &MessageRequest{
		Type: MsgTypeMessage,
		ID:   "test-req-1",
		User: UserInfo{
			ID:   "test-user",
			Name: "Test User",
		},
		Channel: ChannelInfo{
			ID:   "test-channel",
			Type: "dm",
		},
		Content: "Hello Clara!",
	}

	// Collect all sent messages.
	// The processor sends []byte (from MarshalMessage), so we cast directly.
	var sentMessages []json.RawMessage
	send := func(msg any) error {
		switch v := msg.(type) {
		case []byte:
			sentMessages = append(sentMessages, json.RawMessage(v))
		case json.RawMessage:
			sentMessages = append(sentMessages, v)
		default:
			data, err := json.Marshal(msg)
			if err != nil {
				return err
			}
			sentMessages = append(sentMessages, data)
		}
		return nil
	}

	err = processor.Process(context.Background(), req, send)
	if err != nil {
		t.Fatalf("Process returned error: %v", err)
	}

	// We should have at least ResponseStart and ResponseEnd.
	if len(sentMessages) < 2 {
		t.Fatalf("expected at least 2 sent messages, got %d", len(sentMessages))
	}

	// Check first message is ResponseStart.
	var firstEnvelope struct {
		Type string `json:"type"`
	}
	if err := json.Unmarshal(sentMessages[0], &firstEnvelope); err != nil {
		t.Fatalf("failed to unmarshal first message: %v", err)
	}
	if firstEnvelope.Type != MsgTypeResponseStart {
		t.Errorf("expected first message type %q, got %q", MsgTypeResponseStart, firstEnvelope.Type)
	}

	// Check last message is ResponseEnd with content.
	var lastEnvelope struct {
		Type    string          `json:"type"`
		Payload json.RawMessage `json:"payload"`
	}
	lastIdx := len(sentMessages) - 1
	if err := json.Unmarshal(sentMessages[lastIdx], &lastEnvelope); err != nil {
		t.Fatalf("failed to unmarshal last message: %v", err)
	}
	if lastEnvelope.Type != MsgTypeResponseEnd {
		t.Errorf("expected last message type %q, got %q", MsgTypeResponseEnd, lastEnvelope.Type)
	}

	var endPayload ResponseEnd
	if err := json.Unmarshal(lastEnvelope.Payload, &endPayload); err != nil {
		t.Fatalf("failed to unmarshal ResponseEnd payload: %v", err)
	}
	if endPayload.FullText == "" {
		t.Error("expected non-empty FullText in ResponseEnd")
	}
	if endPayload.RequestID != "test-req-1" {
		t.Errorf("expected request_id %q, got %q", "test-req-1", endPayload.RequestID)
	}
}

func TestProcessorProcess_PrivacyScope(t *testing.T) {
	tests := []struct {
		channelType string
		expected    string
	}{
		{"dm", "full"},
		{"server", "public_only"},
		{"group", "public_only"},
		{"", "public_only"},
	}
	for _, tt := range tests {
		got := privacyScope(tt.channelType)
		if got != tt.expected {
			t.Errorf("privacyScope(%q) = %q, want %q", tt.channelType, got, tt.expected)
		}
	}
}

func TestTruncate(t *testing.T) {
	tests := []struct {
		input    string
		maxLen   int
		expected string
	}{
		{"hello", 10, "hello"},
		{"hello world", 5, "hello..."},
		{"", 5, ""},
	}
	for _, tt := range tests {
		got := truncate(tt.input, tt.maxLen)
		if got != tt.expected {
			t.Errorf("truncate(%q, %d) = %q, want %q", tt.input, tt.maxLen, got, tt.expected)
		}
	}
}

// testMigrationPath returns the path to the migration SQL file relative to this test file.
func testMigrationPath() string {
	_, thisFile, _, _ := runtime.Caller(0)
	return filepath.Join(filepath.Dir(thisFile), "..", "db", "migrations", "001_initial.up.sql")
}

// setupTestDB creates an in-memory SQLite DB with the full schema.
func setupTestDB(t *testing.T) *sql.DB {
	t.Helper()

	database, err := sql.Open("sqlite3", ":memory:")
	if err != nil {
		t.Fatalf("failed to open test database: %v", err)
	}
	t.Cleanup(func() { database.Close() })

	if _, err := database.Exec("PRAGMA foreign_keys=ON"); err != nil {
		t.Fatalf("enable foreign keys: %v", err)
	}

	ddl, err := os.ReadFile(testMigrationPath())
	if err != nil {
		t.Fatalf("read migration file: %v", err)
	}
	if _, err := database.Exec(string(ddl)); err != nil {
		t.Fatalf("execute migration: %v", err)
	}

	return database
}
