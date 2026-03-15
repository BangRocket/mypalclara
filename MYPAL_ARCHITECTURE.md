# MyPal Architecture Plan

## Vision

MyPal is the next generation of MyPalClara — a multi-agent, multi-user, multi-tenant personal AI platform. Each agent is an independent persona with its own identity, memory, tools, and LLM configuration. Agents can spawn sub-agents for task delegation. The platform supports rich input modalities (voice, vision, files) and diverse interaction patterns (chat, API, webhooks, scheduled tasks, events).

**Stack**: Python-only backend (FastAPI replaces Rails), React frontend stays.

---

## 1. Core Architecture

### 1.1 Layered Design

```
┌─────────────────────────────────────────────────────┐
│                    Input Layer                       │
│  Adapters (Discord, Slack, Teams, Telegram, etc.)   │
│  API Gateway (REST/WebSocket)                       │
│  Webhooks / Scheduled Triggers / Event Sources      │
├─────────────────────────────────────────────────────┤
│                   Router / Dispatcher                │
│  Tenant resolution → Agent selection → Routing       │
├─────────────────────────────────────────────────────┤
│                   Agent Runtime Layer                │
│  Agent instances (Clara, Rex, custom...)             │
│  Sub-agent orchestration                            │
│  Tool execution, sandbox, MCP                       │
├─────────────────────────────────────────────────────┤
│                   Core Services                      │
│  Memory (Rook v2)  │  LLM Providers  │  Identity    │
│  Session Manager   │  Tool Registry  │  Permissions  │
├─────────────────────────────────────────────────────┤
│                   Data Layer                         │
│  PostgreSQL (relational)  │  pgvector (embeddings)  │
│  Redis (cache/pubsub)     │  FalkorDB (graph, opt)  │
└─────────────────────────────────────────────────────┘
```

### 1.2 Why Not the Current Gateway

The current gateway combines three concerns into one:
1. **Transport** (WebSocket server, adapter connections)
2. **Routing** (message dedup, debouncing, channel queuing)
3. **Processing** (context building, LLM calls, tool execution — all hardcoded for "Clara")

MyPal separates these cleanly. The transport layer stays thin. The router becomes tenant-and-agent-aware. Processing moves into pluggable agent runtimes.

### 1.3 What We Keep

| Component | Status | Notes |
|-----------|--------|-------|
| LLM Provider system | **Keep** | Already provider-agnostic. Add per-agent config. |
| Rook memory core | **Evolve** | Add agent scoping, cross-agent sharing, tenant isolation. |
| Adapter protocol | **Keep** | WebSocket protocol + adapter base class are solid. |
| Plugin system | **Keep** | Already supports the right plugin kinds. |
| Sandbox system | **Keep** | Clean abstraction, works as-is. |
| Message Router | **Evolve** | Add tenant/agent awareness to existing dedup/debounce. |
| Gateway Processor | **Replace** | Becomes the Agent Runtime layer. |
| Rails backend | **Replace** | FastAPI takes over all HTTP API duties. |
| Database models | **Evolve** | Add tenant, agent, and permission models. |

---

## 2. Agent System

### 2.1 Agent Definition

An agent is defined by a manifest (stored in DB, editable via API):

```python
@dataclass
class AgentDefinition:
    id: str                          # "clara", "rex", etc.
    tenant_id: str                   # Owning tenant
    name: str                        # Display name
    persona: PersonaConfig           # System prompt, personality traits, tone
    llm_config: LLMConfig            # Provider, model, tier defaults
    memory_config: MemoryConfig      # What memory scopes to use
    tools: list[str]                 # Enabled tool IDs / MCP servers
    capabilities: set[Capability]    # CHAT, CODE, VOICE, VISION, PROACTIVE, etc.
    sub_agents: list[str]            # Agent IDs this agent can delegate to
    max_concurrent: int              # Max concurrent conversations
    metadata: dict                   # Extensible config
```

