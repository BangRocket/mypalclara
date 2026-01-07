# Clara CrewAI Architecture (v0.8.0)

## Overview

Clara v0.8.0 introduces a new architecture built on CrewAI Flows. Clara is no longer a Discord bot with tools—she's a **persistent mind** with crews as her interface to the world.

```
Discord Message → Thin Adapter → ClaraFlow (the mind) → Response
                                      ↓
                                 mem0 memories
```

## Design Philosophy

- **Clara is a Flow** - The mind, decision maker, holds state and memory
- **Adapters are interfaces** - How Clara perceives and interacts with platforms
- **Reactive only (v1)** - Responds to input, no background processing yet
- **Architecture supports expansion** - Adding new crewai_service/platforms is straightforward

## Components

### 1. ClaraFlow (`crewai_service/flow/clara/flow.py`)

The core "mind" - a CrewAI Flow that processes messages through a deterministic pipeline:

```python
class ClaraFlow(Flow[ClaraState]):
    @start()
    def receive_message(self): ...      # Entry point

    @listen(receive_message)
    def fetch_memories(self): ...       # Query mem0

    @listen(fetch_memories)
    def build_prompt(self): ...         # Personality + context

    @listen(build_prompt)
    def generate_response(self): ...    # LLM call

    @listen(generate_response)
    def store_memories(self): ...       # Save to mem0
```

**Key integrations:**
- `config/bot.py` - Clara's personality (PERSONALITY constant)
- `clara_core/llm.py` - LLM backends (OpenRouter, Anthropic, etc.)
- `clara_core/memory.py` - MemoryManager singleton

### 2. ClaraState (`crewai_service/flow/clara/state.py`)

Pydantic models that hold conversation state:

```python
class ConversationContext(BaseModel):
    user_id: str                    # "discord-123456"
    platform: str                   # "discord"
    channel_id: Optional[str]
    guild_id: Optional[str]
    thread_id: Optional[str]
    is_dm: bool
    user_display_name: str
    guild_name: Optional[str]
    channel_name: Optional[str]
    participants: list[dict]

class ClaraState(BaseModel):
    context: ConversationContext
    user_message: str
    user_memories: list[str]        # From mem0
    project_memories: list[str]     # From mem0
    recent_messages: list[dict]
    response: str
    tier: str                       # "high", "mid", "low"
```

### 3. MemoryBridge (`crewai_service/flow/clara/memory_bridge.py`)

Wrapper around `MemoryManager` for Flow integration:

```python
class MemoryBridge:
    def fetch_context(context, user_message) -> (user_mems, proj_mems)
    def store_exchange(db, context, thread_id, user_msg, assistant_reply)
    def get_recent_messages(db, thread_id) -> list[dict]
    def store_message(db, thread_id, user_id, role, content)
```

### 4. Discord Adapter (`crewai_service/discord/adapter.py`)

Thin Discord.py bot that routes to ClaraFlow:

```python
class ClaraDiscordBot(discord.Client):
    async def on_message(self, message):
        # Filter (mentions, channel modes)
        # Build ConversationContext
        # Run ClaraFlow in thread pool
        # Send response

    async def _run_flow(self, context, content) -> str:
        # Sync/async bridge via run_in_executor
        flow = ClaraFlow()
        flow.kickoff(inputs={...})
        return flow.state.response
```

### 5. Helpers (`crewai_service/discord/helpers.py`)

Utility functions:
- `clean_message_content()` - Remove bot mentions
- `chunk_response()` - Split long responses for Discord
- `build_participants_list()` - Extract mentioned users
- `get_or_create_thread_id()` - Generate thread IDs

## File Structure

```
crewai_service/
├── __init__.py                 # Exports ClaraFlow, run_clara_flow
├── flow/
│   ├── __init__.py
│   └── clara/
│       ├── __init__.py         # Exports ClaraFlow, ClaraState
│       ├── flow.py             # ClaraFlow - the mind
│       ├── state.py            # Pydantic state models
│       └── memory_bridge.py    # mem0 integration wrapper
└── discord/
    ├── __init__.py
    ├── adapter.py              # ClaraDiscordBot
    └── helpers.py              # Utility functions

discord_crewai.py               # Entry point
```

## Running

