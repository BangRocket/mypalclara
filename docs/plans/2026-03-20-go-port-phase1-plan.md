# Go Port Phase 1: Foundation — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Set up the Go module, config/logging, database layer (sqlc), LLM message types, LLM provider interface with OpenAI/Anthropic clients, and token counter — the foundation everything else builds on.

**Architecture:** Standard Go project layout under `go/` with `cmd/` for binaries, `internal/` for business logic. sqlc for type-safe database access. zerolog for structured logging. Provider pattern for LLM clients matching the Python `LLMProvider` interface exactly.

**Tech Stack:** Go 1.23+, sqlc, golang-migrate, zerolog, go-openai, anthropic-sdk-go, godotenv, tiktoken-go

---

### Task 1: Go Module Scaffolding

**Files:**
- Create: `go/go.mod`
- Create: `go/Makefile`
- Create: `go/cmd/clara/main.go`
- Create: `go/cmd/clara-cli/main.go`

**Step 1: Initialize Go module and directory structure**

```bash
cd /Users/heidornj/Code/mypalclara/.worktrees/openlobster-improvements
mkdir -p go/cmd/clara go/cmd/clara-cli go/internal
cd go
go mod init github.com/BangRocket/mypalclara/go
```

**Step 2: Create placeholder main files**

`go/cmd/clara/main.go`:
```go
package main

import "fmt"

func main() {
	fmt.Println("clara gateway - not yet implemented")
}
```

`go/cmd/clara-cli/main.go`:
```go
package main

import "fmt"

func main() {
	fmt.Println("clara-cli - not yet implemented")
}
```

**Step 3: Create Makefile**

`go/Makefile`:
```makefile
.PHONY: build test lint fmt generate clean

build:
	go build -o bin/clara ./cmd/clara
	go build -o bin/clara-cli ./cmd/clara-cli

test:
	go test ./... -v -count=1

lint:
	golangci-lint run ./...

fmt:
	gofmt -s -w .
	goimports -w .

generate:
	sqlc generate

clean:
	rm -rf bin/

# Quick build check
check:
	go vet ./...
	go build ./...
```

**Step 4: Verify it compiles**

Run: `cd go && go build ./... && go vet ./...`
Expected: Clean build, no errors

**Step 5: Commit**

```bash
git add go/
git commit -m "feat: initialize Go module scaffolding [skip-version]"
```

---

### Task 2: Config Loading

Port `mypalclara/config/` to Go. Handles .env loading and environment variable access.

**Files:**
- Create: `go/internal/config/config.go`
- Create: `go/internal/config/config_test.go`

**Step 1: Write the test**

```go
// go/internal/config/config_test.go
package config

import (
	"testing"
)

func TestGetEnvDefault(t *testing.T) {
	tests := []struct {
		name     string
		key      string
		fallback string
		want     string
	}{
		{"missing key returns fallback", "NONEXISTENT_KEY_XYZ", "default", "default"},
		{"empty fallback", "NONEXISTENT_KEY_XYZ", "", ""},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := GetEnv(tt.key, tt.fallback)
			if got != tt.want {
				t.Errorf("GetEnv(%q, %q) = %q, want %q", tt.key, tt.fallback, got, tt.want)
			}
		})
	}
}

func TestGetEnvSetValue(t *testing.T) {
	t.Setenv("TEST_CONFIG_KEY", "myvalue")
	got := GetEnv("TEST_CONFIG_KEY", "fallback")
	if got != "myvalue" {
		t.Errorf("GetEnv() = %q, want %q", got, "myvalue")
	}
}

func TestGetEnvBool(t *testing.T) {
	tests := []struct {
		name     string
		value    string
		fallback bool
		want     bool
	}{
		{"true string", "true", false, true},
		{"TRUE string", "TRUE", false, true},
		{"1 string", "1", false, true},
		{"false string", "false", true, false},
		{"empty uses fallback true", "", true, true},
		{"empty uses fallback false", "", false, false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if tt.value != "" {
				t.Setenv("TEST_BOOL_KEY", tt.value)
			}
			got := GetEnvBool("TEST_BOOL_KEY", tt.fallback)
			if got != tt.want {
				t.Errorf("GetEnvBool() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestGetEnvInt(t *testing.T) {
	t.Setenv("TEST_INT_KEY", "42")
	got := GetEnvInt("TEST_INT_KEY", 10)
	if got != 42 {
		t.Errorf("GetEnvInt() = %d, want 42", got)
	}
}

func TestGetEnvIntInvalid(t *testing.T) {
	t.Setenv("TEST_INT_KEY", "notanumber")
	got := GetEnvInt("TEST_INT_KEY", 99)
	if got != 99 {
		t.Errorf("GetEnvInt() with invalid = %d, want 99", got)
	}
}

func TestLLMProvider(t *testing.T) {
	t.Setenv("LLM_PROVIDER", "anthropic")
	got := LLMProvider()
	if got != "anthropic" {
		t.Errorf("LLMProvider() = %q, want %q", got, "anthropic")
	}
}

func TestLLMProviderDefault(t *testing.T) {
	// Don't set LLM_PROVIDER — should default to "openrouter"
	got := LLMProvider()
	if got != "openrouter" {
		t.Errorf("LLMProvider() default = %q, want %q", got, "openrouter")
	}
}
```

