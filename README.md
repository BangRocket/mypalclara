# MyPalClara

A personal AI assistant with persistent memory, tool use, and multi-platform support. Her name is Clara.

## Features

- **Gateway Architecture** — Central WebSocket server with thin platform adapters (Discord, Teams, CLI, Web)
- **Web Interface** — React-based knowledge base, chat, graph explorer, and identity management
- **Persistent Memory (Rook)** — Vector search (pgvector/Qdrant) with optional graph relationships (FalkorDB/Kuzu)
- **6 LLM Backends** — OpenRouter, Anthropic, NanoGPT, OpenAI-compatible, Amazon Bedrock, Azure OpenAI
- **Model Tiers** — Dynamic model selection (`!high`, `!mid`, `!low`) with auto-tier based on complexity
- **MCP Plugins** — Install and manage [Model Context Protocol](https://modelcontextprotocol.io/) servers at runtime
- **Tool Use** — Code execution (Docker/Incus sandbox), web search, file operations, browser automation
- **Integrations** — GitHub, Azure DevOps, Google Workspace (OAuth), email monitoring

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      Clara Gateway                           │
│  ┌──────────┐  ┌───────────┐  ┌───────────────────────────┐ │
│  │  Router   │──│ Processor │──│    LLM Orchestrator       │ │
│  │ (queuing) │  │ (context) │  │ (streaming, tool calling) │ │
│  └──────────┘  └───────────┘  └───────────────────────────┘ │
│       │                                  │                   │
│       ▼                                  ▼                   │
│  ┌──────────┐  ┌──────────┐    ┌─────────────────────────┐  │
│  │ Sessions │  │  Rook    │    │    Tool Executor        │  │
│  │          │  │ (memory) │    │ (MCP + built-in tools)  │  │
│  └──────────┘  └──────────┘    └─────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
        │ WebSocket
        ▼
┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐
│  Discord   │  │   Teams    │  │    CLI     │  │    Web     │
│  Adapter   │  │  Adapter   │  │  Adapter   │  │  (FastAPI) │
└────────────┘  └────────────┘  └────────────┘  └────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- [Poetry](https://python-poetry.org/)
- Docker (optional, for sandbox and databases)

### Install

```bash
git clone https://github.com/BangRocket/mypalclara.git
cd mypalclara
poetry install

# Configure environment
cp .env.docker.example .env
# Edit .env with your API keys
```

### Run

```bash
# Gateway with adapters (recommended)
poetry run python -m mypalclara.gateway start
poetry run python -m mypalclara.gateway start --adapter discord

# Or with Docker
docker-compose --profile discord up

# Daemon management
poetry run python -m mypalclara.gateway status
poetry run python -m mypalclara.gateway stop
poetry run python -m mypalclara.gateway restart
```

## Configuration

### Required

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Required for Rook embeddings |
| `LLM_PROVIDER` | `openrouter`, `anthropic`, `nanogpt`, `openai`, `bedrock`, or `azure` |
| `DISCORD_BOT_TOKEN` | For Discord adapter |

### LLM Providers

**OpenRouter** (default):
```bash
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your-key
OPENROUTER_MODEL=anthropic/claude-sonnet-4
```

**Anthropic** (native SDK, supports proxies like clewdr):
```bash
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-key
ANTHROPIC_MODEL=claude-sonnet-4-5
ANTHROPIC_BASE_URL=https://your-proxy.example.com  # Optional
```

**NanoGPT**:
```bash
LLM_PROVIDER=nanogpt
NANOGPT_API_KEY=your-key
NANOGPT_MODEL=moonshotai/Kimi-K2-Instruct-0905
```

**Custom OpenAI-compatible**:
```bash
LLM_PROVIDER=openai
CUSTOM_OPENAI_API_KEY=your-key
CUSTOM_OPENAI_BASE_URL=https://api.openai.com/v1
CUSTOM_OPENAI_MODEL=gpt-4o
```

**Amazon Bedrock**:
```bash
LLM_PROVIDER=bedrock
AWS_REGION=us-east-1
BEDROCK_MODEL=anthropic.claude-3-5-sonnet-20241022-v2:0
# Uses IAM role or AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
```

**Azure OpenAI**:
```bash
LLM_PROVIDER=azure
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_API_KEY=your-key
AZURE_DEPLOYMENT_NAME=your-deployment
```

### Model Tiers

Select models dynamically in Discord via message prefixes:

| Prefix | Tier | Use Case |
|--------|------|----------|
| `!high` / `!opus` | High | Complex reasoning, long-form writing |
| `!mid` / `!sonnet` | Mid (default) | General use |
| `!low` / `!haiku` / `!fast` | Low | Quick answers, simple tasks |

```bash
ANTHROPIC_MODEL_HIGH=claude-opus-4-5
ANTHROPIC_MODEL_MID=claude-sonnet-4-5
ANTHROPIC_MODEL_LOW=claude-haiku-4-5
AUTO_TIER_SELECTION=true  # Auto-select based on message complexity
```

### Optional Features

| Variable | Description |
|----------|-------------|
| `TAVILY_API_KEY` | Web search |
| `GITHUB_TOKEN` | GitHub integration |
| `AZURE_DEVOPS_ORG` / `AZURE_DEVOPS_PAT` | Azure DevOps integration |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google Workspace (OAuth) |
| `ENABLE_GRAPH_MEMORY=true` | Graph relationship tracking (FalkorDB/Kuzu) |
| `SMITHERY_API_TOKEN` | Smithery MCP server registry |
| `SANDBOX_MODE=auto` | Code execution sandbox (docker, incus, incus-vm, auto) |

## Memory System (Rook)

Clara uses Rook for persistent memory with vector search and optional graph storage.

### Memory Types

- **User Memories** — Personal facts, preferences, and context per user
- **Project Memories** — Topic-specific knowledge per project
- **Key Memories** — Important facts always included in context
- **Graph Relations** — Entity relationships (requires `ENABLE_GRAPH_MEMORY=true`)

### Vector Store

Supports pgvector (PostgreSQL) or Qdrant. Configure via:
```bash
ROOK_DATABASE_URL=postgresql://user:pass@host:5432/clara_vectors  # pgvector
# or
QDRANT_URL=http://localhost:6333  # Qdrant
```

### Rook Provider

Rook uses its own LLM for memory extraction (independent from chat):
```bash
ROOK_PROVIDER=openrouter
ROOK_MODEL=openai/gpt-4o-mini
```

### Scripts

```bash
poetry run python scripts/bootstrap_memory.py          # Ingest profile data
poetry run python scripts/bootstrap_memory.py --apply   # Apply to Rook
poetry run python scripts/clear_dbs.py                  # Clear memory (with prompt)
poetry run python scripts/clear_dbs.py --yes --user josh  # Clear specific user
poetry run python scripts/backfill_graph_memory.py      # Build graph from history
```

## MCP Plugin System

Clara can install and manage [MCP servers](https://modelcontextprotocol.io/) at runtime via chat commands.

```
@Clara install the MCP server smithery:exa
@Clara install smithery-hosted:@smithery/notion
@Clara install @modelcontextprotocol/server-everything
```

Per-user isolation, OAuth support for hosted servers, and admin controls for install/uninstall. See [MCP Plugin System](wiki/MCP-Plugin-System.md) for details.

## Gateway

The gateway is a central WebSocket server that handles message processing, LLM orchestration, and tool execution. Platform adapters connect as lightweight clients.

```bash
# Foreground (development)
poetry run python -m mypalclara.gateway --host 127.0.0.1 --port 18789

# Adapter management
poetry run python -m mypalclara.gateway adapter discord status
poetry run python -m mypalclara.gateway adapter discord restart
poetry run python -m mypalclara.gateway logs
```

The gateway supports hooks (event-driven automations) and a task scheduler. See `hooks/hooks.yaml.example` for hook configuration.

## Discord

### Channel Modes

- **Active** — Clara responds to all messages
- **Mention** — Clara responds when mentioned (default)
- **Off** — Clara ignores the channel

Configure with `/clara mode active|mention|off`.

### Features

- Reply chain context (up to `DISCORD_MAX_MESSAGES` messages)
- Image analysis
- Streaming responses (message edits)
- Stop phrases (`@Clara stop`, `@Clara nevermind`)
- Monitor dashboard (port 8001)

## Teams

Clara supports Microsoft Teams via the Bot Framework SDK. Requires Azure Bot resource configuration. See [Teams Adapter](wiki/Teams-Adapter.md) for setup instructions.

## Web Interface

Browser-based UI for managing Clara's knowledge base, chatting, exploring the entity graph, and linking platform identities.

### Features

- **Knowledge Base** — Grid/list views, semantic search, Tiptap block editor, tags, saved filter sets, export/import
- **Chat** — Streaming responses via WebSocket, tool call display, file uploads, syntax highlighting
- **Graph Explorer** — React Flow visualization of FalkorDB entity graph
- **Intentions** — Create and manage standing instructions for Clara
- **Adapter Linking** — Unify identities across Discord, Google, etc. via OAuth2
- **Mobile Responsive** — Collapsible sidebar, responsive layout

### Quick Start

```bash
# Development (two terminals)
poetry run uvicorn mypalclara.web.app:create_app --factory --reload --port 8000
cd web-ui && pnpm dev

# Production (Docker)
docker-compose --profile web up

# Or via script
poetry run clara-web
```

### Configuration

```bash
WEB_SECRET_KEY=your-secret-key
DISCORD_OAUTH_CLIENT_ID=...
DISCORD_OAUTH_CLIENT_SECRET=...
```

See [Web Interface](wiki/Web-Interface.md) for full documentation.

## Production

### Docker Compose

```bash
docker-compose --profile discord up              # Discord standalone
docker-compose --profile gateway --profile adapters up  # Gateway + adapters
docker-compose --profile web up                  # Web interface
```

Services: PostgreSQL (main + vectors), FalkorDB (graph), optional Qdrant and Redis.

### Database

```bash
DATABASE_URL=postgresql://user:pass@host:5432/clara_main
ROOK_DATABASE_URL=postgresql://user:pass@host:5432/clara_vectors
```

```bash
poetry run python scripts/migrate.py           # Run pending migrations
poetry run python scripts/migrate.py status    # Check migration status
```

### Backups

Automated PostgreSQL backups to S3-compatible storage. See `backup_service/`.

## Development

```bash
poetry run ruff check . && poetry run ruff format .  # Lint + format
poetry run pytest                                     # Run tests
```

CalVer versioning: `YYYY.WW.N` — auto-bumped via git hook on `feat:`, `fix:`, `perf:`, `breaking:` commits.

```bash
git config core.hooksPath .githooks  # Enable hooks (run once)
```

## Documentation

- [Wiki](wiki/) — Full documentation (installation, configuration, architecture, troubleshooting)
- [Web Interface](wiki/Web-Interface.md) — Web UI setup, API reference, frontend architecture
- [CLAUDE.md](CLAUDE.md) — Development guide and API reference

## License

[PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/) — Free for non-commercial use. Commercial use requires a separate license.
