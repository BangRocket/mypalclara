# MyPalClara Go Port — Design Document

## Goal

Port the entire MyPalClara Python codebase (~58K LOC, 273 files) to Go with 1:1 feature parity. Every function, feature, and schema must match. The Go version lives alongside the Python version in `go/` at the repo root. Additionally, add an OpenClaw-inspired interactive CLI/TUI using bubbletea.

## Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Location | `go/` at repo root | Clean separation, no namespace conflicts |
| Database | sqlc | Type-safe generated code from SQL, matches schema exactly |
| Migrations | golang-migrate | Same SQL migration files work for both Python and Go |
| LLM clients | OpenAI-compatible + native Anthropic SDK | Covers ~95% of providers with minimal deps |
| WebSocket | coder/websocket | Actively maintained, context-based API |
| HTTP API | net/http (stdlib) | No framework needed for the REST API |
| Discord | discordgo | Standard Go Discord library, full API coverage |
| CLI/TUI | charmbracelet/bubbletea + lipgloss + glamour | Best Go TUI ecosystem |
| Testing | Go-idiomatic table-driven tests | Same behavioral coverage, Go-native style |

## Project Structure

```
go/
├── cmd/
│   ├── clara/                # Gateway binary
│   │   └── main.go
│   └── clara-cli/            # Interactive CLI/TUI binary
│       └── main.go
├── internal/
│   ├── config/               # Config loading, env vars, logging
│   ├── db/                   # sqlc generated code, migrations
│   │   ├── migrations/       # SQL migration files (shared with Python)
│   │   ├── queries/          # sqlc .sql query files
│   │   └── sqlc/             # Generated Go code
│   ├── llm/                  # LLM provider interface + implementations
│   │   ├── provider.go       # Provider interface
│   │   ├── openai.go         # OpenAI-compatible (OpenRouter, NanoGPT, custom)
│   │   ├── anthropic.go      # Native Anthropic SDK
│   │   ├── bedrock.go        # AWS Bedrock
│   │   ├── azure.go          # Azure OpenAI
│   │   ├── messages.go       # Message types
│   │   ├── tools.go          # ToolCall, ToolResponse, ToolSchema
│   │   ├── tiers.go          # Model tier resolution
│   │   └── failover.go       # Cooldown, retry, error classification
│   ├── memory/               # Rook memory system
│   │   ├── manager.go        # MemoryManager facade
│   │   ├── retriever.go      # Memory retrieval + caching
│   │   ├── writer.go         # Memory extraction + storage
│   │   ├── prompt.go         # Prompt builder with Clara's persona
│   │   ├── vector/           # VectorStore interface + Qdrant/pgvector
│   │   ├── graph/            # GraphStore interface + FalkorDB
│   │   ├── embeddings/       # OpenAI embeddings with caching
│   │   └── dynamics/         # FSRS scoring, contradiction detection
│   ├── gateway/              # WebSocket gateway + HTTP API
│   │   ├── server.go         # WebSocket server
│   │   ├── api.go            # HTTP API endpoints
│   │   ├── processor.go      # MessageProcessor
│   │   ├── orchestrator.go   # LLMOrchestrator (tool loop, streaming)
│   │   ├── router.go         # Message routing, debounce, dedup
│   │   ├── protocol.go       # Protocol message types
│   │   ├── loopback.go       # Internal dispatch adapter
│   │   ├── compactor.go      # Context compaction via summarization
│   │   └── tools/            # Tool executor, guard, result guard, permissions
│   ├── adapters/
│   │   ├── base.go           # GatewayClient interface
│   │   └── discord/          # discordgo adapter (streaming edits, voice, etc.)
│   ├── mcp/                  # MCP plugin system
│   │   ├── manager.go        # Server lifecycle, tool discovery
│   │   ├── client.go         # MCP protocol client (stdio + HTTP)
│   │   ├── local.go          # Local server management (subprocess)
│   │   ├── remote.go         # Remote server connections
│   │   ├── oauth.go          # OAuth 2.1 + PKCE
│   │   ├── models.go         # Config models
│   │   └── installer.go      # Smithery package installation
│   ├── sandbox/              # Code execution isolation
│   │   ├── manager.go        # Auto-select Docker vs Incus
│   │   ├── docker.go         # Docker container execution
│   │   └── incus.go          # Incus container/VM execution
│   ├── security/             # Security subsystem
│   │   ├── sandboxing.go     # wrap_untrusted, escape_for_prompt
│   │   ├── permissions.go    # Per-user tool permissions
│   │   ├── injection.go      # Injection scanner
│   │   └── circuit_breaker.go
│   ├── services/
│   │   ├── scheduler/        # Cron + one-shot task scheduler
│   │   ├── email/            # Email monitoring (IMAP/Gmail)
│   │   ├── backup/           # PostgreSQL → S3 backup
│   │   └── proactive/        # ORS proactive messaging engine
│   ├── skills/               # Lazy-loading skill system
│   ├── subagent/             # Sub-agent orchestration
│   ├── tools/                # Built-in tool implementations
│   │   ├── registry.go       # Tool discovery + registration
│   │   ├── files.go          # File operations
│   │   ├── terminal.go       # Shell execution
│   │   ├── browser.go        # Headless browser (chromedp)
│   │   └── memory.go         # Memory visibility/management tools
│   └── cli/                  # Interactive TUI
│       ├── app.go            # Main bubbletea model + update loop
│       ├── chatlog.go        # Chat history component (scrollable)
│       ├── input.go          # Multi-line editor with history + autocomplete
│       ├── output.go         # Streaming markdown renderer
│       ├── toolbox.go        # Tool execution display (colored, collapsible)
│       ├── status.go         # Status line + waiting animation
│       ├── overlay.go        # Modal overlays (pickers, approval prompts)
│       ├── commands.go       # Slash command registry
│       ├── theme.go          # Dark/light theme with auto-detection
│       └── gateway.go        # WebSocket client to gateway
├── pkg/
│   └── types/                # Shared types (if needed externally)
├── go.mod
├── go.sum
├── sqlc.yaml
└── Makefile
```

