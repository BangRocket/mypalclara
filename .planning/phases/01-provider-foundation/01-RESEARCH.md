# Phase 1: Provider Foundation - Research

**Researched:** 2026-01-27
**Domain:** Provider abstraction pattern, platform adapters, WebSocket protocol design
**Confidence:** HIGH

## Summary

This research investigated how to establish a provider abstraction layer for the Clara gateway that can wrap the existing Discord bot without rewriting its core logic. The goal is to create a clean separation between platform-specific code (Discord, Email, CLI) and the gateway's message processing pipeline using the Strangler Fig pattern.

The codebase already has excellent foundation work:
- `adapters/base.py` provides `GatewayClient` for WebSocket connections (client-side)
- `adapters/discord/adapter.py` demonstrates the Strangler Fig pattern with `DiscordAdapter`
- `clara_core/platform.py` defines `PlatformAdapter` and `PlatformMessage` abstractions
- `gateway/protocol.py` has comprehensive Pydantic message types with versioning support
- `gateway/server.py` and `gateway/processor.py` provide the server-side infrastructure

The key insight is that we need **providers that run inside the gateway process** (not as WebSocket clients), providing a standardized interface for the gateway to start/stop platform bots and normalize messages for processing.

**Primary recommendation:** Create a Provider base class pattern that mirrors `PlatformAdapter` but is designed for gateway-embedded platforms. Use composition to wrap existing bot implementations (like `ClaraDiscordBot`) without modifying their core logic. Establish clear lifecycle methods (start, stop, initialize) and message normalization (platform-specific → `PlatformMessage`).

## Standard Stack

The established patterns and libraries for provider abstraction in Python:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| abc (stdlib) | 3.12+ | Abstract Base Classes | Python's native mechanism for interface contracts, prevents instantiation of incomplete implementations |
| Pydantic | 2.x | Message validation/serialization | Already used in `gateway/protocol.py`, provides runtime validation, JSON serialization, and clear schema definition |
| asyncio (stdlib) | 3.12+ | Async lifecycle management | Required for Discord bot, gateway server, and all async operations |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| dataclasses (stdlib) | 3.12+ | Simple data containers | For internal structures that don't need validation (Pydantic is heavyweight for private classes) |
| discord.py | 2.x | Discord bot integration | Already in use, wrapped by provider |
| websockets | 13.x | WebSocket protocol | Already used by gateway server |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pydantic BaseModel | dataclass | Pydantic adds validation overhead but prevents bugs - worth it for protocol boundaries |
| Abstract Base Class | Protocol (typing) | ABC enforces implementation at instantiation, Protocol only at type-check time. ABC is better for runtime safety. |
| Embedded providers | WebSocket clients | WebSocket clients add network latency and complexity. Embedded providers are simpler for platforms running in the same process. |

**Installation:**
```bash
# Core dependencies already installed
poetry add pydantic  # 2.x
poetry add discord.py  # 2.x
```

## Architecture Patterns

### Recommended Project Structure
```
gateway/
├── providers/           # Provider implementations
│   ├── __init__.py     # ProviderManager singleton
│   ├── base.py         # Provider ABC
│   ├── discord.py      # DiscordProvider wrapping discord_bot.py
│   └── email.py        # EmailProvider (future)
├── protocol.py         # Existing WebSocket protocol (keep as-is)
├── server.py           # Existing gateway server (minimal changes)
└── processor.py        # Existing processor (use normalized messages)
```

### Pattern 1: Provider ABC with Lifecycle Methods
**What:** Abstract base class defining the interface all providers must implement
**When to use:** Every platform integration (Discord, Email, CLI)
**Example:**
```python
# Source: Based on adapters/base.py and clara_core/platform.py patterns
from abc import ABC, abstractmethod
from typing import AsyncIterator

class Provider(ABC):
    """Base class for platform providers running inside the gateway.

    Providers are responsible for:
    1. Starting/stopping their platform bot (Discord, Email monitor, etc.)
    2. Normalizing platform messages to PlatformMessage
    3. Sending responses back through their platform
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (e.g., 'discord', 'email')."""
        ...

    @abstractmethod
    async def start(self) -> None:
        """Start the provider (initialize bot, connect to platform)."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop the provider (cleanup, disconnect)."""
        ...

    @abstractmethod
    def normalize_message(self, platform_msg: Any) -> PlatformMessage:
        """Convert platform-specific message to PlatformMessage."""
        ...

    @abstractmethod
    async def send_response(
        self,
        context: dict,
        content: str,
        files: list[str] | None = None
    ) -> None:
        """Send response through the platform."""
        ...
```