**Step 2: Run test to verify it fails**

Run: `cd go && go test ./internal/config/ -v`
Expected: FAIL — package doesn't exist

**Step 3: Implement**

```go
// go/internal/config/config.go
package config

import (
	"os"
	"strconv"
	"strings"

	"github.com/joho/godotenv"
)

// Init loads .env file if present. Call once at startup.
func Init() {
	_ = godotenv.Load() // ignore error if .env doesn't exist
}

// GetEnv returns an environment variable or fallback.
func GetEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

// GetEnvBool returns an environment variable as bool.
func GetEnvBool(key string, fallback bool) bool {
	v := os.Getenv(key)
	if v == "" {
		return fallback
	}
	lower := strings.ToLower(v)
	return lower == "true" || lower == "1" || lower == "yes"
}

// GetEnvInt returns an environment variable as int.
func GetEnvInt(key string, fallback int) int {
	v := os.Getenv(key)
	if v == "" {
		return fallback
	}
	i, err := strconv.Atoi(v)
	if err != nil {
		return fallback
	}
	return i
}

// GetEnvFloat returns an environment variable as float64.
func GetEnvFloat(key string, fallback float64) float64 {
	v := os.Getenv(key)
	if v == "" {
		return fallback
	}
	f, err := strconv.ParseFloat(v, 64)
	if err != nil {
		return fallback
	}
	return f
}

// LLMProvider returns the configured LLM provider.
func LLMProvider() string {
	return strings.ToLower(GetEnv("LLM_PROVIDER", "openrouter"))
}
```

**Step 4: Add godotenv dependency and run tests**

Run: `cd go && go get github.com/joho/godotenv && go test ./internal/config/ -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add go/
git commit -m "feat(go): add config loading with env helpers [skip-version]"
```

---

### Task 3: Structured Logging

Port `mypalclara/config/logging.py` to Go using zerolog. Matches the colored console output, tag-based colors, and MCP stderr safety.

**Files:**
- Create: `go/internal/config/logging.go`
- Create: `go/internal/config/logging_test.go`

**Step 1: Write the test**

```go
// go/internal/config/logging_test.go
package config

import (
	"bytes"
	"strings"
	"testing"

	"github.com/rs/zerolog"
)

func TestNewLogger(t *testing.T) {
	var buf bytes.Buffer
	logger := NewLoggerTo("test.module", &buf)
	logger.Info().Msg("hello")
	output := buf.String()
	if !strings.Contains(output, "hello") {
		t.Errorf("log output should contain message, got: %s", output)
	}
}

func TestLoggerLevel(t *testing.T) {
	t.Setenv("LOG_LEVEL", "WARN")
	var buf bytes.Buffer
	logger := NewLoggerTo("test", &buf)
	logger.Info().Msg("should not appear")
	logger.Warn().Msg("should appear")
	output := buf.String()
	if strings.Contains(output, "should not appear") {
		t.Error("INFO should be suppressed at WARN level")
	}
	if !strings.Contains(output, "should appear") {
		t.Error("WARN should be logged at WARN level")
	}
}

func TestGetLogLevel(t *testing.T) {
	tests := []struct {
		env  string
		want zerolog.Level
	}{
		{"DEBUG", zerolog.DebugLevel},
		{"INFO", zerolog.InfoLevel},
		{"WARN", zerolog.WarnLevel},
		{"WARNING", zerolog.WarnLevel},
		{"ERROR", zerolog.ErrorLevel},
		{"", zerolog.InfoLevel},
		{"invalid", zerolog.InfoLevel},
	}
	for _, tt := range tests {
		t.Run(tt.env, func(t *testing.T) {
			if tt.env != "" {
				t.Setenv("LOG_LEVEL", tt.env)
			}
			got := getLogLevel()
			if got != tt.want {
				t.Errorf("getLogLevel() with LOG_LEVEL=%q = %v, want %v", tt.env, got, tt.want)
			}
		})
	}
}
```

**Step 2: Run test to verify it fails**

Run: `cd go && go get github.com/rs/zerolog && go test ./internal/config/ -v -run TestNewLogger`
Expected: FAIL

**Step 3: Implement**

