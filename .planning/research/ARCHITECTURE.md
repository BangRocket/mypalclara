# Architecture Patterns: Multi-Provider Gateway System

**Domain:** Multi-platform messaging gateway with provider abstraction
**Researched:** 2026-01-27
**Confidence:** HIGH

## Executive Summary

Multi-provider gateway systems have matured significantly by 2026, particularly in the AI/LLM space where gateways evolved from simple API proxies to critical infrastructure for production applications. The architecture consolidates platform-specific logic (Discord, Email, CLI) into pluggable providers managed BY a central gateway daemon, reversing the current pattern where providers connect TO the gateway.

This research examines proven patterns from:
- AI Gateway evolution (OpenRouter, Portkey, AWS Multi-Provider Gateway)
- Chat platform architectures (Discord, Slack microservices patterns)
- Strangler Fig migration strategies (AWS/Azure prescriptive guidance)
- Hexagonal/Ports-and-Adapters pattern (domain-driven design)

## Recommended Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Gateway Daemon                            │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                     Gateway Core                          │  │
│  │  - WebSocket Server (existing, for remote adapters)      │  │
│  │  - Provider Manager (new, for managed providers)         │  │
│  │  - Message Router (queuing, batching, cancellation)      │  │
│  │  - Session Manager (user sessions, timeouts)             │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              ↕                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                  Processing Pipeline                      │  │
│  │  - MessageProcessor (context building)                    │  │
│  │  - LLMOrchestrator (tool loop, streaming)                │  │
│  │  - ToolExecutor (sandbox, MCP, local files)              │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              ↕                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                  Shared Resources                         │  │
│  │  - MemoryManager (mem0, graph, sessions)                 │  │
│  │  - Database (SQLAlchemy, sessions, channel config)       │  │
│  │  - Hooks/Scheduler (events, tasks)                       │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                           ↕            ↕
        ┌──────────────────┴────────────┴─────────────────┐
        │                                                  │
┌───────▼──────────┐        ┌────────────────┐    ┌──────▼──────┐
│  Discord Provider│        │ Remote Adapters│    │Email Provider│
│  (Managed)       │        │  (WebSocket)   │    │  (Managed)  │
│  - discord.py    │        │  - CLI client  │    │  - IMAP     │
│  - events→msgs   │        │  - Future      │    │  - Monitor  │
│  - msgs→discord  │        │    adapters    │    │  - Actions  │
└──────────────────┘        └────────────────┘    └─────────────┘
```

### Two-Mode Provider System

The gateway supports TWO types of providers:

**1. Managed Providers (NEW pattern)**
- Run INSIDE the gateway daemon process
- Gateway lifecycle manages provider lifecycle (start/stop/restart)
- Direct function calls (no WebSocket overhead)
- Examples: Discord (discord.py bot), Email (IMAP monitor)
- Use case: Complex integrations with persistent state

**2. Remote Adapters (EXISTING pattern)**
- Run as SEPARATE processes/services
- Connect TO gateway via WebSocket
- Gateway client handles reconnection, heartbeats
- Examples: CLI client, future web interface
- Use case: Simple integrations, multi-process deployments

### Component Boundaries

| Component | Responsibility | Manages | Communicates With |
|-----------|---------------|---------|-------------------|
| **Gateway Core** | Central orchestration, lifecycle management | Provider registry, routing, sessions | All providers, processing pipeline |
| **Provider Manager** | Managed provider lifecycle (start/stop/restart) | Discord provider, Email provider, future providers | Gateway core, individual providers |
| **WebSocket Server** | Remote adapter connections | WebSocket sessions, registration, heartbeats | Remote adapters (CLI, future web) |
| **Message Router** | Queueing, batching, cancellation | Channel queues, active requests, task tracking | Providers (both types), MessageProcessor |
| **MessageProcessor** | Context building, memory fetch | Prompt construction, conversation history | LLMOrchestrator, MemoryManager, Providers (for responses) |
| **LLMOrchestrator** | Multi-turn tool loop, streaming | Tool call detection, result accumulation | ToolExecutor, LLM backends, Providers (for tool status) |
| **ToolExecutor** | Tool routing and execution | Sandbox, MCP servers, file storage, modular tools | Sandbox manager, MCP manager, file manager |
| **MemoryManager** | User/project memory, sessions | mem0, graph DB, session summaries | MessageProcessor, database |
| **Provider (Interface)** | Platform abstraction | Platform-specific message format conversion | Gateway core, MessageProcessor |
| **Discord Provider** | Discord bot lifecycle | discord.py client, event handlers, DM/server logic | Gateway core via provider interface |
| **Email Provider** | Email monitoring | IMAP connections, rule engine, alert dispatching | Gateway core via provider interface |

### Data Flow

#### Incoming Message Flow (Managed Provider)

```
1. Platform Event
   Discord: on_message event from discord.py
   Email: new message detected by IMAP monitor