## Key Interfaces

### LLM Provider

```go
type Provider interface {
    Complete(ctx context.Context, messages []Message, opts ...Option) (string, error)
    CompleteWithTools(ctx context.Context, messages []Message, tools []ToolSchema, opts ...Option) (*ToolResponse, error)
    Stream(ctx context.Context, messages []Message, opts ...Option) (<-chan string, error)
}

type Message interface {
    Role() string
    ToOpenAI() map[string]any
}

type ToolResponse struct {
    Content    string
    ToolCalls  []ToolCall
    StopReason string
    Raw        any
}

type ToolCall struct {
    ID        string
    Name      string
    Arguments map[string]any
}
```

### Gateway Client (Adapter Interface)

```go
type GatewayClient interface {
    Connect(ctx context.Context, url string) error
    Disconnect() error
    SendMessage(msg *protocol.MessageRequest) error
    OnResponse(handler ResponseHandler)
    Capabilities() []string
}
```

### Memory System

```go
type MemoryManager interface {
    FetchContext(ctx context.Context, userID, query string, opts ...FetchOption) (*MemoryContext, error)
    StoreMemory(ctx context.Context, userID string, content string, memType MemoryType) error
    BuildPrompt(ctx context.Context, memories *MemoryContext, history []Message, userMsg string) []Message
    SummarizeSession(ctx context.Context, sessionID string) error
}

type VectorStore interface {
    Search(ctx context.Context, embedding []float32, limit int, filter map[string]any) ([]MemoryItem, error)
    Upsert(ctx context.Context, items []MemoryItem) error
    Delete(ctx context.Context, ids []string) error
}
```

## Database Schema

Same 22 tables as Python. Key tables:

- `projects` — project context
- `sessions` — conversation sessions with context_id, session_summary
- `messages` — individual messages (role, content, created_at)
- `canonical_users` + `platform_links` — cross-platform identity
- `memory_dynamics` + `memory_access_log` — FSRS scoring
- `channel_summaries` — channel context
- `tool_audit_log` — tool execution audit trail
- `proactive_messages` + `proactive_notes` + `proactive_assessments` — ORS engine
- `intentions` — user intention tracking
- `personality_traits` + `personality_trait_history` — personality evolution

Migration files are SQL and shared between Python (Alembic) and Go (golang-migrate).

## CLI/TUI Features

### Layout
```
┌─ Header ──────────────────────────────────────┐
│ clara-cli · ws://127.0.0.1:18789 · mid tier   │
├─ Chat Log ────────────────────────────────────┤
│ [user message - colored bg]                    │
│ [assistant response - streaming markdown]      │
│ ┌─ 🔍 search_memory ✅ ──────────────────┐    │
│ │ query: "relevant context"               │    │
│ │ [user_memories]                         │    │
│ │ - User prefers dark mode                │    │
│ │ ... (12 lines, Ctrl+O to expand)        │    │
│ └─────────────────────────────────────────┘    │
│ [assistant response continued...]              │
├─ Status Line ─────────────────────────────────┤
│ ⠋ kerfuffling · 3.2s | connected              │
├─ Editor ──────────────────────────────────────┤
│ > multi-line input with history                │
└───────────────────────────────────────────────┘
```

