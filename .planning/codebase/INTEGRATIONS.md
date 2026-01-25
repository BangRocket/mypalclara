# External Integrations

**Analysis Date:** 2026-01-24

## APIs & External Services

**LLM Chat Providers:**
- **OpenRouter** - Multi-provider LLM routing
  - SDK/Client: `openai` package (OpenAI-compatible API)
  - Config: `LLM_PROVIDER=openrouter`
  - Auth: `OPENROUTER_API_KEY`
  - Endpoint: `https://openrouter.ai/api/v1`
  - Models: Can use any model via `OPENROUTER_MODEL` (default: `anthropic/claude-sonnet-4`)
  - Headers: `OPENROUTER_SITE` and `OPENROUTER_TITLE` for tracking

- **Anthropic (Native)** - Direct Claude API with native tool calling
  - SDK/Client: `anthropic` package (native SDK)
  - Config: `LLM_PROVIDER=anthropic`
  - Auth: `ANTHROPIC_API_KEY`
  - Models: `claude-opus-4-5`, `claude-sonnet-4-5`, `claude-haiku-4-5` (tier-based)
  - Base URL: `ANTHROPIC_BASE_URL` for proxies like clewdr
  - Location: `clara_core/llm.py` (lines 160-180)

- **NanoGPT** - OpenAI-compatible API
  - SDK/Client: `openai` package
  - Config: `LLM_PROVIDER=nanogpt`
  - Auth: `NANOGPT_API_KEY`
  - Endpoint: `https://nano-gpt.com/api/v1`
  - Model: `NANOGPT_MODEL` (default: `moonshotai/Kimi-K2-Instruct-0905`)

- **Custom OpenAI-Compatible** - Generic OpenAI API endpoint
  - SDK/Client: `openai` package
  - Config: `LLM_PROVIDER=openai`
  - Auth: `CUSTOM_OPENAI_API_KEY`
  - Endpoint: `CUSTOM_OPENAI_BASE_URL` (default: `https://api.openai.com/v1`)
  - Model: `CUSTOM_OPENAI_MODEL` (default: `gpt-4o`)

**Memory Extraction (Independent):**
- **Mem0 Provider** - Uses different LLM than chat for memory extraction
  - Providers: openrouter, nanogpt, openai, anthropic (independent selection)
  - Config: `MEM0_PROVIDER`, `MEM0_MODEL`, `MEM0_API_KEY`, `MEM0_BASE_URL`
  - Default: OpenRouter with `openai/gpt-4o-mini`
  - Location: `vendor/mem0/` (vendored with `anthropic_base_url` fix)

**Web Search:**
- **Tavily** - Web search API
  - SDK/Client: Direct HTTP via `httpx`
  - Auth: `TAVILY_API_KEY`
  - Integration: `clara_core/tools.py` (search tool)

**Discord:**
- **Discord Bot API** - Discord bot integration
  - SDK/Client: `py-cord` 2.6.1
  - Auth: `DISCORD_BOT_TOKEN`, `DISCORD_CLIENT_ID`
  - Features: Slash commands, message context, reactions, embeds
  - Config: `DISCORD_MAX_MESSAGES`, `DISCORD_SUMMARY_AGE_MINUTES`, `DISCORD_CHANNEL_HISTORY_LIMIT`
  - Whitelist: `DISCORD_ALLOWED_SERVERS`, `DISCORD_ALLOWED_CHANNELS`, `DISCORD_ALLOWED_ROLES`
  - Location: `discord_bot.py` (main entry point)

## Data Storage

**Databases:**

**Primary Relational (Sessions, Projects, Messages):**
- **SQLite** (Development)
  - Default: `assistant.db` local file
  - Used when `DATABASE_URL` not set
  - SQLAlchemy ORM: `db/models.py`

- **PostgreSQL** (Production)
  - Connection: `DATABASE_URL` (e.g., `postgresql://user:pass@host:5432/dbname`)
  - Client: `sqlalchemy` ORM with `psycopg2-binary` driver
  - Tables: `projects`, `sessions`, `messages`, `channel_summaries`, `channel_configs`, `log_entries`
  - Docker: Service `postgres` in `docker-compose.yml` (port 5442)

**Memory Vectors (mem0):**
- **Qdrant** (Development, local)
  - Default: In-memory or local file-based
  - Used when `MEM0_DATABASE_URL` not set
  - Client: `qdrant-client` 1.7.0+

- **PostgreSQL + pgvector** (Production)
  - Connection: `MEM0_DATABASE_URL`
  - Extension: `pgvector` for vector similarity search
  - Client: `pgvector` adapter with SQLAlchemy
  - Docker: Service `postgres-vectors` in `docker-compose.yml` (port 5443)
  - Stores: Embedding vectors, memory nodes, relationships