### 2.2 Agent Runtime

Each active agent conversation gets an `AgentRuntime` instance:

```python
class AgentRuntime:
    definition: AgentDefinition
    session: Session
    memory: ScopedMemory            # Agent-scoped view of Rook
    llm: LLMProvider                # Configured per-agent
    tools: ToolRegistry             # Agent's available tools
    context: ConversationContext     # Messages, memories, metadata

    async def process(self, message: IncomingMessage) -> AsyncIterator[ResponseChunk]:
        """Main processing loop: context build → LLM → tool execution → response"""

    async def delegate(self, sub_agent_id: str, task: str) -> SubAgentResult:
        """Spawn a sub-agent for task delegation"""
```

**Key difference from current architecture**: The runtime is instantiated per-conversation, not a singleton. Agent definitions are data, not code. You can create a new agent by inserting a row, not by writing a new Python class.

### 2.3 Sub-Agent Orchestration

Sub-agents are regular agents invoked programmatically by a parent agent:

```python
class SubAgentOrchestrator:
    async def run(self, agent_id: str, task: str, context: dict) -> SubAgentResult:
        """
        1. Load sub-agent definition
        2. Create ephemeral runtime (no persistent session)
        3. Execute task with parent context
        4. Return result to parent
        """
```

Sub-agents:
- Have their own tool access and LLM config
- Receive scoped context from the parent (not full conversation history)
- Results are returned to the parent agent, not directly to the user
- Can be chained (sub-agent spawns sub-sub-agent) with depth limits

### 2.4 Agent Selection & Routing

When a message arrives, the router determines which agent handles it:

```
1. Explicit mention: "@Rex review this code" → route to Rex
2. Channel binding: #code-review channel → always Rex
3. DM default: User's default agent (usually Clara)
4. Tenant default: Tenant-configured default agent
5. Conversation continuity: Continue with whichever agent last responded
```

Multiple agents can participate in the same conversation (group agent chat) if the tenant enables it.

---

## 3. Multi-Tenancy

### 3.1 Tenant Model

```python
@dataclass
class Tenant:
    id: str                          # UUID
    slug: str                        # URL-friendly name
    name: str                        # Display name
    owner_id: str                    # Primary admin user
    plan: PlanTier                   # FREE, PRO, ENTERPRISE
    settings: TenantSettings         # Feature flags, limits
    created_at: datetime
```

### 3.2 Isolation

| Resource | Isolation Method |
|----------|-----------------|
| Database rows | `tenant_id` column on all tables, enforced by query scoping |
| Memories (Rook) | `tenant_id` in metadata filter on vector queries |
| Sessions | Scoped by tenant + user + agent |
| Agent definitions | Per-tenant, with system-provided defaults |
| Tools/MCP | Per-tenant tool allowlists |
| Files/sandbox | Per-tenant container isolation |

**Not** separate databases per tenant (complexity not worth it at this stage). Row-level isolation with strict query scoping. Can revisit for enterprise tier later.

### 3.3 User Model

```python
@dataclass
class User:
    id: str                          # UUID
    tenant_id: str                   # Primary tenant
    external_ids: dict[str, str]     # {"discord": "123", "slack": "U456", ...}
    display_name: str
    role: TenantRole                 # OWNER, ADMIN, MEMBER, GUEST
    preferences: UserPreferences     # Default agent, notification settings, etc.
```

Users can belong to multiple tenants. External IDs map platform identities to a single MyPal user.

---

## 4. Memory System (Rook v2)

### 4.1 Scoping

Current Rook has `user_id` and `agent_id` scoping. Rook v2 adds:

```
Memory Scopes:
├── tenant          # Shared across all agents and users in a tenant
├── agent           # Per-agent knowledge (persona-specific memories)
├── user            # Per-user facts/preferences (shared across agents)
├── user+agent      # Per-user-per-agent relationship memories
├── session         # Ephemeral conversation context
└── cross-tenant    # System-level shared knowledge (optional, admin-only)
```