```go
// go/internal/config/logging.go
package config

import (
	"io"
	"os"
	"strings"
	"time"

	"github.com/rs/zerolog"
)

// getLogLevel returns the zerolog level from LOG_LEVEL env var.
func getLogLevel() zerolog.Level {
	level := strings.ToUpper(os.Getenv("LOG_LEVEL"))
	switch level {
	case "DEBUG":
		return zerolog.DebugLevel
	case "INFO":
		return zerolog.InfoLevel
	case "WARN", "WARNING":
		return zerolog.WarnLevel
	case "ERROR":
		return zerolog.ErrorLevel
	case "CRITICAL":
		return zerolog.FatalLevel
	default:
		return zerolog.InfoLevel
	}
}

// InitLogging sets up the global zerolog configuration.
// All output goes to stderr for MCP compatibility.
func InitLogging() {
	zerolog.TimeFieldFormat = time.TimeOnly
	zerolog.SetGlobalLevel(getLogLevel())
}

// NewLogger creates a named logger writing to stderr with console formatting.
func NewLogger(name string) zerolog.Logger {
	return NewLoggerTo(name, os.Stderr)
}

// NewLoggerTo creates a named logger writing to the given writer.
func NewLoggerTo(name string, w io.Writer) zerolog.Logger {
	output := zerolog.ConsoleWriter{
		Out:        w,
		TimeFormat: "15:04:05",
		NoColor:    false,
	}
	return zerolog.New(output).
		With().
		Timestamp().
		Str("tag", name).
		Logger().
		Level(getLogLevel())
}
```

**Step 4: Run tests**

Run: `cd go && go test ./internal/config/ -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add go/
git commit -m "feat(go): add structured logging with zerolog [skip-version]"
```

---

### Task 4: Database Schema + sqlc

Create SQL schema files matching the Python SQLAlchemy models exactly, configure sqlc, and generate Go code.

**Files:**
- Create: `go/sqlc.yaml`
- Create: `go/internal/db/migrations/001_initial.up.sql`
- Create: `go/internal/db/migrations/001_initial.down.sql`
- Create: `go/internal/db/queries/projects.sql`
- Create: `go/internal/db/queries/sessions.sql`
- Create: `go/internal/db/queries/messages.sql`
- Create: `go/internal/db/db.go`
- Create: `go/internal/db/db_test.go`

**Step 1: Create sqlc config**

`go/sqlc.yaml`:
```yaml
version: "2"
sql:
  - engine: "sqlite"
    queries: "internal/db/queries"
    schema: "internal/db/migrations"
    gen:
      go:
        package: "db"
        out: "internal/db"
        emit_json_tags: true
        emit_empty_slices: true
```

**Step 2: Create initial migration (core tables only for Phase 1)**

`go/internal/db/migrations/001_initial.up.sql`:
```sql
-- Core tables matching Python SQLAlchemy models exactly

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
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
);

CREATE INDEX IF NOT EXISTS ix_session_user_context_project
    ON sessions(user_id, context_id, project_id);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_message_session_created
    ON messages(session_id, created_at);

CREATE TABLE IF NOT EXISTS channel_summaries (
    id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL UNIQUE,
    summary TEXT DEFAULT '',
    summary_cutoff_at DATETIME,
    last_updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS channel_configs (
    id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL UNIQUE,
    guild_id TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'mention',
    configured_by TEXT,
    configured_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS log_entries (
    id TEXT PRIMARY KEY,
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
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
);
```

`go/internal/db/migrations/001_initial.down.sql`:
```sql
DROP TABLE IF EXISTS log_entries;
DROP TABLE IF EXISTS channel_configs;
DROP TABLE IF EXISTS channel_summaries;
DROP TABLE IF EXISTS messages;
DROP TABLE IF EXISTS sessions;
DROP TABLE IF EXISTS projects;
```

**Step 3: Create sqlc query files**

`go/internal/db/queries/projects.sql`:
```sql
-- name: GetProject :one
SELECT * FROM projects WHERE id = ?;

-- name: GetProjectByOwner :one
SELECT * FROM projects WHERE owner_id = ? LIMIT 1;

-- name: CreateProject :one
INSERT INTO projects (id, owner_id, name, created_at, updated_at)
VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
RETURNING *;
```

`go/internal/db/queries/sessions.sql`:
```sql
-- name: GetSession :one
SELECT * FROM sessions WHERE id = ?;

-- name: GetActiveSession :one
SELECT * FROM sessions
WHERE user_id = ? AND context_id = ? AND project_id = ? AND archived != 'true'
ORDER BY last_activity_at DESC
LIMIT 1;

-- name: CreateSession :one
INSERT INTO sessions (id, project_id, user_id, context_id, started_at, last_activity_at)
VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
RETURNING *;

-- name: UpdateSessionActivity :exec
UPDATE sessions SET last_activity_at = CURRENT_TIMESTAMP WHERE id = ?;

-- name: SetSessionSummary :exec
UPDATE sessions SET session_summary = ? WHERE id = ?;
```

`go/internal/db/queries/messages.sql`:
```sql
-- name: GetRecentMessages :many
SELECT * FROM messages
WHERE session_id = ?
ORDER BY created_at DESC
LIMIT ?;

-- name: CreateMessage :one
INSERT INTO messages (session_id, user_id, role, content, created_at)
VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
RETURNING *;

-- name: GetChannelMessages :many
SELECT m.* FROM messages m
JOIN sessions s ON m.session_id = s.id
WHERE s.context_id = ?
ORDER BY m.created_at DESC
LIMIT ?;
```

**Step 4: Create DB connection helper**

