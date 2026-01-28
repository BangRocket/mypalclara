# Phase 2: Gateway Integration & Email Provider - Research

**Researched:** 2026-01-27
**Domain:** WebSocket gateway integration, async callback protocols, provider extraction
**Confidence:** HIGH

## Summary

Phase 2 integrates DiscordProvider with the gateway's MessageProcessor pipeline and extracts email monitoring into EmailProvider. This research covers callback protocol design, WebSocket integration patterns, module extraction strategies, and behavioral testing approaches for Discord parity.

The existing codebase already has strong foundations:
- Gateway protocol with Pydantic models for type safety (gateway/protocol.py)
- Base adapter abstraction with WebSocket communication (adapters/base.py)
- Event system for cross-provider communication (gateway/events.py)
- Existing test patterns using pytest-asyncio (tests/gateway/)

**Primary recommendation:** Use the existing GatewayClient base class for DiscordProvider, implement response callbacks as async methods, and leverage the event system for email-to-Discord routing. Extract email_monitor.py to EmailProvider using the Strangler Fig pattern with feature flags.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| websockets | Latest | WebSocket client/server | Official Python WebSocket library, excellent async support |
| pydantic | 2.x | Message validation | Type-safe protocol definitions with serialization |
| pytest-asyncio | Latest | Async testing | Standard for testing asyncio code in pytest |
| discord.py | 2.x | Discord API client | Official Discord API wrapper with full feature support |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncio | stdlib | Async I/O | Core async runtime for all async operations |
| aiohttp | Latest | HTTP client (optional) | If EmailProvider needs HTTP-based email APIs |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| websockets | socket.io-python | More features (rooms, namespaces) but heavier and less standard |
| Pydantic | dataclasses | Simpler but loses validation and JSON serialization |
| pytest-asyncio | asynctest | Less maintained, pytest-asyncio is community standard |

**Installation:**
```bash
# Already in pyproject.toml
poetry install
```

## Architecture Patterns

### Recommended Project Structure
```
gateway/
├── processor.py        # MessageProcessor pipeline
├── llm_orchestrator.py # LLM with tool calling
├── events.py           # Event system
└── protocol.py         # WebSocket messages

adapters/
├── base.py             # GatewayClient base class
├── discord/
│   ├── adapter.py      # DiscordAdapter (from Phase 1)
│   ├── provider.py     # DiscordProvider (NEW)
│   └── gateway_client.py  # Discord WebSocket client
└── email/
    ├── provider.py     # EmailProvider (NEW)
    └── monitor.py      # Extracted email logic

tests/
└── adapters/
    ├── test_discord_provider.py  # Behavioral tests
    └── test_email_provider.py    # Email integration tests
```

### Pattern 1: Response Callback Protocol

**What:** Async callback methods for streaming LLM responses back to adapters

**When to use:** When the gateway needs to send multi-stage responses (start, chunks, tools, end)

**Example:**
```python
# Source: adapters/base.py (lines 334-357)
class GatewayClient(ABC):
    @abstractmethod
    async def on_response_start(self, message: ResponseStart) -> None:
        """Handle response start from gateway."""
        ...

    @abstractmethod
    async def on_response_chunk(self, message: ResponseChunk) -> None:
        """Handle streaming response chunk."""
        ...

    @abstractmethod
    async def on_tool_start(self, message: ToolStart) -> None:
        """Handle tool execution start."""
        ...
```

**Implementation for DiscordProvider:**
```python
class DiscordProvider(GatewayClient):
    def __init__(self, bot):
        super().__init__(platform="discord", capabilities=["streaming", "attachments"])
        self.bot = bot
        self._active_responses: dict[str, discord.Message] = {}

    async def on_response_start(self, message: ResponseStart) -> None:
        # Create initial "thinking" message
        placeholder = await channel.send("-# 🤔 Thinking...")
        self._active_responses[message.id] = placeholder

    async def on_response_chunk(self, message: ResponseChunk) -> None:
        # Stream chunks to Discord by editing the message
        if msg := self._active_responses.get(message.id):
            await msg.edit(content=message.accumulated[:2000])

    async def on_tool_start(self, message: ToolStart) -> None:
        # Show tool status like discord_bot.py does
        status = f"-# {message.emoji} {message.description or message.tool_name}..."
        if msg := self._active_responses.get(message.id):
            await msg.edit(content=msg.content + "\n" + status)
```