### 4.2 Memory Retrieval

When building context for an agent processing a message:

```python
async def retrieve_context(agent: AgentDefinition, user: User, session: Session) -> Context:
    memories = await rook.retrieve(
        query=recent_messages_text,
        scopes=[
            MemoryScope.USER_AGENT(user.id, agent.id),   # "Clara remembers user likes Python"
            MemoryScope.USER(user.id),                     # "User's birthday is March 5th"
            MemoryScope.AGENT(agent.id),                   # "Clara's knowledge base"
            MemoryScope.TENANT(user.tenant_id),            # "Company coding standards"
        ],
        limits=agent.memory_config.retrieval_limits,
    )
    return Context(
        system_prompt=agent.persona.build_prompt(),
        memories=memories,
        history=session.recent_messages(count=30),
        previous_summary=session.previous_summary,
    )
```

### 4.3 Memory Sharing Between Agents

Agents within the same tenant can share memories through explicit cross-scope queries:

```python
# Clara asks Rex's memory for code context
code_context = await rook.retrieve(
    query="user's project architecture",
    scopes=[MemoryScope.AGENT("rex")],
    requesting_agent="clara",
    permission_check=True,
)
```

Permission model: agents can read other agents' memories by default within a tenant, but tenants can restrict this.

### 4.4 FSRS Dynamics