**Graph Database (Optional):**
- **Neo4j** - Relationship and context graphs
  - Connection: `NEO4J_URL`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`
  - Client: `neo4j` Python driver
  - Enabled: `ENABLE_GRAPH_MEMORY=true`
  - Use case: Optional relationship tracking (disabled by default)

- **Kuzu** - Embedded graph alternative
  - Enabled: `ENABLE_GRAPH_MEMORY=true` with `GRAPH_STORE_PROVIDER=kuzu`
  - Client: `kuzu` package
  - No external server needed (embedded)

**File Storage:**
- **Local Filesystem**
  - Location: `CLARA_FILES_DIR` (default: `./clara_files`)
  - Uses: User file persistence, Discord attachment saves
  - Manager: `storage/local_files.py`
  - Max file size: `CLARA_MAX_FILE_SIZE` (default: 50MB)

- **S3-Compatible Storage** (Optional)
  - Services: Wasabi, AWS S3, DigitalOcean Spaces
  - Client: `boto3` 1.35.0+
  - Config: `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_REGION`
  - Use case: Remote file backup and scaling

**Caching:**
- None explicitly configured (in-memory LRU caches via `functools.lru_cache` in code)

## Authentication & Identity

**Auth Provider:**
- **Custom-built with OAuth 2.0** (planned integration)
  - Google OAuth support for Workspace integration
  - Config: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
  - Tokens: Stored in database (encrypted per-user)

**Discord Authentication:**
- Discord bot token: `DISCORD_BOT_TOKEN`
- OAuth not needed (bot operates on token directly)

**Email Authentication (IMAP):**
- Email provider accounts (Gmail, iCloud, Outlook)
- IMAP credentials: Encrypted with Fernet (`EMAIL_ENCRYPTION_KEY`)
- Client: `imap-tools` 1.11.0+
- Location: `email_service/` and `email_monitor.py`

## Monitoring & Observability

**Error Tracking:**
- None detected (no Sentry, Rollbar, or equivalent)

**Logs:**
- Console logging with rotating file handlers
- Config: `config/logging.py`
- Levels: `LOG_LEVEL` environment variable
- Discord mirroring: Optional `DISCORD_LOG_CHANNEL_ID` (logs sent to Discord channel)

**Telemetry:**
- PostHog - Analytics and feature tracking
  - Client: `posthog` 3.0.0+
  - Used for: Feature usage, performance metrics
  - Config: Via environment variables in docker-compose

**Monitoring Dashboard:**
- **Discord Monitor** - Real-time Discord bot status
  - Port: `DISCORD_MONITOR_PORT` (default: 8001)
  - Enabled: `DISCORD_MONITOR_ENABLED` (default: true)
  - Framework: FastAPI (embedded in `discord_bot.py`)
  - Features: Bot status, message logs, user stats
  - Location: `discord_bot.py` (FastAPI app setup)

## CI/CD & Deployment

**Hosting:**
- **Railway.app** (primary deployment target)
  - Config: `.env.railway`, `railway.toml`
  - Services: Discord bot, PostgreSQL databases
  - Auto-version: Git hooks bump version in CalVer format (YYYY.WW.N)
  - Dockerfile: `Dockerfile.discord`

- **Docker Compose** (local development and self-hosted)
  - Orchestrates: PostgreSQL, pgvector, Discord bot
  - Profiles: discord, postgres for selective startup
  - Location: `docker-compose.yml`

**Git Hooks:**
- `.githooks/` directory contains version bumping hooks
- Setup: `git config core.hooksPath .githooks`
- Script: `scripts/bump_version.py`

**Version Management:**
- Format: CalVer `YYYY.WW.N` (Year.Week.Build)
- Storage: `VERSION` file (synced to `pyproject.toml`)
- Auto-bump: After each commit (skip with `[skip-version]` tag)

## Environment Configuration

**Required env vars (Critical):**
- `OPENAI_API_KEY` - Always needed for mem0 embeddings (text-embedding-3-small)
- `LLM_PROVIDER` - Chat provider selection (openrouter, nanogpt, openai, anthropic)
- `DISCORD_BOT_TOKEN` - Discord bot authentication

**Provider-Specific Keys:**
- OpenRouter: `OPENROUTER_API_KEY`
- Anthropic: `ANTHROPIC_API_KEY`
- NanoGPT: `NANOGPT_API_KEY`
- Custom OpenAI: `CUSTOM_OPENAI_API_KEY`

**Database:**
- `DATABASE_URL` - PostgreSQL connection (optional, defaults to SQLite)
- `MEM0_DATABASE_URL` - Vector database (optional, defaults to Qdrant)

**Optional Keys:**
- `TAVILY_API_KEY` - Web search
- `GITHUB_TOKEN` - GitHub integration
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` - Google Workspace
- `AZURE_DEVOPS_ORG`, `AZURE_DEVOPS_PAT` - Azure DevOps
- `SANDBOX_API_URL`, `SANDBOX_API_KEY` - Remote code sandbox