### Pattern 2: Event-Driven Cross-Provider Communication

**What:** Using the gateway event system for providers to communicate without direct coupling

**When to use:** When one provider needs to notify another (e.g., EmailProvider alerts via DiscordProvider)

**Example:**
```python
# Source: gateway/events.py (lines 78-203)
from gateway.events import Event, EventType, get_event_emitter

# EmailProvider emits email alert event
emitter = get_event_emitter()
await emitter.emit(Event(
    type=EventType.MESSAGE_RECEIVED,
    user_id="discord-123456789",
    channel_id="discord-987654321",
    data={
        "from": "recruiter@example.com",
        "subject": "Job opportunity",
        "preview": "We'd love to discuss...",
        "importance": "high"
    }
))

# DiscordProvider listens for email alerts
async def handle_email_alert(event: Event):
    if event.data.get("importance") == "high":
        user = await bot.fetch_user(int(event.user_id.split("-")[1]))
        await user.send(f"📬 **{event.data['subject']}**\n{event.data['preview']}")

emitter.on(EventType.MESSAGE_RECEIVED, handle_email_alert)
```

### Pattern 3: Strangler Fig Module Extraction

**What:** Gradually replace monolithic email_monitor.py with EmailProvider while keeping existing functionality working

**When to use:** When extracting a module that has complex dependencies and needs zero-downtime migration

**Example:**
```python
# Phase 1: Add feature flag (already exists for Discord)
USE_EMAIL_PROVIDER = os.getenv("USE_EMAIL_PROVIDER", "false").lower() == "true"

# Phase 2: Create EmailProvider wrapping existing code
class EmailProvider:
    def __init__(self):
        from email_monitor import EmailMonitor  # Import existing
        self.monitor = EmailMonitor()

    async def poll_accounts(self):
        # Delegate to existing implementation
        new_emails, error = self.monitor.get_new_emails()
        # Emit events instead of direct Discord messaging
        for email in new_emails:
            await emit(Event(type=EventType.MESSAGE_RECEIVED, ...))

# Phase 3: Conditional routing in discord_bot.py
if USE_EMAIL_PROVIDER:
    email_provider = EmailProvider()
    asyncio.create_task(email_provider.start())
else:
    asyncio.create_task(email_check_loop(bot))  # Existing code

# Phase 4: After validation, remove old code and feature flag
```

### Anti-Patterns to Avoid

- **Direct provider coupling:** EmailProvider should NOT import DiscordProvider. Use events.
- **Synchronous callbacks:** All callbacks must be async to avoid blocking the event loop
- **Shared mutable state:** Each provider manages its own state; gateway is stateless
- **Tight WebSocket coupling:** Providers should work with or without gateway (local mode)

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| WebSocket protocol | Custom binary protocol | Pydantic + JSON | Type safety, validation, easy debugging |
| Async callback dispatch | Manual asyncio.create_task() | Event emitter with handlers | Error isolation, priority ordering, wildcard listeners |
| Message queuing | Custom queue with locks | asyncio.Queue or deque | Thread-safe, well-tested, handles backpressure |
| Reconnection logic | Manual retry loops | Exponential backoff in GatewayClient | Already implemented with session preservation |
| Response streaming | Accumulate then send | Edit-in-place chunking | Discord UX matches existing bot, avoids rate limits |

**Key insight:** The existing gateway architecture already solved hard problems (WebSocket lifecycle, reconnection, protocol parsing). Building on adapters/base.py saves weeks of debugging edge cases.

## Common Pitfalls

### Pitfall 1: Blocking the Event Loop

**What goes wrong:** Synchronous I/O (IMAP, SMTP) blocks asyncio event loop, freezing all providers

**Why it happens:** email_monitor.py uses imaplib (sync) - easy to forget to wrap in executor

**How to avoid:**
```python
# BAD: Blocks event loop
def check_email():
    mail = imaplib.IMAP4_SSL(server, port)  # Blocks!
    mail.login(user, pass)
    return mail.search(None, "UNSEEN")

# GOOD: Run in thread executor
async def check_email():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        BLOCKING_EXECUTOR,
        _sync_check_email  # Sync function in thread
    )
```