Keep the FSRS-6 memory dynamics system. Extend it:
- Per-scope decay rates (agent memories decay slower than session context)
- Cross-agent access boosts stability (if multiple agents reference a memory, it's more important)
- Tenant-level memories have slowest decay

---

## 5. Input Layer

### 5.1 Unified Message Format

All inputs normalize to:

```python
@dataclass
class IncomingMessage:
    id: str                          # Unique message ID
    tenant_id: str
    user_id: str
    agent_id: str | None             # Target agent (None = router decides)
    channel_id: str                  # Source channel/conversation
    platform: str                    # "discord", "api", "webhook", etc.

    # Content (multi-modal)
    text: str | None
    attachments: list[Attachment]    # Images, files, audio, video
    voice_audio: bytes | None        # Raw audio for voice-native input
    metadata: dict                   # Platform-specific extras

    # Context
    reply_to: str | None             # Thread/reply reference
    conversation_id: str | None      # Group conversation ID
    timestamp: datetime
```

### 5.2 Platform Adapters (Chat)

Keep the current adapter pattern. Each adapter:
1. Connects to the transport layer (WebSocket or direct)
2. Normalizes platform messages to `IncomingMessage`
3. Handles platform-specific output (streaming, edits, reactions, threads)

Adapters remain stateless message translators. All logic lives in the agent runtime.

### 5.3 API Gateway (New)

FastAPI-based HTTP + WebSocket API replacing both the current gateway HTTP API and Rails:

```
POST   /api/v1/chat                    # Send message, get response
WS     /api/v1/chat/stream             # Streaming chat via WebSocket
POST   /api/v1/agents                  # Create/configure agents
GET    /api/v1/agents/{id}/memory      # Query agent memory
POST   /api/v1/webhooks                # Register webhook triggers
POST   /api/v1/tasks                   # Schedule a task
GET    /api/v1/tenants/{id}/users      # Tenant user management
```

The API is a first-class input, not a proxy. External systems can interact with any agent directly.

### 5.4 Event Sources (New)

Beyond chat, agents can be triggered by:

```python
class EventSource(ABC):
    async def listen(self) -> AsyncIterator[Event]: ...

class WebhookEventSource(EventSource):     # Incoming webhooks (GitHub, CI, etc.)
class ScheduledEventSource(EventSource):   # Cron-like scheduled triggers
class EmailEventSource(EventSource):       # Email monitoring (evolve current system)
class FileWatchEventSource(EventSource):   # File system changes
class DatabaseEventSource(EventSource):    # Database change notifications
```

Events are normalized to `IncomingMessage` with `platform="event"` and routed through the same agent pipeline.

### 5.5 Modality Processing

New modality processors handle non-text inputs before they reach the agent:

```python
class ModalityProcessor(ABC):
    async def process(self, attachment: Attachment) -> ProcessedInput: ...

class VoiceProcessor(ModalityProcessor):   # STT → text + audio features
class VisionProcessor(ModalityProcessor):  # Image analysis, OCR, description
class DocumentProcessor(ModalityProcessor) # PDF/doc parsing, summarization
class VideoProcessor(ModalityProcessor):   # Frame extraction, transcription
```

These run in the input pipeline before the agent sees the message, enriching `IncomingMessage` with processed content.

---

## 6. Tech Stack (Consolidated Python)

### 6.1 Backend

| Component | Technology | Replaces |
|-----------|-----------|----------|
| HTTP API | **FastAPI** | Rails API, current gateway HTTP API |
| WebSocket | **FastAPI WebSocket** + `websockets` | Current gateway WebSocket server |
| Task queue | **Celery** or **arq** (Redis-backed) | In-process schedulers |
| Database ORM | **SQLAlchemy 2.0** (async) | Current SQLAlchemy (sync) |
| Migrations | **Alembic** | Current Alembic (keep) |
| Auth | **FastAPI Security** + JWT | Rails auth |
| Background jobs | **arq** or **Celery** | Current `asyncio.create_task` patterns |
| Caching | **Redis** | In-memory caches |

### 6.2 Frontend

| Component | Technology | Notes |
|-----------|-----------|-------|
| SPA | **React + TypeScript** | Keep, evolve |
| Build | **Vite** | Keep |
| Styling | **TailwindCSS** | Keep |
| State | **Zustand** or existing stores | Evaluate |
| Real-time | **WebSocket** (native, no ActionCable) | Simplify from Rails ActionCable |

### 6.3 Data

| Store | Purpose |
|-------|---------|
| **PostgreSQL** | Primary relational data (tenants, users, agents, sessions, messages) |
| **pgvector** | Vector embeddings for Rook memory |
| **Redis** | Caching, pub/sub, task queue backend, rate limiting |
| **FalkorDB** | Graph memory (optional, for relationship tracking) |

### 6.4 Game Logic Migration

The Rails game logic (Checkers, Blackjack) moves to Python:
- Games become agent tools or a lightweight game service module
- Game state stored in PostgreSQL (same DB)
- Real-time updates via WebSocket (already available in FastAPI)

---

## 7. Session & Conversation Model

### 7.1 Revised Session Scoping

```python
@dataclass
class Session:
    id: str
    tenant_id: str
    user_id: str
    agent_id: str                    # NEW: which agent this session is with
    channel_id: str
    conversation_id: str | None      # Group conversation (multiple users)
    started_at: datetime
    last_activity_at: datetime
    summary: str | None
    previous_session_id: str | None
```

Key change: `agent_id` is now part of the session key. User talking to Clara and user talking to Rex are separate sessions with separate histories.

### 7.2 Group Conversations

For multi-user conversations (Discord channels, group chats):

```python
@dataclass
class Conversation:
    id: str
    tenant_id: str
    channel_id: str
    participants: list[str]          # User IDs
    agents: list[str]                # Active agent IDs in this conversation
    created_at: datetime
```

A `Conversation` contains multiple users and potentially multiple agents. Each agent maintains its own `Session` within the conversation for memory continuity, but sees the shared message history.

---

## 8. Permissions & Access Control

### 8.1 RBAC Model

```
Tenant
├── Owner        # Full control, billing, delete tenant
├── Admin        # Manage agents, users, settings
├── Member       # Use agents, manage own sessions
└── Guest        # Limited agent access, read-only shared memories

Agent Permissions (per-tenant)
├── Can use tool X
├── Can access memory scope Y
├── Can spawn sub-agent Z
├── Can proactively message
└── Rate limits (messages/hour, tokens/day)
```

### 8.2 API Authentication

- JWT tokens for API access
- API keys for webhook/service integration
- Platform OAuth for adapter connections (Discord bot token, etc.)
- Tenant-scoped API keys (all requests scoped to tenant)

---

## 9. Migration Strategy

### Phase 1: Foundation (Weeks 1-4)
- [ ] Set up new project structure (`mypal/`)
- [ ] Core models: Tenant, User, AgentDefinition, Session
- [ ] FastAPI skeleton with auth (JWT)
- [ ] Port LLM provider system (minimal changes)
- [ ] Port Rook memory with tenant/agent scoping
- [ ] Basic agent runtime (single agent, text only)
- [ ] PostgreSQL + Alembic setup

### Phase 2: Multi-Agent (Weeks 5-8)
- [ ] Agent registry and definition management API
- [ ] Agent router/dispatcher
- [ ] Sub-agent orchestration
- [ ] Multi-agent conversations
- [ ] Per-agent tool configuration
- [ ] Port MCP system with agent scoping

### Phase 3: Platform Adapters (Weeks 9-12)
- [ ] Port Discord adapter to new transport layer
- [ ] Port other adapters (Slack, Teams, Telegram, Matrix)
- [ ] Unified streaming protocol
- [ ] Port sandbox system
- [ ] CLI adapter

### Phase 4: Multi-Input (Weeks 13-16)
- [ ] API gateway (REST + WebSocket for external clients)
- [ ] Webhook event source
- [ ] Scheduled task event source
- [ ] Voice processing pipeline
- [ ] Vision/document processing
- [ ] Port email monitoring as event source

### Phase 5: Web UI & Polish (Weeks 17-20)
- [ ] FastAPI serves React frontend
- [ ] Port game logic to Python
- [ ] Admin UI (tenant/agent management)
- [ ] User dashboard (memory, sessions, preferences)
- [ ] Real-time WebSocket updates (replace ActionCable)

### Phase 6: Multi-Tenancy & Production (Weeks 21-24)
- [ ] Tenant management API
- [ ] RBAC enforcement
- [ ] Rate limiting and quotas
- [ ] Tenant onboarding flow
- [ ] Data export/import
- [ ] Monitoring and observability

---

## 10. Project Structure

```
mypal/
├── mypal/
│   ├── __init__.py
│   ├── main.py                      # FastAPI app entrypoint
│   ├── config.py                    # Settings (Pydantic BaseSettings)
│   │
│   ├── api/                         # FastAPI routes
│   │   ├── v1/
│   │   │   ├── chat.py              # Chat endpoints
│   │   │   ├── agents.py            # Agent CRUD
│   │   │   ├── tenants.py           # Tenant management
│   │   │   ├── users.py             # User management
│   │   │   ├── memory.py            # Memory queries
│   │   │   ├── tasks.py             # Scheduled tasks
│   │   │   ├── webhooks.py          # Webhook registration
│   │   │   └── admin.py             # Admin operations
│   │   ├── auth.py                  # JWT, API key auth
│   │   └── deps.py                  # Dependency injection
│   │
│   ├── agents/                      # Agent system
│   │   ├── definition.py            # AgentDefinition model
│   │   ├── runtime.py               # AgentRuntime (per-conversation)
│   │   ├── router.py                # Agent selection/routing
│   │   ├── orchestrator.py          # Sub-agent orchestration
│   │   └── personas/                # Built-in persona configs
│   │       └── clara.py
│   │
│   ├── transport/                   # Input/output transport
│   │   ├── websocket.py             # WebSocket server for adapters
│   │   ├── protocol.py              # Message types (evolved from current)
│   │   └── stream.py                # Response streaming
│   │
│   ├── adapters/                    # Platform adapters
│   │   ├── base.py                  # Adapter base class
│   │   ├── discord/
│   │   ├── slack/
│   │   ├── telegram/
│   │   └── cli/
│   │
│   ├── inputs/                      # Input processing
│   │   ├── message.py               # IncomingMessage model
│   │   ├── events.py                # Event source base + implementations
│   │   ├── modalities/              # Voice, vision, document processors
│   │   │   ├── voice.py
│   │   │   ├── vision.py
│   │   │   └── document.py
│   │   └── webhooks.py              # Webhook receiver
│   │
│   ├── memory/                      # Rook v2
│   │   ├── manager.py               # Memory manager (not singleton)
│   │   ├── scopes.py                # Memory scope definitions
│   │   ├── retriever.py             # Scoped retrieval
│   │   ├── writer.py                # Scoped writing
│   │   ├── dynamics.py              # FSRS scheduling
│   │   ├── ingestion.py             # Smart dedup/supersede
│   │   ├── vector/                  # pgvector backend
│   │   ├── embeddings/              # Embedding providers
│   │   └── graph/                   # FalkorDB (optional)
│   │
│   ├── llm/                         # LLM providers (ported)
│   │   ├── config.py
│   │   ├── providers/
│   │   └── tools/
│   │
│   ├── tools/                       # Tool system
│   │   ├── registry.py              # Tool registration
│   │   ├── executor.py              # Tool execution routing
│   │   ├── sandbox/                 # Docker/Incus sandbox
│   │   ├── mcp/                     # MCP client
│   │   └── builtins/                # Built-in tools
│   │
│   ├── tenants/                     # Multi-tenancy
│   │   ├── models.py                # Tenant, membership
│   │   ├── service.py               # Tenant CRUD
│   │   └── isolation.py             # Query scoping middleware
│   │
│   ├── auth/                        # Authentication
│   │   ├── jwt.py
│   │   ├── api_keys.py
│   │   └── rbac.py                  # Role-based access
│   │
│   ├── db/                          # Database
│   │   ├── models.py                # All SQLAlchemy models
│   │   ├── session.py               # Async session factory
│   │   └── migrations/              # Alembic
│   │
│   ├── services/                    # Background services
│   │   ├── email/                   # Email monitoring
│   │   ├── backup/                  # DB backups
│   │   ├── proactive/               # ORS (per-agent)
│   │   └── scheduler.py             # Task scheduling
│   │
│   └── plugins/                     # Plugin system (ported)
│       ├── loader.py
│       ├── registry.py
│       └── types.py
│
├── web/                             # React frontend
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
│
├── tests/
├── alembic.ini
├── pyproject.toml
└── docker-compose.yml
```

---

## 11. Key Design Principles

1. **Agents are data, not code.** Creating a new agent should be an API call, not a deployment.
2. **Tenant isolation by default.** Every query, every memory access, every tool invocation is tenant-scoped.
3. **Memory is the moat.** Rook v2 is the differentiator. Rich, scoped, relationship-aware memory that makes agents genuinely personal.
4. **Input-agnostic processing.** An agent shouldn't care if the message came from Discord, an API call, or a webhook. Same pipeline.
5. **Sub-agents are just agents.** No special sub-agent class. Any agent can be invoked by another agent with scoped context.
6. **Progressive complexity.** Single user, single agent, single platform should work out of the box. Multi-tenant, multi-agent, multi-input is additive configuration.

---

## 12. Open Questions

1. **Agent-to-agent communication**: Should agents in the same tenant be able to message each other directly (event bus), or only through sub-agent delegation?
2. **Memory migration**: Do we migrate existing Clara memories into the new system, or start fresh with import tooling?
3. **Billing/quotas**: If multi-tenant goes beyond personal use, how do we meter LLM usage per tenant?
4. **Real-time collaboration**: Should multiple users be able to see each other interacting with an agent live (Google Docs-style), or is it more like separate sessions in a shared space?
5. **Agent marketplace**: Should tenants be able to share/publish agent definitions for others to use?
