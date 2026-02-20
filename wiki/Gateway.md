# Gateway System

The gateway is Clara's central message processing hub that connects platform adapters to the LLM and tool execution systems.

## Overview

The gateway provides:
- WebSocket server for adapter connections
- Message routing and queuing
- Session and context management
- LLM orchestration with streaming
- Tool execution coordination
- Event hooks and scheduled tasks

## Running the Gateway

### Foreground Mode

```bash
poetry run python -m mypalclara.gateway --host 127.0.0.1 --port 18789
```

### Daemon Mode

```bash
# Start gateway with all enabled adapters
poetry run python -m mypalclara.gateway start
poetry run python -m mypalclara.gateway start --logfile /var/log/clara-gateway.log

# Start with specific adapter(s) only
poetry run python -m mypalclara.gateway start --adapter discord
poetry run python -m mypalclara.gateway start --adapter discord --adapter teams

# Start gateway without spawning adapters
poetry run python -m mypalclara.gateway start --no-adapters

# Run in foreground with adapters (for development)
poetry run python -m mypalclara.gateway start -f

# Check status
poetry run python -m mypalclara.gateway status

# Stop
poetry run python -m mypalclara.gateway stop

# Restart
poetry run python -m mypalclara.gateway restart
```

### Adapter Management

The gateway spawns and supervises platform adapters as subprocesses.

```bash
# Check adapter status
poetry run python -m mypalclara.gateway adapter discord status

# Start/stop individual adapters
poetry run python -m mypalclara.gateway adapter discord start
poetry run python -m mypalclara.gateway adapter discord stop

# Restart an adapter
poetry run python -m mypalclara.gateway adapter discord restart
```

### Adapter Configuration

Configure adapters in `mypalclara/gateway/adapters.yaml`:

```yaml
adapters:
  discord:
    enabled: true
    module: mypalclara.adapters.discord
    env:
      DISCORD_BOT_TOKEN: ${DISCORD_BOT_TOKEN}
    restart_policy: always
    restart_delay: 5
    max_restarts: 10
    reset_window: 300

  teams:
    enabled: false  # Enable when configured
    module: mypalclara.adapters.teams
    env:
      TEAMS_APP_ID: ${TEAMS_APP_ID}
      TEAMS_APP_PASSWORD: ${TEAMS_APP_PASSWORD}
    restart_policy: always
    restart_delay: 5
```

**Restart Policies:**
- `always` - Restart on any exit
- `on_failure` - Only restart on non-zero exit
- `never` - Don't auto-restart

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CLARA_GATEWAY_HOST` | 127.0.0.1 | Bind address |
| `CLARA_GATEWAY_PORT` | 18789 | WebSocket port |
| `CLARA_GATEWAY_SECRET` | (none) | Shared auth secret |
| `CLARA_HOOKS_DIR` | ./hooks | Hooks configuration |
| `CLARA_SCHEDULER_DIR` | . | Scheduler configuration |

## Components

### Router (`mypalclara/gateway/router.py`)

Handles message queuing and routing:
- Per-channel message queues
- Priority handling
- Cancellation support

### Processor (`mypalclara/gateway/processor.py`)

Builds context for LLM calls:
- Fetches memories from mem0
- Retrieves channel summaries
- Manages session context

### LLM Orchestrator (`mypalclara/gateway/llm_orchestrator.py`)

Coordinates LLM interactions:
- Streaming response generation
- Tool call detection and execution
- Auto-continue for long responses

### Session Manager (`mypalclara/gateway/session.py`)

Manages user sessions:
- Session creation and lookup
- Activity tracking
- Stale session cleanup

### Tool Executor (`mypalclara/gateway/tool_executor.py`)

Executes tool calls:
- Built-in tool registry
- MCP server integration
- Result formatting

## Protocol

The gateway uses a JSON-based WebSocket protocol:

### Registration

```json
{
  "type": "register",
  "platform": "discord",
  "node_id": "discord-main",
  "capabilities": ["streaming", "attachments", "reactions"]
}
```

### Message Request

```json
{
  "type": "message",
  "request_id": "uuid",
  "user_id": "discord-123",
  "channel_id": "channel-456",
  "content": "Hello Clara",
  "attachments": []
}
```

### Response Chunks

```json
{
  "type": "response_chunk",
  "request_id": "uuid",
  "content": "Hello! How can I help?",
  "done": false
}
```

### Tool Status

```json
{
  "type": "tool_status",
  "request_id": "uuid",
  "tool_name": "web_search",
  "status": "running",
  "description": "Searching for Python tutorials"
}
```

## Hooks

Hooks are automations triggered by gateway events.

### Configuration

Create `hooks/hooks.yaml`:

```yaml
hooks:
  - name: log-startup
    event: gateway:startup
    command: echo "Gateway started at ${CLARA_TIMESTAMP}"
    timeout: 30

  - name: notify-errors
    event: tool:error
    command: |
      curl -X POST https://webhook.example.com/notify \
        -H "Content-Type: application/json" \
        -d "${CLARA_EVENT_DATA}"
    timeout: 10
