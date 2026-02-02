# Configuration

Complete reference for all environment variables and configuration options.

## Required Variables

| Variable | Description |
|----------|-------------|
| `DISCORD_BOT_TOKEN` | Discord bot token |
| `OPENAI_API_KEY` | Required for mem0 embeddings |
| `LLM_PROVIDER` | LLM provider: `openrouter`, `nanogpt`, `anthropic`, `openai` |

## LLM Providers

### OpenRouter (Default)

```bash
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your-key
OPENROUTER_MODEL=anthropic/claude-sonnet-4
OPENROUTER_SITE=https://mypalclara.app  # Optional
OPENROUTER_TITLE=Clara  # Optional
```

### Anthropic (Native SDK)

Recommended for Claude proxies like clewdr:

```bash
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-key
ANTHROPIC_MODEL=claude-sonnet-4-5
ANTHROPIC_BASE_URL=https://proxy.example.com  # Optional
```

### NanoGPT

```bash
LLM_PROVIDER=nanogpt
NANOGPT_API_KEY=your-key
NANOGPT_MODEL=moonshotai/Kimi-K2-Instruct-0905
```

### Custom OpenAI-Compatible

```bash
LLM_PROVIDER=openai
CUSTOM_OPENAI_API_KEY=your-key
CUSTOM_OPENAI_BASE_URL=https://api.openai.com/v1
CUSTOM_OPENAI_MODEL=gpt-4o
```

## Model Tiers

### Tier-Specific Models

```bash
# OpenRouter
OPENROUTER_MODEL_HIGH=anthropic/claude-opus-4-5
OPENROUTER_MODEL_MID=anthropic/claude-sonnet-4
OPENROUTER_MODEL_LOW=anthropic/claude-3-5-haiku

# Anthropic
ANTHROPIC_MODEL_HIGH=claude-opus-4-5
ANTHROPIC_MODEL_MID=claude-sonnet-4-5
ANTHROPIC_MODEL_LOW=claude-haiku-4-5

# NanoGPT
NANOGPT_MODEL_HIGH=anthropic/claude-opus-4-5
NANOGPT_MODEL_MID=anthropic/claude-sonnet-4
NANOGPT_MODEL_LOW=anthropic/claude-3-5-haiku

# Custom OpenAI
CUSTOM_OPENAI_MODEL_HIGH=gpt-4-turbo
CUSTOM_OPENAI_MODEL_MID=gpt-4o
CUSTOM_OPENAI_MODEL_LOW=gpt-4o-mini
```

### Auto-Tier Selection

```bash
AUTO_TIER_SELECTION=true  # Enable automatic tier selection
MODEL_TIER=mid  # Default tier when not specified
```

## Memory System

### mem0 Provider

```bash
MEM0_PROVIDER=openrouter  # or anthropic, nanogpt, openai
MEM0_MODEL=openai/gpt-4o-mini
MEM0_API_KEY=override-key  # Optional override
MEM0_BASE_URL=override-url  # Optional override
```

### Vector Store

```bash
# PostgreSQL with pgvector (production)
MEM0_DATABASE_URL=postgresql://user:pass@host:5432/vectors

# Qdrant (development) - uses local directory
# No config needed, uses ./qdrant_data
```

### Graph Store

```bash
ENABLE_GRAPH_MEMORY=true

# Neo4j
GRAPH_STORE_PROVIDER=neo4j
NEO4J_URL=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password

# Kuzu (embedded)
GRAPH_STORE_PROVIDER=kuzu
# Uses ./kuzu_data directory
```

## Database

```bash
# SQLAlchemy (sessions, messages)
DATABASE_URL=postgresql://user:pass@host:5432/clara_main

# SQLite (development) - default
# Uses ./assistant.db
```

## Discord

### Connection

```bash
DISCORD_BOT_TOKEN=your-token
DISCORD_CLIENT_ID=your-client-id  # For invite link
```

### Access Control

```bash
DISCORD_ALLOWED_SERVERS=123,456  # Whitelist servers
DISCORD_ALLOWED_CHANNELS=789,012  # Whitelist channels
DISCORD_ALLOWED_ROLES=345,678  # Role-based access
```

### Behavior