**Warning signs:** Gateway becomes unresponsive when EmailProvider polls; other providers freeze

### Pitfall 2: Message ID Correlation Failures

**What goes wrong:** Response chunks lost or sent to wrong Discord message

**Why it happens:** Multiple concurrent requests with overlapping response_ids

**How to avoid:**
```python
# Track active responses per request_id, not response_id
self._active_responses: dict[str, tuple[str, discord.Message]] = {}
# Key: request_id -> (response_id, discord_message)

async def on_response_start(self, message: ResponseStart):
    # Store by request_id for lookup
    self._active_responses[message.request_id] = (message.id, discord_msg)

async def on_response_chunk(self, message: ResponseChunk):
    # Find by response_id
    for req_id, (resp_id, discord_msg) in self._active_responses.items():
        if resp_id == message.id:
            await discord_msg.edit(content=message.accumulated)
            break
```

**Warning signs:** Response chunks appear in wrong Discord channels; edit errors on deleted messages

### Pitfall 3: Email Alert Deduplication

**What goes wrong:** Same email alert sent multiple times if provider restarts during polling

**Why it happens:** Email UID tracking lost on provider restart; no persistent seen_uids

**How to avoid:**
```python
# Store seen UIDs in database, not in-memory set
from db.models import EmailAlert  # SQLAlchemy model

async def _is_email_seen(self, account_id: str, uid: str) -> bool:
    with SessionLocal() as db:
        return db.query(EmailAlert).filter_by(
            account_id=account_id, uid=uid
        ).first() is not None

async def _mark_email_seen(self, account_id: str, uid: str):
    with SessionLocal() as db:
        db.add(EmailAlert(account_id=account_id, uid=uid, alerted_at=datetime.now()))
        db.commit()
```

**Warning signs:** Duplicate email alerts after provider restarts; alerts for old emails on first run

### Pitfall 4: Discord Rate Limit Cascade

**What goes wrong:** Streaming responses edit messages too quickly, hit Discord rate limits (5 edits/5 seconds per message)

**Why it happens:** LLM streams chunks faster than Discord allows; naive chunk forwarding

**How to avoid:**
```python
# Debounce edits with rate limiter
class ResponseStreamer:
    def __init__(self):
        self._last_edit: dict[str, float] = {}
        self.edit_cooldown = 0.5  # 500ms between edits

    async def on_response_chunk(self, message: ResponseChunk):
        now = time.time()
        last = self._last_edit.get(message.id, 0)

        if now - last < self.edit_cooldown:
            # Accumulate chunks, edit later
            self._pending_chunks[message.id] = message.accumulated
        else:
            await self._edit_message(message.id, message.accumulated)
            self._last_edit[message.id] = now
```

**Warning signs:** 429 rate limit errors in logs; messages stop updating mid-response

### Pitfall 5: Memory Leak from Unclosed Responses

**What goes wrong:** `_active_responses` dict grows unbounded, causing OOM after days

**Why it happens:** on_response_end not called on errors; no cleanup on cancellation

**How to avoid:**
```python
async def on_response_end(self, message: ResponseEnd):
    # Always clean up, even if edit fails
    try:
        if discord_msg := self._active_responses.pop(message.id, None):
            await discord_msg.edit(content=message.full_text)
    except Exception as e:
        logger.error(f"Failed to finalize response: {e}")
        # Still removed from dict above

async def on_error(self, message: ErrorMessage):
    # Clean up on errors too
    self._active_responses.pop(message.request_id, None)
    await super().on_error(message)
```

**Warning signs:** Memory usage grows over time; stale entries in _active_responses

## Code Examples

Verified patterns from official sources:

### WebSocket Gateway Integration (MessageProcessor to Provider)