2. Provider Normalization
   Provider.normalize_message(platform_event)
   → PlatformMessage(user, channel, content, attachments, metadata)

3. Gateway Routing
   Gateway.submit_message(message, provider_id)
   → MessageRouter.submit(message)
   → Queue or immediate processing (based on channel busy state)

4. Context Building
   MessageProcessor.process(message)
   - Fetch memories from mem0
   - Build reply chain from history
   - Construct system + user messages

5. LLM Processing
   LLMOrchestrator.generate_with_tools(messages, tools)
   - Streaming response generation
   - Tool detection and execution
   - Multi-turn loop until completion

6. Response Streaming (back to provider)
   For each event:
   - provider.on_response_start(response_id)
   - provider.on_tool_start(tool_name, step)
   - provider.on_tool_result(tool_name, success, preview)
   - provider.on_response_chunk(chunk)
   - provider.on_response_end(full_text, files)

7. Platform Delivery
   Provider.send_response(channel, content, files)
   Discord: channel.send(content, files=discord_files)
   Email: smtp.send_reply(to, subject, body)
```

#### Incoming Message Flow (Remote Adapter)

```
1. Adapter Connection
   Adapter connects via WebSocket
   → RegisterMessage
   → Gateway assigns node_id, session_id

2. Message Submission
   Adapter.send_message(user, channel, content, attachments)
   → MessageRequest over WebSocket
   → Gateway.handle_message_request()
   → MessageRouter.submit()

3-5. [Same as managed provider: Context → LLM → Tools]

6. Response Streaming (over WebSocket)
   Gateway → Adapter:
   - ResponseStart
   - ToolStart (repeated)
   - ToolResult (repeated)
   - ResponseChunk (repeated)
   - ResponseEnd

7. Adapter Delivery
   Adapter.on_response_end(message)
   → Adapter-specific platform delivery
```

#### Outgoing Proactive Flow (ORS - Future)

```
1. Scheduler/Hook Trigger
   Scheduled task or event hook fires
   → ORS system generates proactive message

2. Target Resolution
   ORS identifies user_id, channel_id
   → Gateway.send_proactive(user, channel, content)

3. Provider Lookup
   Gateway finds provider managing that channel
   Managed: Direct function call
   Remote: WebSocket ProactiveMessage

4. Platform Delivery
   Provider delivers proactive message
   Discord: channel.send(content, mention=user)
   Email: smtp.send(to, subject, body)