`go/internal/db/db.go`:
```go
package db

import (
	"database/sql"
	"fmt"
	"os"

	_ "github.com/mattn/go-sqlite3"
)

// Open opens the database connection.
// Uses DATABASE_URL env var, defaults to SQLite.
func Open() (*sql.DB, error) {
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		dsn = "clara.db"
	}

	driver := "sqlite3"
	// TODO: PostgreSQL detection by prefix

	db, err := sql.Open(driver, dsn)
	if err != nil {
		return nil, fmt.Errorf("open database: %w", err)
	}

	if err := db.Ping(); err != nil {
		return nil, fmt.Errorf("ping database: %w", err)
	}

	return db, nil
}
```

**Step 5: Install sqlc and generate**

Run:
```bash
cd go
go get github.com/mattn/go-sqlite3
go install github.com/sqlc-dev/sqlc/cmd/sqlc@latest
sqlc generate
```
Expected: Go files generated in `go/internal/db/`

**Step 6: Write test**

```go
// go/internal/db/db_test.go
package db

import (
	"database/sql"
	"os"
	"testing"

	_ "github.com/mattn/go-sqlite3"
)

func testDB(t *testing.T) *sql.DB {
	t.Helper()
	db, err := sql.Open("sqlite3", ":memory:")
	if err != nil {
		t.Fatal(err)
	}
	// Apply migration
	schema, err := os.ReadFile("migrations/001_initial.up.sql")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := db.Exec(string(schema)); err != nil {
		t.Fatal(err)
	}
	return db
}

func TestCreateAndGetProject(t *testing.T) {
	database := testDB(t)
	defer database.Close()

	q := New(database)
	ctx := t

	proj, err := q.CreateProject(ctx, CreateProjectParams{
		ID:      "proj-1",
		OwnerID: "user-1",
		Name:    "Test Project",
	})
	if err != nil {
		t.Fatal(err)
	}
	if proj.Name != "Test Project" {
		t.Errorf("project name = %q, want %q", proj.Name, "Test Project")
	}

	got, err := q.GetProject(ctx, "proj-1")
	if err != nil {
		t.Fatal(err)
	}
	if got.OwnerID != "user-1" {
		t.Errorf("owner_id = %q, want %q", got.OwnerID, "user-1")
	}
}
```

**Step 7: Run tests**

Run: `cd go && go test ./internal/db/ -v`
Expected: PASS

**Step 8: Commit**

```bash
git add go/
git commit -m "feat(go): add database schema and sqlc queries [skip-version]"
```

---

### Task 5: LLM Message Types

Port `mypalclara/core/llm/messages.py` and `tools/response.py` to Go with exact parity.

**Files:**
- Create: `go/internal/llm/messages.go`
- Create: `go/internal/llm/messages_test.go`
- Create: `go/internal/llm/tools.go`
- Create: `go/internal/llm/tools_test.go`

**Step 1: Write message tests**

```go
// go/internal/llm/messages_test.go
package llm

import (
	"testing"
)

func TestSystemMessageToOpenAI(t *testing.T) {
	msg := SystemMessage{Content: "You are Clara."}
	got := msg.ToOpenAI()
	if got["role"] != "system" || got["content"] != "You are Clara." {
		t.Errorf("ToOpenAI() = %v", got)
	}
}

func TestUserMessageToOpenAI(t *testing.T) {
	msg := UserMessage{Content: "Hello"}
	got := msg.ToOpenAI()
	if got["role"] != "user" || got["content"] != "Hello" {
		t.Errorf("ToOpenAI() = %v", got)
	}
}

func TestAssistantMessageWithToolCalls(t *testing.T) {
	content := "Let me search."
	msg := AssistantMessage{
		Content: &content,
		ToolCalls: []ToolCall{
			{ID: "tc1", Name: "search", Arguments: map[string]any{"q": "test"}},
		},
	}
	got := msg.ToOpenAI()
	if got["role"] != "assistant" {
		t.Error("role should be assistant")
	}
	tcs, ok := got["tool_calls"].([]map[string]any)
	if !ok || len(tcs) != 1 {
		t.Error("should have 1 tool call")
	}
}

func TestToolResultMessageToOpenAI(t *testing.T) {
	msg := ToolResultMessage{ToolCallID: "tc1", Content: "result"}
	got := msg.ToOpenAI()
	if got["role"] != "tool" || got["tool_call_id"] != "tc1" {
		t.Errorf("ToOpenAI() = %v", got)
	}
}

func TestMessageFromDict(t *testing.T) {
	tests := []struct {
		name string
		dict map[string]any
		role string
	}{
		{"system", map[string]any{"role": "system", "content": "sys"}, "system"},
		{"user", map[string]any{"role": "user", "content": "hi"}, "user"},
		{"assistant", map[string]any{"role": "assistant", "content": "hello"}, "assistant"},
		{"tool", map[string]any{"role": "tool", "tool_call_id": "tc1", "content": "res"}, "tool"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			msg, err := MessageFromDict(tt.dict)
			if err != nil {
				t.Fatal(err)
			}
			if msg.Role() != tt.role {
				t.Errorf("Role() = %q, want %q", msg.Role(), tt.role)
			}
		})
	}
}

func TestMessageFromDictUnknownRole(t *testing.T) {
	_, err := MessageFromDict(map[string]any{"role": "unknown"})
	if err == nil {
		t.Error("expected error for unknown role")
	}
}
```