```python
# Source: gateway/processor.py (lines 94-202)
# This is how MessageProcessor currently sends responses

async def process(self, request: MessageRequest, websocket: WebSocketServerProtocol, server: GatewayServer):
    response_id = f"resp-{uuid.uuid4().hex[:8]}"

    # Send response start
    await self._send(websocket, ResponseStart(
        id=response_id,
        request_id=request.id,
        model_tier=request.tier_override,
    ))

    # Stream chunks and tools
    async for event in self._llm_orchestrator.generate_with_tools(...):
        if event_type == "tool_start":
            await self._send(websocket, ToolStart(
                id=response_id,
                tool_name=event["tool_name"],
                step=event["step"],
                emoji=self._get_tool_emoji(event["tool_name"]),
            ))
        elif event_type == "chunk":
            await self._send(websocket, ResponseChunk(
                id=response_id,
                chunk=chunk_text,
                accumulated=full_text,
            ))

    # Send completion
    await self._send(websocket, ResponseEnd(
        id=response_id,
        full_text=full_text,
        files=files,
        tool_count=tool_count,
    ))
```

**DiscordProvider receives these via GatewayClient._handle_message and routes to callbacks**

### Behavioral Test Pattern (Discord Parity)

```python
# Source: tests/gateway/test_events.py - shows async test patterns
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_discord_provider_streams_response():
    """Verify response streaming matches discord_bot.py behavior."""
    # Setup mock Discord bot and message
    mock_bot = AsyncMock()
    mock_channel = AsyncMock()
    mock_message = AsyncMock()
    mock_channel.send.return_value = mock_message

    provider = DiscordProvider(mock_bot)
    provider._current_channel = mock_channel

    # Simulate gateway response flow
    await provider.on_response_start(ResponseStart(
        id="resp-123",
        request_id="msg-456",
        model_tier="mid"
    ))

    # Should create initial message
    mock_channel.send.assert_called_once()
    assert "-# 🤔" in mock_channel.send.call_args[0][0]

    # Stream chunks
    await provider.on_response_chunk(ResponseChunk(
        id="resp-123",
        chunk="Hello ",
        accumulated="Hello "
    ))
    await provider.on_response_chunk(ResponseChunk(
        id="resp-123",
        chunk="world",
        accumulated="Hello world"
    ))

    # Should edit message with accumulated text
    assert mock_message.edit.call_count >= 1
    assert "Hello world" in mock_message.edit.call_args[1]["content"]

@pytest.mark.asyncio
async def test_message_queue_batching():
    """Verify active mode batching matches discord_bot.py queue behavior."""
    provider = DiscordProvider(mock_bot)

    # Simulate 3 rapid messages in active mode channel
    msg1 = provider.queue_message(user1, "First message")
    msg2 = provider.queue_message(user2, "Second message")
    msg3 = provider.queue_message(user1, "Third message")

    # Should batch consecutive active-mode messages
    batches = await provider._get_queued_batches(channel_id)
    assert len(batches) == 1  # Single batch
    assert len(batches[0]) == 3  # All 3 messages

    # Verify batch response format
    combined_context = provider._build_batch_context(batches[0])
    assert "[user1]: First message" in combined_context
    assert "[user2]: Second message" in combined_context
```

### Event-Based Email Alerting

