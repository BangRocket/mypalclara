# External Integrations

**Analysis Date:** 2026-01-27

## APIs & External Services

**Chat LLM Providers:**
- OpenRouter - LLM routing service (default)
  - SDK/Client: `openai` package (OpenAI-compatible)
  - Auth: `OPENROUTER_API_KEY`
  - Models: Configurable via `OPENROUTER_MODEL` (default: anthropic/claude-sonnet-4)
  - Headers: `OPENROUTER_SITE`, `OPENROUTER_TITLE`

- Anthropic - Direct Claude API (native SDK)
  - SDK/Client: `anthropic` package (native)
  - Auth: `ANTHROPIC_API_KEY`
  - Proxy support: `ANTHROPIC_BASE_URL` (for clewdr, internal proxies)
  - Models: `ANTHROPIC_MODEL`, `ANTHROPIC_MODEL_HIGH`, `ANTHROPIC_MODEL_MID`, `ANTHROPIC_MODEL_LOW`
  - Native tool calling (no format conversion needed)

- NanoGPT - Alternative LLM provider
  - SDK/Client: `openai` package (OpenAI-compatible)
  - Auth: `NANOGPT_API_KEY`
  - Models: Configurable via `NANOGPT_MODEL`

- Custom OpenAI-compatible - Flexible endpoint
  - SDK/Client: `openai` package
  - Auth: `CUSTOM_OPENAI_API_KEY`
  - Endpoint: `CUSTOM_OPENAI_BASE_URL`
  - Models: Tier-based (`CUSTOM_OPENAI_MODEL_HIGH`, `CUSTOM_OPENAI_MODEL_MID`, `CUSTOM_OPENAI_MODEL_LOW`)
  - Cloudflare Access: `CF_ACCESS_CLIENT_ID`, `CF_ACCESS_CLIENT_SECRET` (for cloudflared endpoints)

**Memory & Embeddings:**
- OpenAI - Embeddings only (always required)
  - API: text-embedding-3-small (hardcoded in mem0)
  - Auth: `OPENAI_API_KEY` (separate from chat LLM)
  - Used by: mem0 for semantic memory extraction

- Mem0 Provider (independent from chat LLM) - Configurable
  - Options: openrouter, nanogpt, openai, anthropic
  - Config: `MEM0_PROVIDER`, `MEM0_MODEL`, `MEM0_API_KEY`, `MEM0_BASE_URL`
  - Can use different endpoint than chat LLM

**Web Search:**
- Tavily - Web search API
  - Auth: `TAVILY_API_KEY`
  - Integration: Optional, triggers if key is present
  - Used by: Docker sandbox code execution for web search capability

## Data Storage

**Databases:**

**Primary - Session and Model Storage:**
- PostgreSQL 13+ (production) or SQLite 3 (development)
  - Connection: `DATABASE_URL`
  - Client: SQLAlchemy 2.0+
  - Migration tool: Alembic
  - Models: `db/models.py` - Project, Session, Message, ChannelSummary, MCPServer, EmailAccount, EmailRule, EmailAlert

**Memory - Vector Storage:**
- PostgreSQL + pgvector (production) or Qdrant (local dev)
  - Connection: `MEM0_DATABASE_URL`
  - Client: qdrant-client 1.7+, pgvector 0.3+
  - Storage: Vector embeddings from OpenAI text-embedding-3-small
  - Located: `vendor/mem0/` (locally vendored with Anthropic base_url fixes)

**Graph Memory - Optional Relationship Storage:**
- Neo4j 5+ (default if enabled)
  - Connection: `NEO4J_URL`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`
  - Client: neo4j 5.0+
  - Enable: Set `ENABLE_GRAPH_MEMORY=true` and `GRAPH_STORE_PROVIDER=neo4j`
  - Docker host: `bolt://neo4j:7687` (when using docker-compose)

- Kuzu (embedded alternative)
  - No external connection needed
  - Enable: `ENABLE_GRAPH_MEMORY=true`, `GRAPH_STORE_PROVIDER=kuzu`
  - Storage: Local filesystem (config/kuzu_data)
  - Lighter weight than Neo4j

**File Storage:**
- Local filesystem (default)
  - Directory: `CLARA_FILES_DIR` (default: `./clara_files`)
  - Per-user storage: Files organized by user_id
  - Max size: `CLARA_MAX_FILE_SIZE` (default: 50MB)