**Step 2: Write tool tests**

```go
// go/internal/llm/tools_test.go
package llm

import (
	"testing"
)

func TestToolCallToOpenAI(t *testing.T) {
	tc := ToolCall{ID: "tc1", Name: "search", Arguments: map[string]any{"q": "test"}}
	got := tc.ToOpenAIFormat()
	if got["id"] != "tc1" {
		t.Error("id mismatch")
	}
	fn, ok := got["function"].(map[string]any)
	if !ok {
		t.Fatal("function should be a map")
	}
	if fn["name"] != "search" {
		t.Error("name mismatch")
	}
}

func TestToolCallFromOpenAI(t *testing.T) {
	dict := map[string]any{
		"id":   "tc1",
		"type": "function",
		"function": map[string]any{
			"name":      "search",
			"arguments": `{"q":"test"}`,
		},
	}
	tc := ToolCallFromOpenAI(dict)
	if tc.Name != "search" {
		t.Errorf("Name = %q, want %q", tc.Name, "search")
	}
	if tc.Arguments["q"] != "test" {
		t.Errorf("Arguments[q] = %v, want %q", tc.Arguments["q"], "test")
	}
}

func TestToolCallFromOpenAIBadJSON(t *testing.T) {
	dict := map[string]any{
		"id":   "tc1",
		"function": map[string]any{
			"name":      "search",
			"arguments": "not valid json",
		},
	}
	tc := ToolCallFromOpenAI(dict)
	if tc.Name != "search" {
		t.Error("name should still parse")
	}
	if len(tc.Arguments) != 0 {
		t.Error("bad JSON should yield empty args")
	}
}

func TestToolResponseHasToolCalls(t *testing.T) {
	empty := ToolResponse{Content: strPtr("hello")}
	if empty.HasToolCalls() {
		t.Error("empty should not have tool calls")
	}

	withCalls := ToolResponse{
		ToolCalls: []ToolCall{{ID: "1", Name: "test", Arguments: map[string]any{}}},
	}
	if !withCalls.HasToolCalls() {
		t.Error("should have tool calls")
	}
}

func strPtr(s string) *string { return &s }
```

**Step 3: Implement messages.go**

```go
// go/internal/llm/messages.go
package llm

import "fmt"

// Message is the interface all message types implement.
type Message interface {
	Role() string
	ToOpenAI() map[string]any
}

// SystemMessage is a system-level instruction.
type SystemMessage struct {
	Content string
}

func (m SystemMessage) Role() string           { return "system" }
func (m SystemMessage) ToOpenAI() map[string]any {
	return map[string]any{"role": "system", "content": m.Content}
}

// UserMessage is a user-sent message, optionally multimodal.
type UserMessage struct {
	Content string
	Parts   []ContentPart
}

func (m UserMessage) Role() string           { return "user" }
func (m UserMessage) ToOpenAI() map[string]any {
	if len(m.Parts) > 0 {
		parts := make([]map[string]any, len(m.Parts))
		for i, p := range m.Parts {
			parts[i] = p.ToOpenAI()
		}
		return map[string]any{"role": "user", "content": parts}
	}
	return map[string]any{"role": "user", "content": m.Content}
}

// AssistantMessage is an assistant response with optional tool calls.
type AssistantMessage struct {
	Content   *string
	ToolCalls []ToolCall
}

func (m AssistantMessage) Role() string           { return "assistant" }
func (m AssistantMessage) ToOpenAI() map[string]any {
	result := map[string]any{"role": "assistant", "content": m.Content}
	if len(m.ToolCalls) > 0 {
		tcs := make([]map[string]any, len(m.ToolCalls))
		for i, tc := range m.ToolCalls {
			tcs[i] = tc.ToOpenAIFormat()
		}
		result["tool_calls"] = tcs
	}
	return result
}

// ToolResultMessage is the result of executing a tool call.
type ToolResultMessage struct {
	ToolCallID string
	Content    string
}

func (m ToolResultMessage) Role() string           { return "tool" }
func (m ToolResultMessage) ToOpenAI() map[string]any {
	return map[string]any{
		"role":         "tool",
		"tool_call_id": m.ToolCallID,
		"content":      m.Content,
	}
}

// ContentPartType enumerates content part types.
type ContentPartType string

const (
	ContentPartText        ContentPartType = "text"
	ContentPartImageBase64 ContentPartType = "image_base64"
	ContentPartImageURL    ContentPartType = "image_url"
)

// ContentPart is a single part of a multimodal message.
type ContentPart struct {
	Type      ContentPartType
	Text      string
	MediaType string
	Data      string
	URL       string
}

func (p ContentPart) ToOpenAI() map[string]any {
	switch p.Type {
	case ContentPartText:
		return map[string]any{"type": "text", "text": p.Text}
	case ContentPartImageBase64:
		mt := p.MediaType
		if mt == "" {
			mt = "image/jpeg"
		}
		dataURL := fmt.Sprintf("data:%s;base64,%s", mt, p.Data)
		return map[string]any{"type": "image_url", "image_url": map[string]any{"url": dataURL}}
	case ContentPartImageURL:
		return map[string]any{"type": "image_url", "image_url": map[string]any{"url": p.URL}}
	default:
		return map[string]any{"type": "text", "text": ""}
	}
}

// MessageFromDict creates a Message from an OpenAI-format dict.
func MessageFromDict(d map[string]any) (Message, error) {
	role, _ := d["role"].(string)

	switch role {
	case "system":
		content, _ := d["content"].(string)
		return SystemMessage{Content: content}, nil

	case "user":
		content, _ := d["content"].(string)
		return UserMessage{Content: content}, nil

	case "assistant":
		var content *string
		if c, ok := d["content"].(string); ok {
			content = &c
		}
		var toolCalls []ToolCall
		if tcs, ok := d["tool_calls"].([]any); ok {
			for _, tc := range tcs {
				if tcMap, ok := tc.(map[string]any); ok {
					toolCalls = append(toolCalls, ToolCallFromOpenAI(tcMap))
				}
			}
		}
		return AssistantMessage{Content: content, ToolCalls: toolCalls}, nil

	case "tool":
		callID, _ := d["tool_call_id"].(string)
		content, _ := d["content"].(string)
		return ToolResultMessage{ToolCallID: callID, Content: content}, nil

	default:
		return nil, fmt.Errorf("unknown message role: %q", role)
	}
}

// MessagesFromDicts converts a slice of OpenAI-format dicts to Messages.
func MessagesFromDicts(ds []map[string]any) ([]Message, error) {
	msgs := make([]Message, 0, len(ds))
	for _, d := range ds {
		msg, err := MessageFromDict(d)
		if err != nil {
			return nil, err
		}
		msgs = append(msgs, msg)
	}
	return msgs, nil
}
```