### Keyboard Shortcuts
| Key | Action |
|-----|--------|
| Enter | Submit message |
| Alt+Enter | Newline in editor |
| Ctrl+C | Clear input / double-press exit |
| Ctrl+D | Exit (if empty) |
| Ctrl+L | Model picker overlay |
| Ctrl+O | Toggle tool output expand/collapse |
| Esc | Abort active request / dismiss overlay |
| Up/Down | Input history navigation |
| Tab | Slash command autocomplete |

### Slash Commands
`/help`, `/model`, `/session`, `/new`, `/status`, `/abort`, `/tier`, `/exit`

### Features
- Streaming markdown rendering with syntax highlighting (glamour + chroma)
- Tool execution boxes: colored borders (pending=blue, success=green, error=red), collapsible output
- Waiting animation with elapsed time and whimsical phrases
- Dark/light theme auto-detection (COLORFGBG env var)
- `!command` local shell execution with approval prompt
- Session management (list, switch, create)
- Model/tier picker overlay
- Paste detection (burst coalescing)

### Gateway Connection
Connects to the gateway over standard WebSocket protocol — same as Discord/Teams adapters. No special CLI API. Uses `coder/websocket` client matching the server.

## Environment Variables

All existing env vars preserved 1:1. The Go binary reads the same `.env` file and respects the same `OPENAI_API_KEY`, `LLM_PROVIDER`, `ANTHROPIC_*`, `OPENROUTER_*`, `ROOK_*`, `DISCORD_*`, `CLARA_GATEWAY_*` variables.

## Go Dependencies

| Package | Purpose |
|---------|---------|
| `coder/websocket` | WebSocket server + client |
| `bwmarrin/discordgo` | Discord adapter |
| `charmbracelet/bubbletea` | TUI framework |
| `charmbracelet/lipgloss` | TUI styling |
| `charmbracelet/glamour` | Markdown rendering |
| `charmbracelet/bubbles` | TUI components |
| `alecthomas/chroma` | Syntax highlighting |
| `sqlc-dev/sqlc` | SQL → Go code generation |
| `golang-migrate/migrate` | Database migrations |
| `lib/pq` | PostgreSQL driver |
| `mattn/go-sqlite3` | SQLite driver (dev) |
| `pgvector/pgvector-go` | pgvector support |
| `qdrant/go-client` | Qdrant vector store |
| `sashabaranov/go-openai` | OpenAI-compatible client |
| `anthropics/anthropic-sdk-go` | Native Anthropic SDK |
| `aws/aws-sdk-go-v2` | AWS Bedrock |
| `docker/docker` | Docker SDK |
| `joho/godotenv` | .env loading |
| `rs/zerolog` | Structured logging |
| `robfig/cron/v3` | Cron expression parsing |
| `chromedp/chromedp` | Headless browser |
| `emersion/go-imap` | IMAP client |
| `redis/go-redis/v9` | Redis client |

## Implementation Phases

### Phase 1: Foundation
- `go mod init`, project scaffolding
- Config loading + logging (zerolog)
- Database schema + sqlc generation
- LLM provider interface + OpenAI/Anthropic clients
- Message types + format converters
- Token counter

### Phase 2: Core Intelligence
- Memory system (Rook) — vector store, embeddings, retrieval, writer
- Prompt builder with Clara's persona
- MemoryManager facade
- FSRS dynamics
- Session management

### Phase 3: Gateway
- Protocol definitions
- WebSocket server + HTTP API
- MessageProcessor + LLMOrchestrator
- Tool executor + guards + permissions
- Security (sandboxing, injection scanner)
- Loopback adapter + scheduler
- Skills system
- Context compactor

### Phase 4: Adapters + Tools
- Discord adapter (discordgo) — streaming, voice, reactions, threads
- MCP client (local + remote)
- Sandbox (Docker/Incus)
- Built-in tools (files, terminal, browser)
- Sub-agent system

### Phase 5: CLI/TUI
- bubbletea app structure
- Chat log with streaming markdown
- Multi-line editor with history
- Tool execution display
- Slash commands + overlays
- Theme system
- Gateway WebSocket client

### Phase 6: Services
- Proactive messaging (ORS)
- Email monitoring
- Backup service

## Parity Verification

Each phase includes a parity check:
- Run the same inputs through both Python and Go versions
- Compare outputs (LLM responses, tool calls, memory retrieval)
- Verify database state matches
- Confirm protocol compatibility (Go gateway accepts Python adapters and vice versa)
