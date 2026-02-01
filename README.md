# MyPalClara

A personal AI assistant platform with persistent memory, extensible plugin system, and multi-channel support. The assistant's name is Clara.

## Features

- **Multi-Channel Support** - Discord, Slack, Telegram, CLI, and more via the channel plugin system
- **Gateway Architecture** - Central WebSocket hub for message processing and LLM orchestration
- **Persistent Memory** - User and project memories via [mem0](https://github.com/mem0ai/mem0) with vector search
- **Plugin System** - Extensible architecture with lifecycle hooks and tool registration
- **MCP Integration** - Install and use tools from external MCP servers
- **Code Execution** - Sandboxed Python/Bash via Docker, Incus, or remote VPS
- **Web Search** - Real-time web search via Tavily
- **File Management** - Local file storage with S3 sync support
- **Integrations** - GitHub, Azure DevOps, Google Workspace, email monitoring
- **Claude Code** - Delegate complex coding tasks to Claude Code agent
- **Multiple LLM Backends** - OpenRouter, NanoGPT, Anthropic, or custom OpenAI-compatible endpoints
- **Model Tiers** - Dynamic model selection (`!high`, `!mid`, `!low`)

## Quick Start

### Prerequisites

- Python 3.11+ (< 3.14)
- [Poetry](https://python-poetry.org/)
- Docker (optional, for code execution sandbox)

### Installation

```bash
# Clone and install
git clone https://github.com/BangRocket/mypalclara.git
cd mypalclara
poetry install

# Run the setup wizard
poetry run clara onboard
```

### Running

```bash
# Start the gateway server
poetry run clara serve

# Or start with specific options
poetry run clara serve --host 0.0.0.0 --port 8080 --detach

# Start interactive chat
poetry run clara chat
```

## CLI Reference

Clara provides a comprehensive CLI for management and interaction:

```bash
clara --help                    # Show all commands
```

### Core Commands

| Command | Description |
|---------|-------------|
| `clara chat [message]` | Interactive chat or send single message |
| `clara serve` | Start the gateway server |
| `clara doctor` | Run system diagnostics |
| `clara onboard` | Interactive setup wizard |
| `clara version` | Show version information |

### Gateway Management

```bash
clara gateway start             # Start gateway server
clara gateway stop              # Stop gateway server
clara gateway status            # Show gateway status
clara gateway logs -f           # Follow gateway logs
clara gateway adapters          # List connected adapters
```

### Channel Management

```bash
clara channels list             # List enabled channels
clara channels list --all       # Show all channels
clara channels status discord   # Show channel details
clara channels start discord    # Start a channel
clara channels stop discord     # Stop a channel
clara channels setup discord    # Run channel setup wizard
clara channels test discord     # Test channel connectivity
```

### Plugin Management

```bash
clara plugins list              # List installed plugins
clara plugins info <name>       # Show plugin details
clara plugins install <source>  # Install a plugin
clara plugins uninstall <name>  # Remove a plugin
clara plugins enable <name>     # Enable a plugin
clara plugins disable <name>    # Disable a plugin
clara plugins reload <name>     # Reload a plugin
```

### Configuration

```bash
clara config show               # Show current configuration
clara config show llm           # Show specific section
clara config validate           # Validate configuration
clara config set llm.model X    # Set a value
clara config edit               # Open in editor
clara config init               # Create default config
```

### Status & Diagnostics

```bash
clara status overview           # System overview
clara status gateway            # Gateway details
clara status memory             # Memory system status
clara status channels           # Channel status
clara status llm                # LLM provider status
clara status env                # Environment variables
```

## Architecture

Clara uses a modular architecture inspired by [OpenClaw](https://github.com/openclaw):

```
┌─────────────────────────────────────────────────────────────┐
│                        Gateway Server                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ LLM Orchestrator │  │ Tool Executor │  │ Plugin Manager │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │ WebSocket
        ┌──────────────────┼──────────────────┐
        │                  │                  │
┌───────┴───────┐  ┌───────┴───────┐  ┌───────┴───────┐
│ Discord Adapter│  │ Slack Adapter │  │  CLI Adapter  │
└───────────────┘  └───────────────┘  └───────────────┘
```

### Channel Plugin System

Channels are implemented as plugins with optional adapters:

- **Gateway Adapter** - WebSocket connection handling
- **Messaging Adapter** - Send/receive messages
- **Streaming Adapter** - Real-time response streaming
- **Threading Adapter** - Thread/reply management
- **Security Adapter** - Authentication/authorization
- **Setup Adapter** - Interactive configuration

### Plugin System

Plugins can register:
- **Hooks** - Lifecycle events (startup, message received, tool execution, etc.)
- **Tools** - Custom tools available to the LLM
- **Channels** - New communication channels

### Routing System

Routes determine how messages are processed:
- **Binding Priority** - peer (100) > guild (80) > team (70) > account (60) > channel (40) > default (0)
- **Session Scoping** - main, per-peer, per-channel-peer, per-account-channel-peer

## Configuration

### Configuration File

Clara uses YAML configuration at `~/.clara/config.yaml`:

```yaml
llm:
  provider: anthropic
  model: claude-sonnet-4-5

memory:
  enabled: true
  provider: postgres  # or qdrant

gateway:
  host: 127.0.0.1
  port: 18789

channels:
  discord:
    enabled: true
    token: ${DISCORD_BOT_TOKEN}
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Required for mem0 embeddings |
| `LLM_PROVIDER` | `openrouter`, `nanogpt`, `anthropic`, or `openai` |
| `DISCORD_BOT_TOKEN` | Discord bot token |
| `DATABASE_URL` | PostgreSQL for sessions/messages |
| `MEM0_DATABASE_URL` | PostgreSQL+pgvector for vectors |

### LLM Providers

**Anthropic** (recommended):
```bash
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-key
ANTHROPIC_MODEL=claude-sonnet-4-5
```

**OpenRouter**:
```bash
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your-key
OPENROUTER_MODEL=anthropic/claude-sonnet-4
```

**Model Tiers** - Configure tier-specific models:
```bash
ANTHROPIC_MODEL_HIGH=claude-opus-4-5
ANTHROPIC_MODEL_MID=claude-sonnet-4-5
ANTHROPIC_MODEL_LOW=claude-haiku-4-5
```

## MCP Plugin System

Clara can install [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) servers to extend capabilities.

### Installation Sources

```bash
# Smithery registry
clara plugins install smithery:e2b

# npm packages
clara plugins install @modelcontextprotocol/server-everything

# GitHub repos
clara plugins install github.com/user/mcp-server

# Docker images
clara plugins install ghcr.io/example/mcp-server:latest
```

### Using MCP Tools

Tools are namespaced: `{server_name}__{tool_name}`
- Example: `everything__echo`, `filesystem__read_file`

### Discord Slash Commands

```
/mcp search <query>     - Search Smithery registry
/mcp install <source>   - Install a server
/mcp list               - List installed servers
/mcp status <server>    - Get server status
/mcp uninstall <server> - Remove a server
```

## Memory System

Clara uses mem0 for persistent memory with vector search.

### Bootstrap Profile Data

```bash
poetry run python -m src.bootstrap_memory          # Dry run
poetry run python -m src.bootstrap_memory --apply  # Apply to mem0
```

### Clear Memory

```bash
poetry run python clear_dbs.py              # With prompt
poetry run python clear_dbs.py --yes        # Skip prompt
poetry run python clear_dbs.py --user <id>  # Specific user
```

## Production Deployment

### Docker Compose

```bash
# Gateway + Discord adapter
docker-compose --profile gateway --profile discord up

# With PostgreSQL
docker-compose --profile gateway --profile discord --profile postgres up
```

### Railway

The repo includes `railway.toml` for deployment:

1. Connect GitHub repo to Railway
2. Set environment variables
3. Deploy

### Database Setup

For production, use PostgreSQL:

```bash
DATABASE_URL=postgresql://user:pass@host:5432/clara_main
MEM0_DATABASE_URL=postgresql://user:pass@host:5432/clara_vectors
```

Enable pgvector:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

## Development

```bash
poetry run ruff check .    # Lint
poetry run ruff format .   # Format
poetry run pytest          # Test
```

### Project Structure

```
mypalclara/
├── clara_core/
│   ├── cli/           # CLI commands
│   ├── channels/      # Channel plugin system
│   ├── plugins/       # Plugin system
│   ├── routing/       # Route resolution
│   └── mcp/           # MCP integration
├── gateway/           # Gateway server
├── adapters/          # Platform adapters
├── tools/             # Built-in tools
└── config/            # Configuration schemas
```

See [CLAUDE.md](CLAUDE.md) for detailed development documentation.

## License

[PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/) - Free for non-commercial use. Commercial use requires a separate license.