```bash
DISCORD_MAX_MESSAGES=25  # Messages in conversation chain
DISCORD_MAX_TOOL_RESULT_CHARS=50000  # Tool result truncation
DISCORD_STOP_PHRASES="clara stop,stop clara,nevermind"
DISCORD_SUMMARY_AGE_MINUTES=30  # Summarize old messages
DISCORD_CHANNEL_HISTORY_LIMIT=50  # Channel history fetch
```

### Images

```bash
DISCORD_MAX_IMAGE_DIMENSION=1568
DISCORD_MAX_IMAGE_SIZE=4194304  # 4MB
DISCORD_MAX_IMAGES_PER_REQUEST=1
```

### Monitor

```bash
DISCORD_MONITOR_ENABLED=true
DISCORD_MONITOR_PORT=8001
DISCORD_LOG_CHANNEL_ID=123456  # Mirror logs
```

## Gateway

```bash
CLARA_GATEWAY_HOST=127.0.0.1
CLARA_GATEWAY_PORT=18789
CLARA_GATEWAY_SECRET=shared-secret  # Optional auth
CLARA_HOOKS_DIR=./hooks
CLARA_SCHEDULER_DIR=.
```

## Sandbox (Code Execution)

### Mode Selection

```bash
SANDBOX_MODE=auto  # auto, docker, incus, incus-vm, remote
```

### Docker

```bash
DOCKER_SANDBOX_IMAGE=python:3.12-slim
DOCKER_SANDBOX_TIMEOUT=900
DOCKER_SANDBOX_MEMORY=512m
DOCKER_SANDBOX_CPU=1.0
```

### Incus

```bash
INCUS_SANDBOX_IMAGE=images:debian/12/cloud
INCUS_SANDBOX_TYPE=container  # or vm
INCUS_SANDBOX_TIMEOUT=900
INCUS_SANDBOX_MEMORY=512MiB
INCUS_SANDBOX_CPU=1
INCUS_REMOTE=local
```

### Remote Sandbox

```bash
SANDBOX_API_URL=https://sandbox.example.com
SANDBOX_API_KEY=your-key
SANDBOX_TIMEOUT=60
```

## Tool Execution

```bash
TOOL_API_KEY=override-key  # Optional
TOOL_BASE_URL=override-url  # Optional
TOOL_DESC_TIER=high  # Tier for status descriptions
TOOL_DESC_MAX_WORDS=20
```

## Integrations

### Web Search

```bash
TAVILY_API_KEY=your-key
```

### GitHub

```bash
GITHUB_TOKEN=your-personal-access-token
```

### Azure DevOps

```bash
AZURE_DEVOPS_ORG=your-org
AZURE_DEVOPS_PAT=your-pat
AZURE_DEVOPS_PROJECT=optional-default-project
```

### Google Workspace

```bash
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=https://api.example.com/oauth/google/callback
CLARA_API_URL=https://api.example.com
```

### Email Monitoring

```bash
EMAIL_MONITORING_ENABLED=true
EMAIL_ENCRYPTION_KEY=fernet-key  # For IMAP passwords
EMAIL_DEFAULT_POLL_INTERVAL=5  # Minutes
```

### Claude Code

```bash
ANTHROPIC_API_KEY=your-key  # Or use Claude subscription
CLAUDE_CODE_WORKDIR=/path/to/projects
CLAUDE_CODE_MAX_TURNS=10
```

## MCP

```bash
MCP_SERVERS_DIR=.mcp_servers
SMITHERY_API_TOKEN=your-token
```

## Local Storage

```bash
CLARA_FILES_DIR=./clara_files
CLARA_MAX_FILE_SIZE=52428800  # 50MB
```

## Other

```bash
USER_ID=demo-user  # Single-user identifier
DEFAULT_PROJECT="Default Project"
SKIP_PROFILE_LOAD=true  # Skip initial mem0 profile
DEFAULT_TIMEZONE=America/New_York
```

## Cloudflare Access

For endpoints behind Cloudflare tunnels:

```bash
CF_ACCESS_CLIENT_ID=your-client-id
CF_ACCESS_CLIENT_SECRET=your-client-secret
```

## File-Based Configuration

### hooks/hooks.yaml

```yaml
hooks:
  - name: my-hook
    event: gateway:startup
    command: echo "Started"
    timeout: 30
```

### scheduler.yaml

```yaml
tasks:
  - name: cleanup
    type: interval
    interval: 3600
    command: poetry run python cleanup.py
```

### .mcp_servers/

MCP server configurations stored as JSON files.