**Step 4: Implement tools.go**

```go
// go/internal/llm/tools.go
package llm

import (
	"encoding/json"
	"log"
)

// ToolCall represents a single tool call from an LLM response.
type ToolCall struct {
	ID           string
	Name         string
	Arguments    map[string]any
	RawArguments string
}

// ToOpenAIFormat converts to OpenAI tool_call format.
func (tc ToolCall) ToOpenAIFormat() map[string]any {
	args, _ := json.Marshal(tc.Arguments)
	return map[string]any{
		"id":   tc.ID,
		"type": "function",
		"function": map[string]any{
			"name":      tc.Name,
			"arguments": string(args),
		},
	}
}

// ToResultMessage creates a ToolResultMessage from this call's output.
func (tc ToolCall) ToResultMessage(output string) ToolResultMessage {
	return ToolResultMessage{ToolCallID: tc.ID, Content: output}
}

// ToolCallFromOpenAI creates a ToolCall from an OpenAI tool_call dict.
func ToolCallFromOpenAI(d map[string]any) ToolCall {
	fn, _ := d["function"].(map[string]any)
	argsStr, _ := fn["arguments"].(string)
	name, _ := fn["name"].(string)
	id, _ := d["id"].(string)

	var args map[string]any
	if err := json.Unmarshal([]byte(argsStr), &args); err != nil {
		log.Printf("failed to parse tool call arguments for %s: %v", name, err)
		args = map[string]any{}
	}

	return ToolCall{
		ID:           id,
		Name:         name,
		Arguments:    args,
		RawArguments: argsStr,
	}
}

// ToolResponse is a unified response from an LLM with tool calling support.
type ToolResponse struct {
	Content    *string
	ToolCalls  []ToolCall
	StopReason string
	Raw        any
}

// HasToolCalls returns true if the response contains tool calls.
func (r ToolResponse) HasToolCalls() bool {
	return len(r.ToolCalls) > 0
}

// ToAssistantMessage converts to an AssistantMessage.
func (r ToolResponse) ToAssistantMessage() AssistantMessage {
	tcs := make([]ToolCall, len(r.ToolCalls))
	copy(tcs, r.ToolCalls)
	return AssistantMessage{Content: r.Content, ToolCalls: tcs}
}

// ToolSchema defines a tool's interface for LLM binding.
type ToolSchema struct {
	Name        string         `json:"name"`
	Description string         `json:"description"`
	Parameters  map[string]any `json:"parameters"`
}
```

**Step 5: Run tests**

Run: `cd go && go test ./internal/llm/ -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add go/
git commit -m "feat(go): add LLM message types and tool call structs [skip-version]"
```

---

### Task 6: LLM Config + Tiers

Port `mypalclara/core/llm/config.py` and `tiers.py` to Go.

**Files:**
- Create: `go/internal/llm/config.go`
- Create: `go/internal/llm/tiers.go`
- Create: `go/internal/llm/tiers_test.go`

**Step 1: Write tier tests**