### Pattern 2: ProviderManager Singleton
**What:** Central registry managing provider lifecycle
**When to use:** Gateway startup/shutdown, provider discovery
**Example:**
```python
# Source: Inspired by clara_core/mcp/manager.py pattern
class ProviderManager:
    """Singleton managing all platform providers."""

    _instance = None

    def __init__(self):
        self._providers: dict[str, Provider] = {}
        self._running = False

    @classmethod
    def get_instance(cls) -> ProviderManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, provider: Provider) -> None:
        """Register a provider."""
        self._providers[provider.name] = provider

    async def start_all(self) -> None:
        """Start all registered providers."""
        for name, provider in self._providers.items():
            logger.info(f"Starting provider: {name}")
            await provider.start()
        self._running = True

    async def stop_all(self) -> None:
        """Stop all providers."""
        for name, provider in self._providers.items():
            logger.info(f"Stopping provider: {name}")
            await provider.stop()
        self._running = False
```

### Pattern 3: Strangler Fig Wrapping
**What:** Wrap existing bot code without rewriting it
**When to use:** Migrating legacy code to new architecture
**Example:**
```python
# Source: adapters/discord/adapter.py demonstrates this pattern
class DiscordProvider(Provider):
    """Wraps the existing ClaraDiscordBot using Strangler Fig pattern."""

    def __init__(self):
        self._bot = None  # Will be ClaraDiscordBot instance
        self._bot_task = None

    async def start(self) -> None:
        """Start Discord bot in background task."""
        from discord_bot import ClaraDiscordBot

        self._bot = ClaraDiscordBot()
        # Override message handler to route through provider
        self._bot._original_handle = self._bot._handle_message
        self._bot._handle_message = self._intercept_message

        self._bot_task = asyncio.create_task(self._bot.start(DISCORD_TOKEN))

    async def _intercept_message(self, discord_msg, is_dm=False):
        """Intercept messages before bot processes them."""
        # Normalize to PlatformMessage
        platform_msg = self.normalize_message(discord_msg)

        # Let gateway processor handle it
        response = await gateway_processor.process(platform_msg)

        # Send response through Discord
        if response:
            await self.send_response(discord_msg.channel, response)
```

### Pattern 4: Protocol Versioning
**What:** Add version field to all messages for future compatibility
**When to use:** All WebSocket messages (already partially implemented)
**Example:**
```python
# Source: gateway/protocol.py already has MessageType enum
# Add protocol_version to base messages
class RegisterMessage(BaseModel):
    type: Literal[MessageType.REGISTER] = MessageType.REGISTER
    protocol_version: str = "1.0.0"  # Add this field
    node_id: str
    platform: str
    capabilities: list[str] = Field(default_factory=list)
```

### Anti-Patterns to Avoid
- **Don't rewrite discord_bot.py**: Use composition and delegation instead. The existing bot has 4000+ lines of proven logic - wrapping is safer than rewriting.
- **Don't make providers WebSocket clients**: Providers run in-process with the gateway. WebSocket clients (like CLI adapter) are a different concept.
- **Don't mix provider and adapter concepts**: Providers are server-side (embedded in gateway), adapters are client-side (connect to gateway via WebSocket).

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Message validation | Manual dict checking | Pydantic models | Already used in `gateway/protocol.py`, handles validation, serialization, and documentation |
| Abstract base classes | Duck typing | abc.ABC with @abstractmethod | Prevents runtime errors from missing methods, better IDE support |
| Async lifecycle | Manual task tracking | Structured concurrency patterns | Python 3.11+ asyncio.TaskGroup, or manual task tracking like in discord_bot.py |
| Singleton pattern | Global variables | Class with _instance and get_instance() | Thread-safe, testable, already used in MemoryManager |

**Key insight:** The codebase already has excellent patterns established. Don't invent new approaches - follow what's working in `adapters/`, `gateway/protocol.py`, and `clara_core/mcp/manager.py`.

## Common Pitfalls

### Pitfall 1: Trying to Rewrite Discord Bot Logic
**What goes wrong:** Attempting to extract and refactor discord_bot.py's 4000+ lines of logic leads to bugs and lost functionality
**Why it happens:** The temptation to "do it right" instead of incrementally improve
**How to avoid:** Use the Strangler Fig pattern - wrap, don't rewrite. Keep the existing `_handle_message`, `_generate_response`, and tool execution logic intact. Only add a thin provider wrapper that normalizes input/output.
**Warning signs:**
- Finding yourself copying methods from discord_bot.py
- Changing core bot behavior "while we're at it"
- Tests breaking or features being lost

