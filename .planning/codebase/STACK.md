# Technology Stack

**Analysis Date:** 2026-01-24

## Languages

**Primary:**
- Python 3.11+ - Core bot logic, API services, memory management

**Secondary:**
- TypeScript/JavaScript - MCP server development, future web UI components

## Runtime

**Environment:**
- Python 3.11-3.13 (specified in `pyproject.toml`: `^3.11,<3.14`)

**Package Manager:**
- Poetry (dependency management and packaging)
- Lockfile: `poetry.lock` (present)

## Frameworks

**Core Application:**
- FastAPI 0.115.0+ - Lightweight async API framework for endpoints and webhooks
- Uvicorn 0.38.0+ - ASGI server (with standard extras for full HTTP/2 support)

**Discord Integration:**
- py-cord 2.6.1 - Discord.py fork with modern slash command support

**LLM Abstraction:**
- openai 1.42.0+ - OpenAI SDK used for OpenRouter, NanoGPT, and custom OpenAI-compatible endpoints
- anthropic 0.40.0+ - Anthropic SDK for native Claude API (preferred for Claude proxies like clewdr)

**Memory System:**
- Vendored mem0 (in `vendor/mem0/`) - Semantic memory system with fixes for `anthropic_base_url` support
- pydantic 2.0+ - Configuration validation and data models
- huggingface_hub 0.26.0+ - HuggingFace model integration

**Database:**
- SQLAlchemy 2.0+ - ORM for relational data (Projects, Sessions, Messages, ChannelSummary, ChannelConfig)
- psycopg2-binary 2.9.9+ - PostgreSQL adapter
- pgvector 0.3.0+ - Vector support for mem0 memory extraction in PostgreSQL

**Vector Stores:**
- qdrant-client 1.7.0+ - Vector database for local development (can switch to pgvector in production)

**Graph Database (Optional):**
- neo4j 5.0+ - Graph database for relationship tracking (when `ENABLE_GRAPH_MEMORY=true`)
- kuzu 0.9.0+ - Embedded graph database alternative (when `GRAPH_STORE_PROVIDER=kuzu`)

**Sandbox Execution:**
- docker 7.0.0+ - Docker client for local code execution sandboxes
- Supports remote sandbox via HTTP API (for VPS-based execution)

**Code Execution & Automation:**
- claude-agent-sdk 0.1.18+ - Claude Code agent integration for autonomous coding tasks
- playwright 1.49.0+ - Browser automation for web interactions

**MCP Plugin System:**
- mcp 1.0.0+ - Official Model Context Protocol SDK for plugin servers
- gitpython 3.1.0+ - Git operations (cloning MCP repos from GitHub)

**Utilities:**
- requests 2.32.5+ - HTTP library for API calls
- httpx 0.28.0+ - Async HTTP client for web search
- python-dotenv 1.0.1+ - Environment variable loading
- pillow 11.0.0+ - Image processing for vision resizing/compression
- vaderSentiment 3.3.2+ - Sentiment analysis for emotional continuity
- watchdog 4.0.0+ - File system watching (hot-reload for MCP servers)
- imessage-reader 0.6.1+ - iMessage database integration
- imap-tools 1.11.0+ - IMAP email access
- posthog 3.0.0+ - Telemetry collection
- pytz 2024.1+ - Timezone handling
- boto3 1.35.0+ - S3-compatible storage (Wasabi, AWS)

## Configuration

**Environment:**
- `.env` file (development, with example at `.env.example`)
- `.env.docker.example` - Docker-specific configuration template
- `.env.railway` - Railway.app deployment config
- `.env.remote` - Remote sandbox configuration
- Environment variables loaded via `python-dotenv` before application startup

**Build:**
- `pyproject.toml` - Poetry configuration with all dependencies and metadata
- `docker-compose.yml` - Multi-service orchestration (PostgreSQL, pgvector, Discord bot)
- `Dockerfile.discord` - Docker image for Discord bot deployment
- `.gitignore` - Standard Python/Node.js exclusions

**Code Quality:**
- Ruff 0.8+ - Fast Python linter and formatter
  - Line length: 120 characters
  - Target version: Python 3.11
  - Excludes: `vendor`, `.venv`, `__pycache__`
  - Rules: E (errors), F (Pyflakes), I (isort)
  - Ignores: E501 (long lines), E402 (module imports), E741 (ambiguous names), F401 (unused imports), F841 (unused variables)
  - Per-file ignores: `__init__.py` (F401), `tools/*.py` and `sandbox/*.py` (E501)

## Platform Requirements

**Development:**
- Python 3.11+ interpreter
- Poetry for dependency management
- Docker (optional, for local code sandbox)
- Git (required for MCP server installation from GitHub)

**Production:**
- PostgreSQL 13+ (recommended for data persistence)
- PostgreSQL with pgvector extension (for mem0 vector storage)
- Docker (optional, if using local sandbox mode)
- Discord bot token from Discord Developer Portal
- LLM API keys (OpenAI, Anthropic, OpenRouter, or compatible endpoint)

**Optional Services:**
- Neo4j 5.0+ or Kuzu (for graph memory relationships)
- Remote sandbox service (self-hosted or third-party)
- S3-compatible storage (Wasabi, AWS S3, or DigitalOcean Spaces)
- Tavily API (for web search capabilities)
- GitHub API (for repository integration)
- Google OAuth (for Workspace integration)

---

*Stack analysis: 2026-01-24*
