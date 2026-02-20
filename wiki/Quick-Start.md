# Quick Start

Get Clara running in 5 minutes.

## Prerequisites

- Python 3.11+
- Poetry
- Discord bot token
- OpenAI API key (for embeddings)
- LLM provider API key (Anthropic, OpenRouter, etc.)

## 1. Clone and Install

```bash
git clone https://github.com/BangRocket/mypalclara.git
cd mypalclara
poetry install
```

## 2. Configure

```bash
cp .env.example .env
```

Edit `.env` with minimum required settings:

```bash
# Discord
DISCORD_BOT_TOKEN=your-discord-bot-token

# Embeddings (required for memory)
OPENAI_API_KEY=sk-your-openai-key

# LLM Provider (choose one)
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-anthropic-key
ANTHROPIC_MODEL=claude-sonnet-4-5
```

## 3. Run

```bash
# Direct run
poetry run python -m mypalclara.adapters.discord

# Or daemon mode
poetry run python -m mypalclara.adapters.discord --daemon
```

## 4. Test

1. Invite bot to your Discord server
2. Send: `@Clara hello`
3. Clara should respond!

## Next Steps

| Want to... | See... |
|------------|--------|
| Configure all options | [[Configuration]] |
| Use Teams instead | [[Teams-Adapter]] |
| Set up memory | [[Memory-System]] |
| Install MCP plugins | [[MCP-Plugin-System]] |
| Deploy to production | [[Deployment]] |

## Common Quick Fixes

**Bot not responding?**
- Check token is correct
- Enable intents in Discord Developer Portal (Message Content, Server Members, Presence)
- Verify bot has channel permissions

**Memory errors?**
- Ensure `OPENAI_API_KEY` is set (required for embeddings)

**Import errors?**
```bash
poetry shell
python -m mypalclara.adapters.discord
```

See [[Troubleshooting]] for more help.