### Pitfall 2: Confusing Providers and Adapters
**What goes wrong:** Mixing up the two concepts leads to incorrect architecture
**Why it happens:** Both deal with platform integration, names sound similar
**How to avoid:**
- **Providers** = Server-side, embedded in gateway, manage platform bots (Discord, Email)
- **Adapters** = Client-side, connect to gateway via WebSocket (CLI, future web dashboard)
- If it runs in the same process as the gateway → Provider
- If it connects remotely via WebSocket → Adapter (use GatewayClient)
**Warning signs:** Making DiscordProvider inherit from GatewayClient

### Pitfall 3: Breaking Existing Protocol
**What goes wrong:** Adding protocol_version field breaks existing CLI adapter
**Why it happens:** Protocol changes affect all clients
**How to avoid:**
- Make new fields optional with defaults: `protocol_version: str = "1.0.0"`
- Test with existing CLI adapter before merging
- Consider backward compatibility window
**Warning signs:** CLI adapter failing to connect after changes

### Pitfall 4: Over-abstracting Too Early
**What goes wrong:** Creating overly generic abstractions that don't match real needs
**Why it happens:** Trying to predict all future platforms
**How to avoid:**
- Start with Discord and Email (two concrete cases)
- Extract commonalities after second implementation
- PlatformMessage is already well-designed - reuse it
**Warning signs:**
- Abstract methods that only one provider implements
- Complex inheritance hierarchies
- Parameters that are only used by one platform

### Pitfall 5: Ignoring Existing Message Flow
**What goes wrong:** Provider sends messages directly instead of through gateway processor
**Why it happens:** Not understanding the gateway's role as central message hub
**How to avoid:**
- Providers normalize messages → Gateway processor builds context → LLM orchestrator generates response → Provider sends response
- Don't let providers call MemoryManager directly
- Don't let providers call LLM directly
- All processing goes through gateway/processor.py
**Warning signs:**
- Importing MemoryManager in provider code
- Calling make_llm() from provider
- Provider having its own context-building logic

## Code Examples

Verified patterns from codebase:

### Normalizing Discord Message to PlatformMessage
```python
# Source: adapters/discord/adapter.py lines 51-78
def normalize_message(self, discord_msg) -> PlatformMessage:
    """Convert Discord Message to PlatformMessage."""
    is_dm = discord_msg.guild is None

    return PlatformMessage(
        user_id=f"discord-{discord_msg.author.id}",
        platform="discord",
        platform_user_id=str(discord_msg.author.id),
        content=discord_msg.content,
        channel_id=str(discord_msg.channel.id),
        user_name=discord_msg.author.name,
        user_display_name=discord_msg.author.display_name,
        timestamp=discord_msg.created_at,
        metadata={
            "is_dm": is_dm,
            "guild_id": str(discord_msg.guild.id) if discord_msg.guild else None,
            "guild_name": discord_msg.guild.name if discord_msg.guild else None,
            "message_id": str(discord_msg.id),
            "channel_name": getattr(discord_msg.channel, "name", "DM"),
        },
    )
```

### Gateway Message Protocol (Already Well-Designed)
```python
# Source: gateway/protocol.py lines 142-163
class MessageRequest(BaseModel):
    """Adapter -> Gateway: Process a user message."""

    type: Literal[MessageType.MESSAGE] = MessageType.MESSAGE
    id: str = Field(..., description="Unique message ID for tracking")
    user: UserInfo = Field(..., description="User information")
    channel: ChannelInfo = Field(..., description="Channel information")
    content: str = Field(..., description="Message text content")
    attachments: list[AttachmentInfo] = Field(
        default_factory=list,
        description="Message attachments (images, files)",
    )
    reply_chain: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Previous messages in the reply chain",
    )
    tier_override: str | None = Field(None, description="Model tier override (high/mid/low)")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Platform-specific metadata",
    )
```

### Singleton Manager Pattern
```python
# Source: Adapted from clara_core/mcp/manager.py pattern
class ProviderManager:
    """Singleton for managing platform providers."""

    _instance: ProviderManager | None = None
    _lock = asyncio.Lock()

    def __init__(self):
        if ProviderManager._instance is not None:
            raise RuntimeError("Use ProviderManager.get_instance()")
        self._providers: dict[str, Provider] = {}
        self._initialized = False

    @classmethod
    def get_instance(cls) -> ProviderManager:
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def initialize(self) -> None:
        """Initialize all providers."""
        async with self._lock:
            if self._initialized:
                return

            # Providers register themselves during import
            # or can be registered explicitly
            self._initialized = True
```