```

### Event Types

| Event | Description |
|-------|-------------|
| `gateway:startup` | Gateway has started |
| `gateway:shutdown` | Gateway is shutting down |
| `adapter:connected` | Adapter connected |
| `adapter:disconnected` | Adapter disconnected |
| `session:start` | New session created |
| `session:end` | Session ended |
| `session:timeout` | Session timed out |
| `message:received` | Message received from adapter |
| `message:sent` | Response sent to adapter |
| `message:cancelled` | Message processing cancelled |
| `tool:start` | Tool execution started |
| `tool:end` | Tool execution completed |
| `tool:error` | Tool execution failed |
| `scheduler:task_run` | Scheduled task executed |
| `scheduler:task_error` | Scheduled task failed |

### Environment Variables in Hooks

Hooks receive context via environment variables:

| Variable | Description |
|----------|-------------|
| `CLARA_EVENT_TYPE` | Event type |
| `CLARA_TIMESTAMP` | ISO timestamp |
| `CLARA_NODE_ID` | Adapter node ID |
| `CLARA_PLATFORM` | Platform name |
| `CLARA_USER_ID` | User ID |
| `CLARA_CHANNEL_ID` | Channel ID |
| `CLARA_REQUEST_ID` | Request ID |
| `CLARA_EVENT_DATA` | Full event as JSON |

### Python Hooks

Register hooks programmatically:

```python
from mypalclara.gateway import hook, EventType, Event

@hook(EventType.SESSION_START)
async def on_session_start(event: Event):
    print(f"Session started for {event.user_id}")
```

## Scheduler

The scheduler runs tasks on intervals or cron schedules.

### Configuration

Create `scheduler.yaml`:

```yaml
tasks:
  - name: cleanup-sessions
    type: interval
    interval: 3600  # Every hour
    command: poetry run python -m scripts.cleanup_sessions
    timeout: 300

  - name: daily-backup
    type: cron
    cron: "0 3 * * *"  # 3 AM daily
    command: ./scripts/backup.sh
    timeout: 1800

  - name: send-reminder
    type: one_shot
    run_at: "2024-12-25T09:00:00Z"
    command: echo "Merry Christmas!"
```

### Task Types

| Type | Description |
|------|-------------|
| `interval` | Run every N seconds |
| `cron` | Run on cron schedule |
| `one_shot` | Run once at specific time |

### Python Tasks

Register tasks programmatically:

```python
from mypalclara.gateway import scheduled, TaskType

@scheduled(type=TaskType.INTERVAL, interval=3600)
async def hourly_cleanup():
    # Cleanup logic
    pass

@scheduled(type=TaskType.CRON, cron="0 3 * * *")
async def daily_backup():
    # Backup logic
    pass
```

## Adapter Development

### Creating an Adapter

1. Connect to gateway WebSocket
2. Send registration message
3. Handle incoming messages
4. Send message requests
5. Process response chunks

### Example Adapter

```python
import asyncio
import json
import websockets

async def run_adapter():
    async with websockets.connect("ws://localhost:18789") as ws:
        # Register
        await ws.send(json.dumps({
            "type": "register",
            "platform": "custom",
            "node_id": "custom-1",
            "capabilities": ["streaming"]
        }))

        # Handle messages
        async for msg in ws:
            data = json.loads(msg)
            if data["type"] == "response_chunk":
                print(data["content"], end="", flush=True)
            elif data["type"] == "response_end":
                print()  # Newline
```

See `mypalclara/adapters/discord/gateway_client.py` for a full implementation.