```go
// go/internal/llm/tiers_test.go
package llm

import "testing"

func TestGetModelForTier(t *testing.T) {
	tests := []struct {
		provider string
		tier     ModelTier
		wantHas  string // substring the model should contain
	}{
		{"anthropic", TierHigh, "opus"},
		{"anthropic", TierMid, "sonnet"},
		{"anthropic", TierLow, "haiku"},
		{"openrouter", TierMid, "sonnet"},
	}
	for _, tt := range tests {
		t.Run(tt.provider+"/"+string(tt.tier), func(t *testing.T) {
			got := GetModelForTier(tt.tier, tt.provider)
			if got == "" {
				t.Error("got empty model")
			}
		})
	}
}

func TestGetModelForTierEnvOverride(t *testing.T) {
	t.Setenv("ANTHROPIC_MODEL_HIGH", "my-custom-opus")
	got := GetModelForTier(TierHigh, "anthropic")
	if got != "my-custom-opus" {
		t.Errorf("got %q, want %q", got, "my-custom-opus")
	}
}

func TestGetBaseModel(t *testing.T) {
	t.Setenv("ANTHROPIC_MODEL", "claude-custom")
	got := GetBaseModel("anthropic")
	if got != "claude-custom" {
		t.Errorf("got %q, want %q", got, "claude-custom")
	}
}

func TestGetCurrentTier(t *testing.T) {
	t.Setenv("MODEL_TIER", "high")
	tier := GetCurrentTier()
	if tier == nil || *tier != TierHigh {
		t.Errorf("got %v, want high", tier)
	}
}

func TestGetCurrentTierUnset(t *testing.T) {
	tier := GetCurrentTier()
	if tier != nil {
		t.Errorf("got %v, want nil", tier)
	}
}
```

**Step 2: Implement tiers.go (exact port of Python tiers.py)**

Port `DEFAULT_MODELS` map, `GetModelForTier()`, `GetBaseModel()`, `GetCurrentTier()`, `GetTierInfo()`, `GetToolModel()` — all matching the Python logic exactly including the env var fallback chains.

**Step 3: Implement config.go**

Port `LLMConfig` struct with `FromEnv()` constructor and `WithTier()` method. Same env var mapping as Python.

**Step 4: Run tests**

Run: `cd go && go test ./internal/llm/ -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add go/
git commit -m "feat(go): add LLM config and model tier management [skip-version]"
```

---

### Task 7: Token Counter

Port `mypalclara/core/token_counter.py` to Go.

**Files:**
- Create: `go/internal/llm/tokens.go`
- Create: `go/internal/llm/tokens_test.go`

**Step 1: Write tests**

```go
// go/internal/llm/tokens_test.go
package llm

import "testing"

func TestCountTokens(t *testing.T) {
	tests := []struct {
		text    string
		wantMin int
		wantMax int
	}{
		{"hello world", 1, 10},
		{"", 0, 0},
		{"The quick brown fox jumps over the lazy dog", 5, 15},
	}
	for _, tt := range tests {
		t.Run(tt.text, func(t *testing.T) {
			got := CountTokens(tt.text)
			if got < tt.wantMin || got > tt.wantMax {
				t.Errorf("CountTokens(%q) = %d, want [%d, %d]", tt.text, got, tt.wantMin, tt.wantMax)
			}
		})
	}
}

func TestCountMessageTokens(t *testing.T) {
	msgs := []Message{
		SystemMessage{Content: "You are helpful."},
		UserMessage{Content: "Hello"},
	}
	got := CountMessageTokens(msgs)
	if got < 5 {
		t.Errorf("CountMessageTokens() = %d, want >= 5", got)
	}
}

func TestGetContextWindow(t *testing.T) {
	tests := []struct {
		model string
		want  int
	}{
		{"claude-sonnet-4", 200_000},
		{"gpt-4o-mini", 128_000},
		{"unknown-model", 128_000},
	}
	for _, tt := range tests {
		t.Run(tt.model, func(t *testing.T) {
			got := GetContextWindow(tt.model)
			if got != tt.want {
				t.Errorf("GetContextWindow(%q) = %d, want %d", tt.model, got, tt.want)
			}
		})
	}
}
```

**Step 2: Implement**

Use `github.com/pkoukk/tiktoken-go` for Go tiktoken. Same `cl100k_base` encoding as Python.

```go
// go/internal/llm/tokens.go
package llm

import (
	"strings"

	"github.com/pkoukk/tiktoken-go"
)

var encoder *tiktoken.Tiktoken

func init() {
	enc, err := tiktoken.GetEncoding("cl100k_base")
	if err != nil {
		panic("failed to load cl100k_base encoding: " + err.Error())
	}
	encoder = enc
}

func CountTokens(text string) int {
	if text == "" {
		return 0
	}
	return len(encoder.Encode(text, nil, nil))
}

func CountMessageTokens(msgs []Message) int {
	total := 0
	for _, msg := range msgs {
		content := ""
		switch m := msg.(type) {
		case SystemMessage:
			content = m.Content
		case UserMessage:
			content = m.Content
		case AssistantMessage:
			if m.Content != nil {
				content = *m.Content
			}
		case ToolResultMessage:
			content = m.Content
		}
		total += CountTokens(content) + 4
	}
	return total
}

var contextWindows = map[string]int{
	"claude":  200_000,
	"gpt-4o":  128_000,
	"gpt-4":   128_000,
	"default": 128_000,
}

func GetContextWindow(model string) int {
	lower := strings.ToLower(model)
	for key, size := range contextWindows {
		if key != "default" && strings.Contains(lower, key) {
			return size
		}
	}
	return contextWindows["default"]
}
```