### Discord Bot Lifecycle Wrapping
```python
# Source: Based on discord_bot.py async_main() pattern (lines 4116-4142)
class DiscordProvider(Provider):
    async def start(self) -> None:
        """Start Discord bot."""
        # Import here to avoid circular dependencies
        from discord_bot import ClaraDiscordBot, DISCORD_BOT_TOKEN

        self._bot = ClaraDiscordBot()

        # Start bot in background task (don't await)
        self._bot_task = asyncio.create_task(
            self._bot.start(DISCORD_BOT_TOKEN)
        )

        # Wait for bot to be ready
        await self._bot.wait_until_ready()
        logger.info(f"Discord provider started: {self._bot.user}")

    async def stop(self) -> None:
        """Stop Discord bot gracefully."""
        if self._bot:
            await self._bot.close()
        if self._bot_task:
            self._bot_task.cancel()
            try:
                await self._bot_task
            except asyncio.CancelledError:
                pass
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| WebSocket adapters for all platforms | Embedded providers for local platforms, WebSocket for remote | Ongoing migration | Reduces latency for Discord/Email, simplifies architecture |
| discord_bot.py as standalone | discord_bot.py wrapped by DiscordProvider | Phase 1 goal | Enables multi-platform gateway without rewriting bot |
| Hard-coded Discord logic in gateway | Platform-agnostic processor using PlatformMessage | Phase 1 goal | Gateway becomes reusable for any platform |
| No protocol versioning | Semantic versioning in all messages | Phase 1 goal | Enables backward-compatible protocol evolution |

**Deprecated/outdated:**
- **Direct Discord integration in gateway**: Gateway should be platform-agnostic, Discord is just one provider
- **Mixing adapter and provider concepts**: Current code has both - need to clarify the distinction

## Open Questions

Things that couldn't be fully resolved:

1. **How to handle Discord's event-driven architecture**
   - What we know: Discord bot uses `on_message` event handler
   - What's unclear: Best way to intercept messages before existing handler processes them
   - Recommendation: Override `on_message` in the bot instance after initialization, delegate to provider's message handler, then call original if needed

2. **Provider initialization order**
   - What we know: Gateway server must start before providers send messages
   - What's unclear: Should providers be initialized in gateway/main.py before or after server.start()?
   - Recommendation: Initialize ProviderManager between server creation and server.start(), but start providers after server is listening

3. **Email provider message batching**
   - What we know: Email monitor will need to batch notifications
   - What's unclear: Should batching happen in provider or processor?
   - Recommendation: Provider handles platform-specific batching (email dedup), processor handles general queuing (already exists in gateway/router.py)

4. **Protocol version compatibility**
   - What we know: Adding protocol_version field to existing messages
   - What's unclear: How to handle clients that don't send version?
   - Recommendation: Make field optional with default "1.0.0", log warning if absent for monitoring

## Sources

### Primary (HIGH confidence)
- Codebase analysis:
  - `adapters/base.py` - GatewayClient pattern for WebSocket adapters
  - `adapters/discord/adapter.py` - Strangler Fig pattern example
  - `clara_core/platform.py` - PlatformAdapter and PlatformMessage abstractions
  - `gateway/protocol.py` - Pydantic message protocol definitions
  - `gateway/server.py` - WebSocket server implementation
  - `gateway/processor.py` - Message processing pipeline
  - `discord_bot.py` - Existing Discord bot (4384 lines)

### Secondary (MEDIUM confidence)
- [Python's ABC: Enforcing patterns in classes](https://docs.python.org/3/library/abc.html) - Official Python documentation
- [Strangler Fig Pattern: Modernizing It Without Losing It](https://swimm.io/learn/legacy-code/strangler-fig-pattern-modernizing-it-without-losing-it) - Pattern overview
- [Pydantic Dataclasses](https://docs.pydantic.dev/latest/concepts/dataclasses/) - Validation approach

### Tertiary (LOW confidence)
- [Multi-Provider Strategy for App Configuration](https://devblogs.microsoft.com/ise/multi-provider-strategy-configuration-python/) - General provider patterns (not specific to our use case)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Libraries are already in use, proven in codebase
- Architecture: HIGH - Patterns exist in adapters/ directory, well-documented
- Pitfalls: HIGH - Based on analyzing existing code structure and common migration mistakes
- Protocol versioning: MEDIUM - Strategy is clear but implementation details need validation with CLI adapter
- Email provider specifics: MEDIUM - Gateway router exists but email batching needs design

**Research date:** 2026-01-27
**Valid until:** 2026-02-27 (30 days - stable architecture patterns)