**Secrets location:**
- Development: `.env` file (git-ignored)
- Production: Railway.app environment variables
- Encrypted storage: Email passwords (Fernet encryption with `EMAIL_ENCRYPTION_KEY`)

## Webhooks & Callbacks

**Incoming Webhooks:**
- None detected in core application

**Outgoing Webhooks:**
- Discord message responses (via bot token)
- Organic Response System can trigger proactive Discord messages
- Location: `organic_response_system.py`

**OAuth Callbacks:**
- Google OAuth redirect: Planned integration point
- MCP OAuth: Hosted Smithery servers use OAuth (handled in `clara_core/mcp/oauth.py`)

## MCP Plugin System

**Smithery Registry Integration:**
- **Search:** `smithery_search` tool
- **Install Sources:**
  - Smithery local (stdio transport): `smithery:e2b`
  - Smithery hosted (HTTP + OAuth): `smithery-hosted:@smithery/notion`
  - npm packages: `@modelcontextprotocol/server-everything`
  - GitHub repos: `github.com/user/mcp-server`
  - Docker images: `ghcr.io/user/mcp-server:latest`
  - Local paths: `/path/to/mcp-server`

- **Auth:** `SMITHERY_API_TOKEN` or `SMITHERY_API_KEY` for Smithery registry access

**MCP Server Management:**
- Location: `clara_core/mcp/manager.py` (MCPServerManager singleton)
- Config storage: `.mcp_servers/` directory (JSON configs)
- Types: Local (stdio) and Remote (HTTP)
- Tools: Namespaced as `{server_name}__{tool_name}`
- Features: Hot-reload, OAuth support, auto-restart

## Code Execution Sandbox

**Local Docker Sandbox:**
- Client: `docker` 7.0.0+ package
- Image: `DOCKER_SANDBOX_IMAGE` (default: `python:3.12-slim`)
- Config: `DOCKER_SANDBOX_TIMEOUT`, `DOCKER_SANDBOX_MEMORY`, `DOCKER_SANDBOX_CPU`
- Location: `sandbox/docker.py`

**Remote Sandbox (VPS):**
- Client: Custom HTTP client in `sandbox/remote_client.py`
- Auth: `SANDBOX_API_KEY`
- Endpoint: `SANDBOX_API_URL`
- Timeout: `SANDBOX_TIMEOUT`
- Mode selection: `SANDBOX_MODE` (local, remote, auto)

**Unified Manager:**
- Location: `sandbox/manager.py` (auto-selects backend)
- Selection: Remote if configured, falls back to local Docker

## Claude Code Integration

**SDK:**
- Package: `claude-agent-sdk` 0.1.18+
- Authentication: CLI login or `ANTHROPIC_API_KEY`
- Working directory: `CLAUDE_CODE_WORKDIR` (configurable)
- Max turns: `CLAUDE_CODE_MAX_TURNS` (default: 10)
- Tools: `claude_code`, `claude_code_status`, `claude_code_set_workdir`
- Location: `discord_bot.py` (tool integration)

## Email Integration

**Providers:**
- **Gmail** - Via Google OAuth (when Workspace integration complete)
- **IMAP** - Generic IMAP servers (iCloud, Outlook, etc.)
  - Client: `imap-tools` 1.11.0+
  - Encryption: Fernet-encrypted credentials

**Monitoring:**
- Location: `email_service/monitor.py` and `email_monitor.py`
- Credentials: `email_service/credentials.py`
- Rules engine: `email_service/rules_engine.py`
- Presets: `email_service/presets.py`
- Configuration: `EMAIL_MONITORING_ENABLED`, `EMAIL_ENCRYPTION_KEY`

**Discord Integration:**
- Alert channel: `DISCORD_LOG_CHANNEL_ID` for alerts
- Notifications: Per-user or channel-wide

## Graph Memory (Optional)

**Neo4j:**
- Connection: `NEO4J_URL`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`
- Driver: `neo4j` 5.0+ Python driver
- Use: Relationship tracking between entities
- Enable: `ENABLE_GRAPH_MEMORY=true`

**Kuzu:**
- Type: Embedded graph database
- No external server required
- Enable: `ENABLE_GRAPH_MEMORY=true` with `GRAPH_STORE_PROVIDER=kuzu`

## Cloudflare Access

**Service Tokens (for cloudflared tunnels):**
- Client ID: `CF_ACCESS_CLIENT_ID`
- Client Secret: `CF_ACCESS_CLIENT_SECRET`
- Used for: Endpoints behind Cloudflare Access
- Implementation: `clara_core/llm.py` (_get_cf_access_headers)

---

*Integration audit: 2026-01-24*