```python
# EmailProvider emits events instead of direct Discord calls
from gateway.events import Event, EventType, emit

class EmailProvider:
    async def _process_new_email(self, email_info: EmailInfo, account: EmailAccount):
        # Evaluate importance using rules engine
        importance = await self._evaluate_importance(email_info)

        if importance != "ignore":
            # Emit event for any interested providers
            await emit(Event(
                type=EventType.MESSAGE_RECEIVED,
                platform="email",
                user_id=f"discord-{account.discord_user_id}",
                channel_id=account.alert_channel_id,
                data={
                    "provider": "email",
                    "from": email_info.from_addr,
                    "subject": email_info.subject,
                    "preview": email_info.preview,
                    "importance": importance,
                    "account": account.email_address,
                }
            ))

# DiscordProvider listens for email events
class DiscordProvider(GatewayClient):
    async def start(self):
        await super().start()

        # Register email alert handler
        emitter = get_event_emitter()
        emitter.on(EventType.MESSAGE_RECEIVED, self._handle_email_alert)

    async def _handle_email_alert(self, event: Event):
        if event.data.get("provider") != "email":
            return  # Not an email event

        # Extract Discord user/channel from event
        user_id = int(event.user_id.split("-")[1])
        channel_id = event.channel_id

        # Format alert message
        importance_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        emoji = importance_emoji.get(event.data["importance"], "📬")

        alert = (
            f"{emoji} **New Email**\n"
            f"**From:** {event.data['from']}\n"
            f"**Subject:** {event.data['subject']}\n"
            f"{event.data['preview']}"
        )

        # Send to Discord channel
        channel = await self.bot.fetch_channel(channel_id)
        await channel.send(alert)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Direct Discord imports in email_monitor.py | Event-driven provider architecture | Phase 2 (2026) | Enables multi-platform email alerts |
| Sync IMAP blocking event loop | AsyncIO executor wrapping | Required for gateway | Non-blocking email checks |
| Monolithic discord_bot.py | Modular DiscordProvider + EmailProvider | Strangler Fig pattern | Testable, maintainable providers |
| Feature flags per-provider | Unified provider registry | Phase 1 foundation | Consistent lifecycle management |

**Deprecated/outdated:**
- `email_check_loop()` in email_monitor.py: Replace with EmailProvider.poll_loop()
- Direct `bot.send()` calls: Replace with event emission for cross-provider alerts
- `USE_DISCORD_ADAPTER` feature flag: Will be removed after Phase 2 validation

## Open Questions

Things that couldn't be fully resolved:

1. **Tool execution context in DiscordProvider**
   - What we know: discord_bot.py creates ToolContext with sandbox, file manager, user_id
   - What's unclear: Should DiscordProvider manage ToolContext or delegate to gateway?
   - Recommendation: Keep ToolContext in gateway (already has ToolExecutor), provider only formats results

2. **Email provider polling interval tuning**
   - What we know: Current default is 60 seconds (CHECK_INTERVAL)
   - What's unclear: Should EmailProvider support per-account intervals? How to handle rate limits?
   - Recommendation: Start with single global interval, add per-account config in Phase 3 if needed

3. **Behavioral test coverage scope**
   - What we know: Need 20+ tests for Discord parity
   - What's unclear: Which discord_bot.py behaviors are critical vs. nice-to-have?
   - Recommendation: Focus on: message dedup, queue batching, tier selection, tool status, emotional context tracking, image handling

4. **Gateway vs. local mode for providers**
   - What we know: Some providers might want to run without gateway (standalone mode)
   - What's unclear: Should DiscordProvider support local mode or always require gateway?
   - Recommendation: Phase 2 gateway-only; add local mode in Phase 4 if CLI client needs it

## Sources

### Primary (HIGH confidence)
- gateway/processor.py - MessageProcessor implementation
- gateway/llm_orchestrator.py - LLM response generation
- gateway/events.py - Event system implementation
- adapters/base.py - GatewayClient base class
- email_monitor.py - Existing email monitoring logic
- discord_bot.py - Current Discord implementation (lines 1-800)
- tests/gateway/test_events.py - Test patterns

### Secondary (MEDIUM confidence)
- [WebSocket Gateway Reference Architecture](https://www.dasmeta.com/docs/solutions/websocket-gateway-reference-architecture/index) - Gateway patterns with message bus
- [AWS API Gateway WebSocket](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-websocket-api-overview.html) - Connection lifecycle management
- [Refactoring a monolith to microservices](https://microservices.io/refactoring/) - Strangler Fig pattern
- [From monolith to modular monolith](https://dev.to/sepehr/from-monolith-to-modular-monolith-to-microservices-realistic-migration-patterns-36f2) - Module extraction strategies

### Tertiary (LOW confidence)
- [Event-Driven Architecture with Python](https://www.tothenew.com/blog/design-implement-a-event-driven-architecture-in-python/) - Cross-provider communication patterns
- [async test patterns for Pytest](https://tonybaloney.github.io/posts/async-test-patterns-for-pytest-and-unittest.html) - Async testing approaches
- [dpytest documentation](https://dpytest.readthedocs.io/en/latest/tutorials/getting_started.html) - Discord bot testing library

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Libraries already in use, proven in production
- Architecture: HIGH - Patterns verified from existing codebase files
- Pitfalls: MEDIUM - Based on common async/Discord issues, not all observed in this codebase
- Code examples: HIGH - All examples from actual codebase files

**Research date:** 2026-01-27
**Valid until:** 2026-02-27 (30 days - stable domain, slow-moving libraries)