**Step 3: Run tests**

Run: `cd go && go get github.com/pkoukk/tiktoken-go && go test ./internal/llm/ -v`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add go/
git commit -m "feat(go): add token counter with tiktoken [skip-version]"
```

---

### Task 8: LLM Provider Interface + OpenAI Client

Create the Provider interface and the OpenAI-compatible implementation (covers OpenRouter, NanoGPT, custom OpenAI).

**Files:**
- Create: `go/internal/llm/provider.go`
- Create: `go/internal/llm/provider_openai.go`
- Create: `go/internal/llm/provider_openai_test.go`

**Step 1: Define Provider interface**

```go
// go/internal/llm/provider.go
package llm

import "context"

// Provider is the interface all LLM providers implement.
type Provider interface {
	// Complete generates a text response.
	Complete(ctx context.Context, messages []Message, config *LLMConfig) (string, error)

	// CompleteWithTools generates a response that may include tool calls.
	CompleteWithTools(ctx context.Context, messages []Message, tools []ToolSchema, config *LLMConfig) (*ToolResponse, error)

	// Name returns the provider name.
	Name() string
}
```

**Step 2: Implement OpenAI-compatible provider**

Uses `github.com/sashabaranov/go-openai`. Handles OpenRouter, NanoGPT, and custom OpenAI endpoints by swapping the base URL. Converts our `Message` types to go-openai format, calls the API, converts back to `ToolResponse`.

**Step 3: Write tests (with mock or integration test pattern)**

Test message conversion, tool schema conversion, and response parsing. Use table-driven tests. Actual API calls gated behind `OPENAI_API_KEY` env var (skip if not set).

**Step 4: Run tests**

Run: `cd go && go test ./internal/llm/ -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add go/
git commit -m "feat(go): add OpenAI-compatible LLM provider [skip-version]"
```

---

### Task 9: Anthropic Provider

Native Anthropic SDK provider for direct Anthropic API and clewdr proxy support.

**Files:**
- Create: `go/internal/llm/provider_anthropic.go`
- Create: `go/internal/llm/provider_anthropic_test.go`

**Step 1: Implement**

Uses `github.com/anthropics/anthropic-sdk-go`. Converts messages to Anthropic format (system message separate, user/assistant alternating, tool_use/tool_result content blocks). Handles native tool calling.

**Step 2: Write tests**

Test message format conversion (system prompt extraction, content block building, tool result format). Test `ToolResponse` construction from Anthropic response.

**Step 3: Run tests and commit**

```bash
git add go/
git commit -m "feat(go): add native Anthropic LLM provider [skip-version]"
```

---

### Task 10: Provider Registry + Factory

Port the provider selection logic: read `LLM_PROVIDER` env var, create the right provider.

**Files:**
- Create: `go/internal/llm/registry.go`
- Create: `go/internal/llm/registry_test.go`

**Step 1: Implement**

```go
// go/internal/llm/registry.go
package llm

import "fmt"

// GetProvider creates a Provider based on LLMConfig.
func GetProvider(config *LLMConfig) (Provider, error) {
	switch config.Provider {
	case "openrouter", "nanogpt", "openai":
		return NewOpenAIProvider(config)
	case "anthropic":
		return NewAnthropicProvider(config)
	default:
		return nil, fmt.Errorf("unsupported provider: %s", config.Provider)
	}
}

// MakeProvider creates a Provider from environment configuration.
func MakeProvider(tier *ModelTier) (Provider, error) {
	var t ModelTier
	if tier != nil {
		t = *tier
	}
	config := LLMConfigFromEnv(nil, &t, false)
	return GetProvider(config)
}
```

**Step 2: Write tests + run + commit**

```bash
git add go/
git commit -m "feat(go): add provider registry and factory [skip-version]"
```

---

## Summary

| Task | What | Depends On |
|------|------|-----------|
| 1 | Go module scaffolding | None |
| 2 | Config loading | Task 1 |
| 3 | Structured logging | Task 2 |
| 4 | Database schema + sqlc | Task 1 |
| 5 | LLM message types | Task 1 |
| 6 | LLM config + tiers | Task 2, 5 |
| 7 | Token counter | Task 5 |
| 8 | OpenAI provider | Task 5, 6 |
| 9 | Anthropic provider | Task 5, 6 |
| 10 | Provider registry | Task 8, 9 |

After Phase 1, you have: a compiling Go project with config, logging, database, message types, token counting, and working LLM providers (OpenAI + Anthropic) — the foundation for Phase 2 (memory system).