### Local Development

```bash
# Install dependencies (includes crewai)
poetry install

# Set environment variables
export DISCORD_BOT_TOKEN="your-token"
export LLM_PROVIDER="anthropic"  # or openrouter, openai
export ANTHROPIC_API_KEY="your-key"

# Run
poetry run python discord_crewai.py
```

### Docker

```bash
docker build -f Dockerfile.discord -t clara-discord .
docker run -e DISCORD_BOT_TOKEN=... -e LLM_PROVIDER=... clara-discord
```

### Docker Compose

```bash
docker-compose --profile discord up
```

## Configuration

All existing environment variables from `CLAUDE.md` still apply:

| Variable | Description |
|----------|-------------|
| `DISCORD_BOT_TOKEN` | Discord bot token (required) |
| `LLM_PROVIDER` | Backend: openrouter, anthropic, openai, nanogpt |
| `ANTHROPIC_API_KEY` | For Anthropic provider |
| `OPENROUTER_API_KEY` | For OpenRouter provider |
| `DATABASE_URL` | PostgreSQL connection (optional) |
| `MEM0_DATABASE_URL` | PostgreSQL for mem0 vectors (optional) |

## Async/Sync Bridge

CrewAI Flows are synchronous, Discord.py is async. The bridge pattern:

```python
async def _run_flow(self, context, content):
    loop = asyncio.get_event_loop()

    def run_sync():
        flow = ClaraFlow()
        flow.kickoff(inputs={...})
        return flow.state.response

    return await loop.run_in_executor(None, run_sync)
```

This runs ClaraFlow in a thread pool, keeping Discord.py's event loop responsive.

## Memory Flow

1. **Fetch** - `MemoryBridge.fetch_context()` queries mem0 for relevant memories
2. **Inject** - Memories added to system prompt in `build_prompt()`
3. **Store** - After response, `store_memories()` saves exchange to:
   - SQLAlchemy DB (message persistence)
   - mem0 (semantic memory extraction)

## What's Preserved from v0.7

- Clara's personality (`config/bot.py`)
- mem0 integration (full semantic memory)
- LLM backends (all providers supported)
- Channel modes (active/mention/off)
- Model tiers (high/mid/low)

## What's Deferred to v2+

| Feature | Status |
|---------|--------|
| Tool calling | Deferred - will add ToolsCrew |
| Queue system | Deferred - simplified for v1 |
| Stop phrases | Deferred |
| Tier auto-detection | Deferred |
| ORS/proactive messaging | Deferred |
| Streaming responses | Deferred |
| Attachment handling | Basic only |

## Extending the Architecture

### Adding a New Platform (e.g., Slack)

1. Create `crewai_service/slack/adapter.py` with platform-specific bot
2. Build `ConversationContext` from Slack events
3. Call `ClaraFlow.kickoff()` with context
4. Send response back to Slack

The Flow doesn't change - only the adapter.

### Adding Tools (v2)

1. Create `crewai_service/tools/crew.py` with tool-executing agents
2. Add a new Flow step that calls the tools crew:

```python
@listen(build_prompt)
def execute_tools_if_needed(self):
    if self._needs_tools(self.state.full_messages):
        tools_crew = ToolsCrew()
        result = tools_crew.kickoff(...)
        # Add tool results to messages
```

### Adding Background Processing (Rumination)

1. Create `crewai_service/rumination/flow.py` with its own Flow
2. Run on a schedule or trigger
3. Can share mem0 with main ClaraFlow

## Troubleshooting

### "MemoryManager not initialized"

The adapter must call `MemoryManager.initialize(llm)` before running flows. This happens in `ClaraDiscordBot.__init__()`.

### CrewAI Flow hangs

Check if mem0 is configured correctly. If Qdrant/pgvector isn't available, mem0 calls may timeout.

### Response is empty

Check logs for `[flow]` messages. The flow logs each step:
```
[flow] Received message from Username
[flow] Found 5 user, 2 project memories
[flow] Generating response with tier=mid
[flow] Response generated: 342 chars
```

## References

- [CrewAI Flows Documentation](https://docs.crewai.com/concepts/flows)
- [Original Spec](./clara-crewai-spec.md)
- [Environment Variables](../CLAUDE.md)
