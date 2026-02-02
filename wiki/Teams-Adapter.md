# Teams Adapter

Microsoft Teams integration for Clara using the Bot Framework SDK.

## Overview

The Teams adapter connects Clara to Microsoft Teams, enabling:
- Direct messages and channel conversations
- Tier override prefixes (`!high`, `!mid`, `!low`)
- Reactions (add/remove)
- Welcome messages for new members
- Gateway reconnection with session preservation

## Architecture

```
Teams Channel/DM
       │
       ▼
┌─────────────────┐
│  Teams Adapter  │  (adapters/teams/)
│    Bot.py       │
└────────┬────────┘
         │ WebSocket
         ▼
┌─────────────────┐
│    Gateway      │  Message processing, tools, memory
└─────────────────┘
```

## Prerequisites

1. Azure account with Bot Service access
2. Teams Admin access (for app deployment)
3. Running Clara Gateway

## Azure Bot Service Setup

### Step 1: Create Azure Bot

1. Go to [Azure Portal](https://portal.azure.com)
2. Create resource → Search "Azure Bot"
3. Fill in:
   - **Bot handle**: `clara-teams-bot`
   - **Subscription**: Your subscription
   - **Resource group**: Create or select existing
   - **Pricing tier**: F0 (free) for development
   - **Microsoft App ID**: Create new
4. Click **Create**

### Step 2: Get Credentials

1. Navigate to your bot resource → **Configuration**
2. Copy **Microsoft App ID** → This is `TEAMS_APP_ID`
3. Click **Manage Password** → **New client secret**
4. Copy the secret value → This is `TEAMS_APP_PASSWORD`

### Step 3: Configure Messaging Endpoint

In bot **Configuration**:
- **Messaging endpoint**: `https://your-domain.com/api/messages`

This URL must be publicly accessible. Use ngrok for local development.

### Step 4: Enable Teams Channel

1. Bot resource → **Channels**
2. Click **Microsoft Teams** icon
3. Accept terms and save

## Configuration

```bash
# Required
TEAMS_APP_ID=your-azure-bot-app-id
TEAMS_APP_PASSWORD=your-azure-bot-password

# Optional
TEAMS_PORT=3978                           # Listen port (default: 3978)
TEAMS_TENANT_ID=your-tenant-id            # Restrict to specific tenant
CLARA_GATEWAY_URL=ws://127.0.0.1:18789    # Gateway WebSocket URL
```

## Running

### Standalone

```bash
poetry run python -m adapters.teams
```

### With Gateway

```bash
# Terminal 1: Start gateway
poetry run python -m gateway

# Terminal 2: Start Teams adapter
poetry run python -m adapters.teams
```

### Via Gateway Daemon

```bash
# Enable Teams in gateway/adapters.yaml, then:
poetry run python -m gateway start
```

## Local Development with ngrok

```bash
# Start ngrok tunnel
ngrok http 3978

# Update Azure Bot messaging endpoint to ngrok URL:
# https://xxxx.ngrok.io/api/messages

# Run Teams adapter
poetry run python -m adapters.teams --port 3978
```

## Teams App Manifest

Create `teams_manifest/manifest.json`:

```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/teams/v1.16/MicrosoftTeams.schema.json",
  "manifestVersion": "1.16",
  "version": "1.0.0",
  "id": "<your-bot-app-id>",
  "packageName": "com.mypalclara.teams",
  "developer": {
    "name": "Your Name",
    "websiteUrl": "https://github.com/BangRocket/mypalclara",
    "privacyUrl": "https://github.com/BangRocket/mypalclara/privacy",
    "termsOfUseUrl": "https://github.com/BangRocket/mypalclara/terms"
  },
  "name": {
    "short": "Clara",
    "full": "MyPalClara AI Assistant"
  },
  "description": {
    "short": "AI assistant with memory",
    "full": "Personal AI assistant with persistent memory and tool execution"
  },
  "icons": {
    "color": "color.png",
    "outline": "outline.png"
  },
  "accentColor": "#FFFFFF",
  "bots": [
    {
      "botId": "<your-bot-app-id>",
      "scopes": ["personal", "team", "groupchat"],
      "supportsFiles": true,
      "isNotificationOnly": false
    }
  ],
  "permissions": ["identity", "messageTeamMembers"],
  "validDomains": ["your-domain.com"]
}
```

### Install in Teams

1. Zip `manifest.json` + icon files (color.png, outline.png)
2. Teams → Apps → **Upload a custom app**
3. Or use Teams Admin Center for org-wide deployment

## Features

### Model Tiers

Prefix messages to select model tier:

| Prefix | Tier | Example |
|--------|------|---------|
| `!high` or `!opus` | High | `!high Explain quantum physics` |
| `!mid` or `!sonnet` | Mid | `!mid Summarize this` |
| `!low` or `!haiku` | Low | `!low What time is it?` |

### Reactions

Clara responds to reactions on her messages (platform-dependent behavior).

### Welcome Messages

New team members receive a welcome message from Clara (configurable).

## Docker Deployment

```yaml
# docker-compose.yml
services:
  teams-adapter:
    build: .
    command: poetry run python -m adapters.teams
    ports:
      - "3978:3978"
    environment:
      - TEAMS_APP_ID
      - TEAMS_APP_PASSWORD
      - CLARA_GATEWAY_URL=ws://gateway:18789
    depends_on:
      - gateway
```

## Troubleshooting

### Bot Not Responding

1. Check Azure Bot messaging endpoint is correct
2. Verify ngrok tunnel is running (for local dev)
3. Check adapter logs for connection errors
4. Verify Teams channel is enabled in Azure

### Authentication Errors

1. Verify `TEAMS_APP_ID` and `TEAMS_APP_PASSWORD` are correct
2. Check client secret hasn't expired
3. Ensure bot is properly registered in Azure

### Gateway Connection Failed

1. Verify gateway is running
2. Check `CLARA_GATEWAY_URL` is correct
3. Check firewall allows WebSocket connections

## File Structure

```
adapters/teams/
├── __init__.py
├── bot.py              # Bot Framework activity handler
├── gateway_client.py   # Gateway WebSocket client
├── message_builder.py  # Teams message formatting
└── main.py             # Entry point
```

## See Also

- [[Gateway]] - Gateway server documentation
- [[Discord-Features]] - Discord adapter (similar features)
- [[Deployment]] - Production deployment guide
