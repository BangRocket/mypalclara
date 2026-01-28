# Technology Stack

**Analysis Date:** 2026-01-27

## Languages

**Primary:**
- Python 3.11+ - Core platform, bot, and services
- JavaScript/TypeScript - MCP servers (npm packages)
- SQL - Database queries

**Secondary:**
- YAML - Configuration files (docker-compose, hooks, scheduler)
- Bash - Deployment and utility scripts

## Runtime

**Environment:**
- Python 3.11 to 3.13 (from `pyproject.toml`: `^3.11,<3.14`)

**Package Manager:**
- Poetry (v1.x) - Dependency management
- Lockfile: `poetry.lock` present

**Node.js/npm** - For MCP (Model Context Protocol) servers installation

## Frameworks

**Core:**
- FastAPI 0.115+ - REST/WebSocket server framework
- discord.py (py-cord 2.6.1) - Discord bot framework
- SQLAlchemy 2.0+ - ORM for database models
- Alembic 1.18+ - Database migrations

**LLM Backends:**
- Anthropic SDK 0.40+ - Native Claude API (with base_url proxy support)
- OpenAI SDK 1.42+ - OpenAI/OpenRouter/custom endpoint compatibility
- HuggingFace Hub 0.26+ - Model access

**Memory System:**
- vendor/mem0 (locally vendored) - Semantic memory with Qdrant/pgvector storage
- mem0 Memory class - Core memory abstraction with vector embeddings
- Qdrant 1.7+ - Vector database for local dev
- pgvector 0.3+ - PostgreSQL vector extension for production

**Graph Memory (Optional):**
- Neo4j 5.0+ - Graph database for relationship tracking
- Kuzu 0.9+ - Embedded graph alternative
- langchain-neo4j 0.4+ - Neo4j integration

**Testing:**
- pytest 8.0+ - Test runner
- pytest-asyncio 0.24+ - Async test support

**Build/Dev:**
- Ruff 0.8+ - Linter and formatter
- Uvicorn 0.38+ - ASGI web server
- Watchdog 4.0+ - File system monitoring

## Key Dependencies

**Critical:**
- `sqlalchemy` 2.0+ - ORM/database abstraction
- `pydantic` 2.0+ - Data validation (required by mem0)
- `anthropic` 0.40+ - Claude API with native tool calling
- `py-cord` 2.6.1 - Discord bot integration
- `websockets` 15.0+ - WebSocket server for gateway

**Infrastructure:**
- `docker` 7.0+ - Docker daemon interaction for sandbox
- `boto3` 1.35+ - S3-compatible storage (Wasabi, AWS)
- `psycopg2-binary` 2.9.9+ - PostgreSQL driver
- `qdrant-client` 1.7+ - Vector database client (local dev)
- `pgvector` 0.3+ - PostgreSQL vector extension support

**Integration/Tools:**
- `neo4j` 5.0+ - Graph database driver
- `rank-bm25` 0.2+ - BM25 ranking for graph search
- `requests` 2.32.5+ - HTTP library
- `httpx` 0.28+ - Async HTTP client (web search)
- `playwright` 1.49+ - Browser automation
- `imap-tools` 1.11+ - Email/IMAP support
- `mcp` 1.0+ - Official MCP (Model Context Protocol) SDK
- `gitpython` 3.1+ - Git operations for MCP repo cloning

**Utilities:**
- `python-dotenv` 1.0+ - Environment variable loading
- `pillow` 11.0+ - Image processing (Discord vision)
- `vaderSentiment` 3.3.2+ - Sentiment analysis
- `posthog` 3.0+ - Telemetry
- `prompt-toolkit` 3.0.52+ - CLI interface
- `rich` 14.0+ - Terminal formatting
- `pytz` 2024.1+ - Timezone handling
- `claude-agent-sdk` 0.1.18+ - Claude Code integration

## Configuration

**Environment:**
- `.env` files - Configuration via environment variables (see CLAUDE.md)
- `dotenv.load_dotenv()` - Loads `.env` on startup in `discord_bot.py`

**Key configs required:**
- `DISCORD_BOT_TOKEN` - Discord bot token
- `OPENAI_API_KEY` - Required for embeddings (mem0 always uses OpenAI text-embedding-3-small)
- `LLM_PROVIDER` - Chat LLM provider selection (openrouter, nanogpt, openai, anthropic)
- Provider-specific keys (OPENROUTER_API_KEY, ANTHROPIC_API_KEY, etc.)
- `DATABASE_URL` - PostgreSQL connection (defaults to SQLite if not set)
- `MEM0_DATABASE_URL` - PostgreSQL with pgvector for mem0 (defaults to Qdrant if not set)

**Build:**
- `pyproject.toml` - Poetry project configuration with all dependencies
- `alembic.ini` - Database migration configuration
- `docker-compose.yml` - Service orchestration (PostgreSQL, Neo4j, gateway, Discord bot)
- `Dockerfile.discord` - Discord bot container
- `Dockerfile.gateway` - Gateway service container

**Development:**
- `.env.local` or `.env.docker.example` - Local development configuration
- `.ruff.toml` in `pyproject.toml` - Linter configuration
- Line length: 120 characters

## Platform Requirements

**Development:**
- Python 3.11+ (verified at runtime)
- Poetry package manager
- Docker (optional, for sandbox code execution)
- Node.js + npm (optional, for MCP server installation)

**Production:**
- PostgreSQL 13+ (recommended, replaces SQLite)
- pgvector extension enabled on PostgreSQL (for mem0 vectors)
- Neo4j 5+ (optional, if graph memory enabled)
- Docker daemon (optional, for code sandbox)
- S3-compatible storage (Wasabi, AWS S3) - optional for file storage
- Access to LLM provider API endpoints (OpenRouter, Anthropic, OpenAI, NanoGPT)

**Deployment Targets:**
- Railway (primary cloud deployment)
- Docker Compose (local multi-service)
- Self-hosted VPS (with Docker or Incus)

## Optional Features

**Code Execution Sandbox:**
- Docker 7.0+ - Local container-based sandbox
- Incus containers/VMs - Alternative sandbox option
- Remote VPS - Via SANDBOX_API_URL endpoint

**File Storage:**
- S3-compatible endpoints - Wasabi, AWS S3, MinIO
- Local filesystem - Default fallback

**Monitoring:**
- PostHog - Telemetry (optional, can be disabled)
- Discord log channel mirroring - Console logs to Discord channel

## Versioning

- CalVer format: `YYYY.WW.N` (Year.Week.Build)
- Stored in `VERSION` file at project root
- Auto-bumped after each commit via `.githooks/post-commit`
- Synced to `pyproject.toml`

---

*Stack analysis: 2026-01-27*
