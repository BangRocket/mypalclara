# Installation

Step-by-step guide to installing MyPalClara.

## Prerequisites

- **Python 3.11+** - Required for the bot
- **Poetry** - Python dependency management
- **Docker** - Optional, for code execution sandbox
- **Node.js/npm** - Optional, for MCP servers from npm

### Installing Prerequisites

**macOS:**
```bash
# Python via pyenv
brew install pyenv
pyenv install 3.12
pyenv global 3.12

# Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Docker Desktop
brew install --cask docker
```

**Ubuntu/Debian:**
```bash
# Python
sudo apt update
sudo apt install python3.12 python3.12-venv

# Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

**Windows:**
```powershell
# Python - download from python.org
# Poetry
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -

# Docker Desktop - download from docker.com
```

## Clone and Install

```bash
# Clone the repository
git clone https://github.com/BangRocket/mypalclara.git
cd mypalclara

# Install dependencies
poetry install

# Install git hooks (for version auto-bump)
git config core.hooksPath .githooks
```

## Configuration

### Create Environment File

```bash
cp .env.example .env
```

### Required Settings

Edit `.env` with your API keys:

```bash
# Discord bot token (from Discord Developer Portal)
DISCORD_BOT_TOKEN=your-bot-token

# OpenAI API key (required for mem0 embeddings)
OPENAI_API_KEY=sk-your-key

# Choose LLM provider
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-anthropic-key
ANTHROPIC_MODEL=claude-sonnet-4-5
```

### Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to Bot section
4. Create a bot and copy the token
5. Enable these intents:
   - Message Content Intent
   - Server Members Intent
   - Presence Intent
6. Go to OAuth2 > URL Generator
7. Select scopes: `bot`, `applications.commands`
8. Select permissions: Send Messages, Embed Links, Attach Files, Read Message History, Add Reactions
9. Use generated URL to invite bot to your server

## Running

### Development

```bash
# Run the Discord bot directly
poetry run python -m mypalclara.adapters.discord

# Or run via gateway (multi-platform support)
poetry run python -m mypalclara.gateway
```

### Production

```bash
# Daemon mode via gateway (recommended)
poetry run python -m mypalclara.gateway start --adapter discord

# Check status
poetry run python -m mypalclara.gateway status

# Stop
poetry run python -m mypalclara.gateway stop
```

### Docker

```bash
# Discord bot only
docker-compose --profile discord up -d

# With PostgreSQL databases
docker-compose --profile discord --profile postgres up -d
```

## Verify Installation

1. Check bot appears online in Discord
2. Send a test message: `@Clara hello`
3. Verify response received

## Next Steps

- [[Configuration]] - All configuration options
- [[Discord-Features]] - Discord-specific features
- [[MCP-Plugin-System]] - Install tool plugins
- [[Memory-System]] - Set up persistent memory

## Common Issues

### Poetry Not Found

Add Poetry to PATH:
```bash
export PATH="$HOME/.local/bin:$PATH"
```

Add to `~/.bashrc` or `~/.zshrc` for persistence.

### Import Errors

Ensure you're in the project directory and using Poetry:
```bash
cd mypalclara
poetry shell  # Activate virtual environment
python -m mypalclara.adapters.discord
```

### Bot Not Responding

1. Check token is correct
2. Verify intents are enabled in Developer Portal
3. Check bot has permissions in the channel
4. Review logs for errors

### Memory Errors (mem0)

1. Ensure OPENAI_API_KEY is set
2. Check vector store is running (if using Qdrant)
3. Verify pgvector extension (if using PostgreSQL)

See [[Troubleshooting]] for more solutions.