- S3-compatible storage (optional)
  - Providers: Wasabi, AWS S3, MinIO
  - Enable: `S3_ENABLED=true`
  - Config: `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_REGION`
  - Client: boto3 1.35+
  - Used for: Persistent file storage, backup service integration

**Caching:**
- Redis (optional, for Cortex system)
  - Host: `CORTEX_REDIS_HOST`
  - Port: `CORTEX_REDIS_PORT`
  - Auth: `CORTEX_REDIS_PASSWORD`
  - Used by: Proactive organic response (ORS) system

## Authentication & Identity

**Auth Provider:**
- Custom (Discord user IDs are primary identifiers)
  - User context: Extracted from Discord messages or CLI input
  - Per-user storage: Email connections, OAuth tokens, file storage

**Discord Identity:**
- Discord bot token for server authentication
- User roles for permission checks: `CLARA_ADMIN_ROLE`, configurable roles
- Server/channel/role whitelisting: `DISCORD_ALLOWED_SERVERS`, `DISCORD_ALLOWED_CHANNELS`, `DISCORD_ALLOWED_ROLES`

**Google OAuth (Optional):**
- Provider: Google Cloud
  - Client ID: `GOOGLE_CLIENT_ID`
  - Client Secret: `GOOGLE_CLIENT_SECRET`
  - Redirect URI: `GOOGLE_REDIRECT_URI` (e.g., https://your-api.up.railway.app/oauth/google/callback)
  - Tokens stored per-user in database
  - OAuth implementation: `api_service/` directory
  - Access: Google Sheets, Drive, Docs, Calendar, Gmail

## Platform Integrations

**Discord Bot:**
- Platform: Discord
  - Token: `DISCORD_BOT_TOKEN`
  - Client ID: `DISCORD_CLIENT_ID` (for invite link generation)
  - Framework: py-cord 2.6.1
  - Features:
    - Multi-user support (per Discord user_id)
    - Reply chains (thread context)
    - Streaming responses
    - Image/vision support (Discord attachments, auto-resized)
    - Slash commands
    - Monitor dashboard on port 8001 (HTTP)
    - Console log mirroring to Discord channel: `DISCORD_LOG_CHANNEL_ID`

**GitHub Integration (Optional):**
- Provider: GitHub
  - Auth: `GITHUB_TOKEN` (Personal Access Token)
  - MCP Server: `@modelcontextprotocol/server-github` (official npm package)
  - Features: Repo search, issues, PRs, commits, file operations
  - Activation: Automatically installed if `GITHUB_TOKEN` is set

**Sandbox Code Execution:**

**Docker (Local):**
- Image: `DOCKER_SANDBOX_IMAGE` (default: python:3.12-slim)
- Connection: Docker daemon socket or `DOCKER_HOST`
- Config: `DOCKER_SANDBOX_TIMEOUT` (900s), `DOCKER_SANDBOX_MEMORY` (512m), `DOCKER_SANDBOX_CPU` (1.0)
- Web search: Enabled if `TAVILY_API_KEY` is set

**Incus (Local Lightweight):**
- Mode: `SANDBOX_MODE=incus` (containers) or `incus-vm` (VMs)
- Config: `INCUS_SANDBOX_IMAGE`, `INCUS_SANDBOX_TIMEOUT`, `INCUS_SANDBOX_MEMORY`, `INCUS_SANDBOX_CPU`
- Remote: `INCUS_REMOTE` (default: local)

**Remote Sandbox (VPS):**
- Endpoint: `SANDBOX_API_URL`
- Auth: `SANDBOX_API_KEY`
- Selection: `SANDBOX_MODE=remote` or `auto` (tries remote first, falls back to local)
- Timeout: `SANDBOX_TIMEOUT` (60s)
- Service: Self-hosted at `sandbox_service/` (Docker-based)

## Monitoring & Observability

**Error Tracking:**
- None detected (PostHog handles telemetry, not errors)

**Logs:**
- Console output (stdout/stderr)
- File logging: Optional `logfile` parameter when daemonizing
- Discord channel mirroring: `DISCORD_LOG_CHANNEL_ID` receives all console logs
- Log level: `LOG_LEVEL` env var (default: INFO)
- Logging config: `config/logging.py`

**Telemetry:**
- PostHog 3.0+ (optional)
  - Used for: Usage metrics, feature tracking
  - Can be disabled (it's optional)

## CI/CD & Deployment

**Hosting:**
- Primary: Railway (with PostgreSQL managed databases)
- Fallback: Docker Compose (local or self-hosted)
- Alternative: VPS with Docker/Incus

**CI Pipeline:**
- GitHub Actions (repository configured at `.github/workflows/`)
- Deploy workflows: Promote from stage to main branch
- Release dashboard: Separate service for deployment management (`release_dashboard/`)

**Deployment Services:**
- api_service/ - OAuth callback API for Google/GitHub
- release_dashboard/ - Deployment UI and workflow trigger
- backup_service/ - Automated PostgreSQL backups to S3

## Webhooks & Callbacks

**Incoming:**
- Discord bot - Accepts messages via Discord WebSocket
- Gateway - WebSocket server at port 18789 for adapter connections
  - Auth: Optional shared secret `CLARA_GATEWAY_SECRET`
  - Protocol: Binary WebSocket with adapter registration
  - Message types: Register, MessageRequest, Status, Ping/Pong

- Email monitoring - IMAP polling for incoming emails
  - Accounts: Per-user Gmail (via Google OAuth) or IMAP (encrypted password storage)
  - Poll interval: `EMAIL_DEFAULT_POLL_INTERVAL` (default: 5 minutes)
  - Alerts: Configurable rules, Discord notification

**Outgoing:**
- Gateway processor - Streams LLM responses back to adapter connections
- Discord - Message and embed responses, status updates
- Hooks system - Custom webhook triggers on gateway events
  - Events: gateway:startup, adapter:connected, session:start, tool:start, etc.
  - Execution: Shell commands or Python callables
  - Config file: `hooks/hooks.yaml`

**Scheduler - Task Automation:**
- One-shot tasks
- Interval-based tasks (every N seconds)
- Cron-based tasks
- Config file: `scheduler.yaml`

## MCP Plugin System

**Model Context Protocol (MCP):**
- Official SDK: mcp 1.0+
- Directory: `MCP_SERVERS_DIR` (default: `.mcp_servers/`)
- Installation sources:
  - Smithery registry (local or hosted with OAuth)
  - npm packages
  - GitHub repositories (cloned)
  - Docker images
  - Local paths

**Official MCP Servers (Auto-installed if env vars present):**
- GitHub - `@modelcontextprotocol/server-github` (requires `GITHUB_TOKEN`)
- Playwright - `@playwright/mcp` (browser automation)
- Tavily - `tavily-mcp` (web search, requires `TAVILY_API_KEY`)
- Filesystem - `@modelcontextprotocol/server-filesystem` (file operations)

**Smithery Registry:**
- API: registry.smithery.ai
- Auth: `SMITHERY_API_TOKEN` or `SMITHERY_API_KEY`
- Local servers: Run stdio transport via @smithery/cli
- Hosted servers: Connect via HTTP with OAuth support

## Environment Configuration

**Required env vars:**
- `DISCORD_BOT_TOKEN` - Discord bot authentication
- `OPENAI_API_KEY` - Embeddings (mem0 always uses this)
- `LLM_PROVIDER` - Chat LLM selection (openrouter, nanogpt, openai, anthropic)

**Provider-specific (one required based on LLM_PROVIDER):**
- OpenRouter: `OPENROUTER_API_KEY`
- Anthropic: `ANTHROPIC_API_KEY`
- NanoGPT: `NANOGPT_API_KEY`
- Custom OpenAI: `CUSTOM_OPENAI_API_KEY`

**Secrets location:**
- `.env` file in project root (dev)
- Railway environment variables (production)
- Docker Compose secrets via `.env` file
- Encrypted storage: Email IMAP passwords use Fernet encryption (`EMAIL_ENCRYPTION_KEY`)

## Third-Party Services

**Backup Service:**
- S3-compatible storage (Wasabi default)
- Auto-backup: Daily at 3 AM UTC (Railway cron)
- Retention: `BACKUP_RETENTION_DAYS` (default: 7)
- Respawn protection: `RESPAWN_PROTECTION_HOURS` (default: 23)

**Email Monitoring Service (Optional):**
- Gmail via Google OAuth (reuses Google integration)
- IMAP for other providers (iCloud, Outlook, etc.)
- Encryption key: `EMAIL_ENCRYPTION_KEY` (Fernet)
- Alert channel: Discord (configurable per user)

**Browser Automation:**
- Playwright 1.49+ - Accessibility tree access
- Supports: Chrome, Firefox, WebKit, Microsoft Edge
- Via MCP server: `@playwright/mcp`

---

*Integration audit: 2026-01-27*
