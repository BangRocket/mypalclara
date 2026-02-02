# Discord Features

Clara's Discord bot provides a rich conversational interface with streaming responses, tool execution, and channel management.

## Getting Started

### Bot Setup

1. Create a Discord application at [Discord Developer Portal](https://discord.com/developers/applications)
2. Enable the bot and get your token
3. Configure required intents:
   - Message Content Intent
   - Server Members Intent
   - Presence Intent

### Configuration

```bash
# Required
DISCORD_BOT_TOKEN=your-bot-token

# Optional
DISCORD_CLIENT_ID=your-client-id  # For invite link
DISCORD_ALLOWED_SERVERS=123,456   # Whitelist servers
DISCORD_ALLOWED_CHANNELS=789,012  # Whitelist channels
DISCORD_ALLOWED_ROLES=345,678     # Role-based access
```

## Channel Modes

Clara supports three channel modes:

### Active Mode
Clara responds to all messages in the channel.
```
/clara mode active
```

### Mention Mode (Default)
Clara only responds when mentioned with @Clara.
```
/clara mode mention
```

### Off Mode
Clara ignores all messages in the channel.
```
/clara mode off
```

## Message Handling

### Response Behavior

When processing a message, Clara:
1. Shows "Clara is typing..." indicator while generating
2. Sends the complete response when finished

This provides a clean experience without message flickering during streaming. The typing indicator refreshes automatically during long responses.

### Reply Chains
Clara tracks conversation threads through Discord's reply feature. Reply to Clara's message to continue the conversation context.

### Stop Phrases
Interrupt Clara mid-task:
- "@Clara stop"
- "@Clara nevermind"
- "clara stop"
- "stop clara"

Configure custom phrases:
```bash
DISCORD_STOP_PHRASES="clara stop,stop clara,nevermind,cancel that"
```

### Message Queuing

When Clara is busy, messages are queued:

**DMs and Mentions:**
- Queue position notification shown
- "Starting your queued request" when processed

**Active Mode:**
- Messages batched together
- React with hourglass while queued
- Combined response with all queued messages

## Model Tiers

Select models via message prefixes:

| Prefix | Tier | Description |
|--------|------|-------------|
| `!high` or `!opus` | High | Most capable (Opus-class) |
| `!mid` or `!sonnet` | Mid | Balanced (Sonnet-class) - default |
| `!low`, `!haiku`, `!fast` | Low | Fast/cheap (Haiku-class) |

Example:
```
!high Explain quantum entanglement in detail
```

### Auto-Tier Selection

Enable automatic tier selection based on message complexity:
```bash
AUTO_TIER_SELECTION=true
```

## Image Support

Clara can analyze images attached to messages.

### Configuration

```bash
DISCORD_MAX_IMAGE_DIMENSION=1568  # Max pixels
DISCORD_MAX_IMAGES_PER_REQUEST=1  # Batch limit
DISCORD_MAX_IMAGE_SIZE=4194304    # 4MB max
```

### Supported Formats
- PNG
- JPEG/JPG
- GIF
- WebP

### Multi-Image Handling
When multiple images exceed the batch limit:
1. Images processed in sequential batches
2. Context preserved between batches
3. Combined response returned

## Slash Commands

### General

| Command | Description |
|---------|-------------|
| `/clara help` | Show help information |
| `/clara status` | Check bot status |
| `/clara mode` | Set channel mode |
| `/clara clear` | Clear conversation context |

### MCP

| Command | Description |
|---------|-------------|
| `/mcp search <query>` | Search Smithery registry |
| `/mcp install <source>` | Install a server |
| `/mcp list` | List installed servers |
| `/mcp status <server>` | Get server status |
| `/mcp tools [server]` | List available tools |
| `/mcp enable/disable <server>` | Toggle server |
| `/mcp uninstall <server>` | Remove server |

### Google Workspace

| Command | Description |
|---------|-------------|
| `/google connect` | Start OAuth flow |
| `/google status` | Check connection |
| `/google disconnect` | Remove connection |

## Tool Execution

When Clara uses tools, status messages appear:

```
-# 🐍 Running Python code... (step 1)
-# ↳ Analyzing the CSV file to compute statistics
```

Configure status descriptions:
```bash
TOOL_DESC_TIER=high  # LLM tier for descriptions
TOOL_DESC_MAX_WORDS=20  # Max words
```

## Attachments

### Text Files
Clara can read text file attachments:
- .txt, .md, .py, .js, .json, etc.
- Content extracted and included in context

### Images
See [Image Support](#image-support) above.

### Other Files
- Saved to local storage
- Can be referenced in conversation

## Permissions

### Admin Operations

Require one of:
- Administrator permission
- Manage Channels permission
- Clara-Admin role

Admin operations include:
- MCP server installation/removal
- Channel mode changes (server-wide)
- Memory management

### User Operations

Available to all users:
- Chat with Clara
- Use tools
- Check status
- Personal OAuth connections

## Console Mirroring

Mirror console logs to a Discord channel:

```bash
DISCORD_LOG_CHANNEL_ID=123456789
```

Special events highlighted:
- 🟢 Bot started
- 🔴 Bot shutting down
- 🟡 Bot disconnected
- 🔄 Bot reconnected

## Monitor Dashboard

Web dashboard for bot status:

```bash
DISCORD_MONITOR_ENABLED=true
DISCORD_MONITOR_PORT=8001
```

Access at `http://localhost:8001`

## Best Practices

### Channel Setup
- Use mention mode for busy channels
- Use active mode for dedicated bot channels
- Set up a Clara-Admin role for trusted users

### Performance
- Limit concurrent active mode channels
- Configure appropriate model tiers
- Use stop phrases when needed

### Security
- Restrict to allowed servers/channels in production
- Use role-based access for sensitive features
- Monitor tool execution logs