```

### Critical Interfaces

#### Provider Interface (Base Class)

```python
class Provider(ABC):
    """Base provider interface for all platform integrations."""

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Platform identifier (discord, email, slack, etc.)"""
        ...

    @abstractmethod
    async def start(self) -> None:
        """Start the provider (connect, authenticate, begin listening)"""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop the provider gracefully"""
        ...

    @abstractmethod
    def normalize_message(self, event: Any) -> PlatformMessage:
        """Convert platform-specific event to PlatformMessage"""
        ...

    @abstractmethod
    async def send_response(
        self,
        channel_id: str,
        content: str,
        files: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Send response to platform channel"""
        ...

    # Response streaming callbacks
    async def on_response_start(self, response_id: str, request_id: str) -> None: ...
    async def on_tool_start(self, tool_name: str, step: int, emoji: str) -> None: ...
    async def on_tool_result(self, tool_name: str, success: bool) -> None: ...
    async def on_response_chunk(self, chunk: str, accumulated: str) -> None: ...
    async def on_response_end(self, full_text: str, files: list[str]) -> None: ...
```

#### Message Normalization

```python
@dataclass
class PlatformMessage:
    """Normalized message from any platform"""
    id: str                          # Unique message ID
    user: UserInfo                   # User who sent the message
    channel: ChannelInfo             # Channel where message was sent
    content: str                     # Message text
    attachments: list[AttachmentInfo]  # Files, images, etc.
    reply_chain: list[dict]          # Conversation context
    tier_override: str | None        # Model tier (high/mid/low)
    metadata: dict[str, Any]         # Platform-specific extras
```

#### Gateway → Provider Communication

Managed providers receive callbacks directly (function calls).
Remote adapters receive WebSocket messages (JSON).

Both support the same event types:
- `response_start` - Response generation started
- `tool_start` - Tool execution started (with emoji, step number)
- `tool_result` - Tool execution completed (success/failure)
- `response_chunk` - Streaming text chunk
- `response_end` - Response complete (with files to attach)

## Patterns to Follow

### Pattern 1: Provider Lifecycle Management

**What:** Gateway controls provider startup, shutdown, and restarts.

**When:** For providers that need to run inside the gateway process (Discord bot, Email monitor).

**Why:**
- Single process deployment (simpler than multi-process)
- Direct function calls (lower latency than WebSocket)
- Unified logging and monitoring
- Graceful shutdown coordination

**Example:**
```python
class GatewayDaemon:
    def __init__(self):
        self.provider_manager = ProviderManager()
        self.ws_server = WebSocketServer()

    async def start(self):
        # Start managed providers
        await self.provider_manager.start_all()

        # Start WebSocket server for remote adapters
        await self.ws_server.start()

    async def stop(self):
        # Stop in reverse order
        await self.ws_server.stop()
        await self.provider_manager.stop_all()
```

### Pattern 2: Message Normalization at Provider Boundary

**What:** Each provider translates platform-specific objects to `PlatformMessage` at ingress, and translates `PlatformMessage` back to platform format at egress.

**When:** Always. All message processing uses the normalized format.

**Why:**
- Processing pipeline is platform-agnostic
- Adding new platforms doesn't change core logic
- Testing is easier (mock PlatformMessage, not Discord/Email objects)

**Example:**
```python
# Discord provider
def normalize_message(self, discord_msg: discord.Message) -> PlatformMessage:
    return PlatformMessage(
        id=f"discord-{discord_msg.id}",
        user=UserInfo(
            id=self.format_user_id(str(discord_msg.author.id)),
            platform_id=str(discord_msg.author.id),
            name=discord_msg.author.name,
            display_name=discord_msg.author.display_name,
        ),
        channel=ChannelInfo(
            id=str(discord_msg.channel.id),
            type="dm" if discord_msg.guild is None else "server",
            name=getattr(discord_msg.channel, "name", None),
        ),
        content=discord_msg.content,
        # ... etc
    )
```

### Pattern 3: Strangler Fig Migration

**What:** Wrap existing code (discord_bot.py) in a provider interface without rewriting it first.

**When:** Migrating large, working codebases to new architecture.

**Why:**
- Reduces risk (existing code keeps working)
- Allows incremental migration
- Provides immediate value (new providers can be added)
- Team can refactor internals later

**Example:**
```python
class DiscordProvider(Provider):
    def __init__(self):
        # Wrap existing ClaraDiscordBot
        self.bot = ClaraDiscordBot(...)

    async def start(self):
        # Delegate to existing bot startup
        await self.bot.start(self.token)

    def normalize_message(self, event):
        # Convert discord.Message → PlatformMessage
        return PlatformMessage(...)
```

**Migration phases:**
1. Wrap discord_bot.py in DiscordProvider (no internal changes)
2. Extract email monitoring to EmailProvider
3. Gradually move shared logic to gateway core
4. Eventually refactor provider internals

### Pattern 4: Dual-Mode Provider System

**What:** Support both managed (in-process) and remote (WebSocket) providers.

**When:**
- Managed: Complex integrations (Discord, Email) with persistent state
- Remote: Simple integrations, multi-process deployments, language barriers

**Why:**
- Flexibility: Choose deployment model per provider
- Performance: Managed providers avoid serialization overhead
- Isolation: Remote adapters can crash independently
- Language-agnostic: Remote adapters can be written in any language

**Example:**
```python
class Gateway:
    def __init__(self):
        self.managed_providers: dict[str, Provider] = {}
        self.remote_adapters: dict[str, WebSocketSession] = {}

    async def route_message(self, msg: PlatformMessage):
        # Determine provider type
        if msg.metadata.get("provider_type") == "managed":
            provider = self.managed_providers.get(msg.metadata["platform"])
            if provider:
                await self._process_via_managed(provider, msg)
        else:
            # Remote adapter (WebSocket)
            session = self.remote_adapters.get(msg.metadata["node_id"])
            if session:
                await self._process_via_remote(session, msg)
```

### Pattern 5: Anti-Corruption Layer (ACL)

**What:** Provider interface acts as an ACL, preventing platform-specific types from leaking into the core.

**When:** Always. Never pass `discord.Message` or `email.Message` to processing pipeline.

**Why:**
- Core remains platform-agnostic
- Tests don't need to mock Discord/Email libraries
- Easier to add new platforms
- Core can evolve independently of platform SDKs

**Example:**
```python
# BAD: Platform type leaks into core
async def process_message(discord_msg: discord.Message):
    await llm_orchestrator.generate(discord_msg.content)
    await discord_msg.channel.send(response)

# GOOD: ACL at provider boundary
async def process_message(msg: PlatformMessage):
    await llm_orchestrator.generate(msg.content)
    await provider.send_response(msg.channel.id, response)
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Providers Connect TO Gateway

**What:** Making Discord and Email run as separate processes that connect to gateway via WebSocket.

**Why bad:**
- Unnecessary complexity: discord.py already manages connections internally
- Double WebSocket: Discord ↔ discord.py ↔ gateway (instead of Discord ↔ gateway)
- Serialization overhead: Every message crosses process boundary
- State synchronization: Session state split across processes
- Deployment complexity: Multiple processes to manage

**Instead:** Run Discord/Email providers INSIDE the gateway process, managed by ProviderManager.

**Exception:** Remote adapters (CLI, future web) SHOULD connect via WebSocket because they're simple, stateless, or written in different languages.

### Anti-Pattern 2: Fat Providers

**What:** Putting LLM logic, tool execution, or memory management inside providers.

**Why bad:**
- Logic duplication: Each provider reimplements the same features
- Inconsistent behavior: Discord and Email handle tools differently
- Hard to test: Can't test LLM logic without spinning up Discord
- Tight coupling: Changes to memory system require updating all providers

**Instead:** Providers are THIN adapters that normalize messages and send responses. All processing happens in the shared pipeline (MessageProcessor, LLMOrchestrator, ToolExecutor).

### Anti-Pattern 3: Shared Mutable State

**What:** Providers directly access global variables or singleton state without synchronization.

**Why bad:**
- Race conditions: Discord and Email modify state concurrently
- Deadlocks: Two providers wait on each other's locks
- Hard to debug: Non-deterministic failures

**Instead:**
- Use message passing (async queues) for cross-provider communication
- MemoryManager handles all database access (SQLAlchemy sessions)
- Gateway Core routes messages (providers don't talk to each other)

### Anti-Pattern 4: Blocking I/O in Async Context

**What:** Calling blocking APIs (mem0, OpenAI, database) from async provider code without `run_in_executor`.

**Why bad:**
- Blocks event loop: Discord stops responding while waiting for mem0
- Cascading failures: One slow request blocks all providers
- Poor user experience: Bot appears frozen

**Instead:** Use ThreadPoolExecutor for all blocking calls:
```python
# Existing pattern in MessageProcessor
loop = asyncio.get_event_loop()
result = await loop.run_in_executor(BLOCKING_EXECUTOR, blocking_fn, args)
```

### Anti-Pattern 5: Platform-Specific Core Logic

**What:** Adding `if platform == "discord"` conditionals in MessageProcessor or LLMOrchestrator.

**Why bad:**
- Core becomes platform-aware (defeats abstraction)
- Adding platforms requires core changes
- Hard to test: Need to mock multiple platforms

**Instead:**
- Put platform-specific logic in providers
- Use metadata dict for platform-specific data
- Extend PlatformMessage/ChannelInfo if new platforms need common fields

## Scalability Considerations

| Concern | Single Gateway Process | Distributed (Future) |
|---------|----------------------|----------------------|
| **Message throughput** | Async I/O handles 1K+ msg/sec with single process | Horizontal scaling with load balancer + multiple gateway instances |
| **Provider isolation** | Managed providers share process; remote adapters isolated | All providers as remote adapters; gateway stateless |
| **Tool execution** | ThreadPoolExecutor (10-20 workers) | Separate tool executor service; gateway delegates via RPC |
| **Memory/session state** | Shared PostgreSQL; mem0 in-process | Redis for session cache; PostgreSQL for persistence |
| **Deployment** | Single container (Discord + Email + Gateway) | Separate containers; Kubernetes orchestration |

**Recommended approach:** Start with single process (managed providers). Migrate to distributed only when:
- Message volume exceeds 10K/min
- Provider crashes affect other providers
- Tool execution saturates CPU/memory

## Build Order and Dependencies

### Phase Dependencies

```
Foundation (No Dependencies):
├─ Gateway Protocol (existing, stable)
└─ Provider Interface (abstract base class)

Phase 1: Provider Abstraction (Week 1)
├─ Depends: Provider Interface
├─ Provider Manager (lifecycle, registry)
├─ PlatformMessage normalization
└─ Provider → Gateway communication contracts

Phase 2: Discord Provider Extraction (Week 1-2)
├─ Depends: Provider Abstraction
├─ Wrap discord_bot.py in DiscordProvider
├─ Route Discord events through Provider interface
└─ Verify: Existing Discord functionality unchanged

Phase 3: Gateway Integration (Week 2)
├─ Depends: Discord Provider
├─ Gateway starts/stops DiscordProvider
├─ MessageProcessor accepts PlatformMessage (not discord.Message)
└─ Verify: End-to-end flow works (Discord → Gateway → LLM → Discord)

Phase 4: Email Provider (Week 2-3)
├─ Depends: Gateway Integration
├─ Extract email_monitor.py to EmailProvider
├─ Normalize email messages to PlatformMessage
└─ Verify: Email alerts work through gateway

Phase 5: Consolidation (Week 3)
├─ Depends: All providers working
├─ Remove discord_bot.py as entrypoint (use gateway/__main__.py)
├─ Move shared code to gateway/shared/
└─ Update docker-compose.yml
```

### Suggested Build Order

**Week 1: Foundation + Discord Provider**

1. **Provider Interface** (1 day)
   - Create `gateway/providers/base.py` with Provider abstract class
   - Define PlatformMessage, UserInfo, ChannelInfo dataclasses
   - No dependencies on existing code

2. **Provider Manager** (1 day)
   - Create `gateway/providers/manager.py`
   - `start_provider()`, `stop_provider()`, `get_provider()` methods
   - Registry dict: `platform_name → Provider instance`
   - No actual providers yet (empty registry)

3. **Discord Provider Wrapper** (2 days)
   - Create `gateway/providers/discord_provider.py`
   - Instantiate ClaraDiscordBot inside DiscordProvider
   - Forward discord.py events to `normalize_message()`
   - Forward `send_response()` calls to `channel.send()`
   - **Key:** Don't modify discord_bot.py yet (Strangler Fig)

4. **Integration Test** (1 day)
   - Test script that starts DiscordProvider standalone
   - Verify Discord events → PlatformMessage conversion
   - Verify PlatformMessage → Discord send works
   - Confirm: Bot functionality unchanged

**Week 2: Gateway Integration + Email Provider**

5. **Gateway Entry Point** (1 day)
   - Modify `gateway/main.py` to start ProviderManager
   - `gateway.add_provider(DiscordProvider(...))`
   - `await gateway.start()` starts both gateway server AND providers
   - Test: Discord bot starts when gateway starts

6. **MessageProcessor Adaptation** (2 days)
   - Modify `processor.process()` to accept PlatformMessage (not MessageRequest)
   - Update `_build_context()` to work with PlatformMessage
   - Add provider callback hooks for response streaming
   - Test: Discord message → LLM → Discord response works

7. **Email Provider** (2 days)
   - Create `gateway/providers/email_provider.py`
   - Move email monitoring logic from `email_monitor.py`
   - Normalize email alerts to PlatformMessage
   - Forward responses to SMTP send
   - Test: Email alert triggers proactive message

**Week 3: Cleanup + Documentation**

8. **Consolidation** (2 days)
   - Update `docker-compose.yml`: Single service runs gateway
   - Remove `discord_bot.py` as entrypoint (redirect to `gateway/__main__.py`)
   - Move shared utilities to `gateway/shared/`
   - Update environment variable docs

9. **Refactoring** (2 days)
   - Begin extracting shared Discord logic from discord_bot.py
   - Move generic message handling to gateway core
   - Leave Discord-specific features in DiscordProvider
   - Goal: Reduce discord_bot.py from 4400 lines to ~2000 lines

10. **Testing + Documentation** (1 day)
    - Integration tests for all provider types
    - Update CLAUDE.md with provider architecture
    - Deployment guide

### Critical Path

The critical path (minimum required for deployment):
1. Provider Interface → 2. Provider Manager → 3. Discord Provider → 6. MessageProcessor Adaptation

Everything else can be parallelized or deferred:
- Email Provider (parallel with Discord testing)
- Consolidation (post-deployment)
- Refactoring (continuous, post-deployment)

### Risk Mitigation

**Risk 1:** Discord provider breaks existing bot functionality
- **Mitigation:** Strangler Fig pattern (wrap, don't rewrite)
- **Validation:** Side-by-side testing (old bot vs new provider)

**Risk 2:** Gateway restart kills all providers (Discord connection lost)
- **Mitigation:** Discord auto-reconnect (existing in discord.py)
- **Future:** Separate discord container + WebSocket adapter

**Risk 3:** Blocking I/O in providers deadlocks event loop
- **Mitigation:** Audit all provider code for blocking calls
- **Tooling:** Add `asyncio.run_in_executor()` wrappers

**Risk 4:** Memory leaks from provider objects not being cleaned up
- **Mitigation:** Explicit cleanup in `provider.stop()`
- **Monitoring:** Track process memory usage in dashboard

## Sources and References

### Multi-Provider Gateway Architecture
- [AWS Multi-Provider Generative AI Gateway](https://aws.amazon.com/blogs/machine-learning/streamline-ai-operations-with-the-multi-provider-generative-ai-gateway-reference-architecture/)
- [Top 5 AI Gateways for 2026](https://dev.to/kuldeep_paul/top-5-ai-gateways-for-2026-building-reliable-multi-provider-ai-infrastructure-16e3)
- [Gateway Routing Pattern - Azure](https://learn.microsoft.com/en-us/azure/architecture/patterns/gateway-routing)
- [API Gateway Pattern - AWS Prescriptive Guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/modernization-integrating-microservices/api-gateway-pattern.html)

### Platform Adapter Pattern
- [Gateway Pattern - Martin Fowler](https://martinfowler.com/articles/gateway-pattern.html)
- [Adapter Pattern in Microservices](https://medium.com/@jescrich_57703/harnessing-the-adapter-pattern-in-microservice-architectures-for-vendor-agnosticism-debc21d2fe21)
- [Hexagonal Architecture (Ports and Adapters) - AWS](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/hexagonal-architecture.html)
- [Backend for Frontend (BFF) Pattern - Microsoft](https://learn.microsoft.com/en-us/dotnet/architecture/microservices/architect-microservice-container-applications/direct-client-to-microservice-communication-versus-the-api-gateway-pattern)

### Chat Platform Architecture
- [Slack Architecture - System Design](https://systemdesign.one/slack-architecture/)
- [Discord Architecture Explained](https://chrisza.me/discord-architecture-alternative/)
- [Build a Distributed Messaging System like Discord](https://www.almabetter.com/bytes/articles/build-a-distributed-messaging-system-like-discord)
- [Real-time Chat Application Design](https://medium.com/@codeRohit/design-a-real-time-chat-application-like-slack-or-discord-d045922acb79)

### Strangler Fig Migration
- [Strangler Fig Pattern - AWS Prescriptive Guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/strangler-fig.html)
- [Strangler Fig Pattern - Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/patterns/strangler-fig)
- [Strangler Fig Application - Martin Fowler](https://martinfowler.com/bliki/StranglerFigApplication.html)
- [Microservices Pattern: Strangler Application](https://microservices.io/patterns/refactoring/strangler-application.html)

### LLM Gateway Architecture
- [What is an LLM Gateway?](https://medium.com/@yadav.navya1601/what-is-an-llm-gateway-understanding-the-infrastructure-layer-for-multi-model-ai-fea4fecbc931)
- [LLM Gateway Infrastructure](https://www.truefoundry.com/blog/llm-gateway)
- [How an LLM Gateway Helps Build Better AI Applications](https://dev.to/kuldeep_paul/how-an-llm-gateway-can-help-you-build-better-ai-applications-27hf)

---

**Confidence Level: HIGH**
- Architecture patterns verified from AWS, Azure, Martin Fowler
- Chat platform patterns verified from real systems (Discord, Slack)
- Existing codebase examined (gateway/, discord_bot.py, adapters/)
- Provider interface already partially implemented (adapters/base.py)
