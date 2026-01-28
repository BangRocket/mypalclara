# Architecture

**Analysis Date:** 2026-01-27

## Pattern Overview

**Overall:** Layered hexagonal (ports and adapters) architecture with a central Clara Core providing unified platform abstractions. Multiple entry points (Discord bot, CLI, Email monitor, Gateway server) delegate to core services.

**Key Characteristics:**
- Platform-agnostic core (`clara_core`) with implementations for Discord, CLI, web, and gateway adapters
- Strangler fig pattern used in Discord adapter (wraps existing bot while providing new PlatformAdapter interface)
- Singleton pattern for key managers (MemoryManager, ToolRegistry, MCPServerManager)
- Event-driven hooks system in the gateway for extensibility
- Layered data access: Session/Message storage → mem0 semantic memory → graph memory (optional)

## Layers

**Platform Adapters Layer:**
- Purpose: Receive messages from external platforms, convert to platform-agnostic format, route to processing
- Location: `adapters/discord/`, `adapters/cli/`, `adapters/web/`
- Contains: Platform-specific implementation code (Discord event handlers, CLI interface, web routes)
- Depends on: `clara_core.platform`, `gateway` (WebSocket communication)
- Used by: External platforms (Discord servers, terminal, web clients)

**Gateway Layer (Message Router & Processor):**
- Purpose: Central hub for message routing and processing orchestration
- Location: `gateway/`
- Contains: WebSocket server (`server.py`), message processor (`processor.py`), LLM orchestrator (`llm_orchestrator.py`), tool executor (`tool_executor.py`), session/node management, event hooks, task scheduler
- Depends on: `clara_core` (MemoryManager, LLM, tools), database models
- Used by: Platform adapters via WebSocket connections

**Clara Core Layer (Business Logic):**
- Purpose: Platform-independent business logic for memory, LLM, tools, configuration
- Location: `clara_core/`
- Contains: MemoryManager, LLM backends, ToolRegistry, MCP integration, platform abstractions
- Depends on: `config/`, `db/`, `storage/`, `sandbox/`, vendor libraries
- Used by: Gateway processor, Discord bot, CLI bot, email monitor, scripts

**Data Access Layer:**
- Purpose: Persistence and memory retrieval
- Location: `db/` (session/message models), `config/mem0.py` (mem0 configuration), `storage/local_files.py` (file storage)
- Contains: SQLAlchemy models (Project, Session, Message, ChannelSummary, ChannelConfig), mem0 integration, local/S3 file storage
- Depends on: SQLAlchemy ORM, mem0 (vendored), boto3 for S3
- Used by: MemoryManager, Gateway processor, Discord bot

**Infrastructure Layer:**
- Purpose: Code execution, external service integration, system utilities
- Location: `sandbox/`, `email_service/`, `clara_core/mcp/`, scripts
- Contains: Docker/Incus sandbox managers, email monitoring, MCP server management
- Depends on: Docker SDK, email libraries, MCP SDK
- Used by: Tool execution, background services

## Data Flow

**Discord Message to Response:**

1. Discord user sends message → `discord_bot.py` event handler
2. Handler builds context (session history, mem0 memories, emotional state)
3. MemoryManager.get_context() fetches last 15 messages + key memories
4. LLM backend (`make_llm_with_tools()`) generates response with tool support
5. Tool execution via UnifiedSandboxManager or ToolRegistry
6. Response streamed back to Discord channel
7. Message stored in database, emotional state tracked

**Gateway Message to Response (Adapter-based):**

1. Platform adapter connects to gateway via WebSocket → GatewayServer registers node
2. Adapter sends MessageRequest with user_id, context, message content
3. GatewayServer routes to MessageProcessor
4. MessageProcessor initializes with MemoryManager, ToolExecutor, LLMOrchestrator
5. Builds prompt with session context + mem0 memories
6. LLMOrchestrator calls LLM with tools available
7. ToolExecutor runs tools (detection via response parsing)
8. Response streamed back in chunks to adapter via WebSocket
9. Adapter displays in platform UI

**State Management:**
- Session state: Stored in database with message history, summaries on timeout (30 min idle)
- Memory state: User facts/preferences in mem0 (vector store), filtered by project_id
- Emotional continuity: Tracked via sentiment analysis, stored in mem0
- Tool state: Maintained per-request (no cross-request state)
- Graph memories: Optional Neo4j or embedded Kuzu for relationship tracking

## Key Abstractions

**MemoryManager (singleton):**
- Purpose: Orchestrates all memory retrieval and session handling
- Location: `clara_core/memory.py`
- Pattern: Singleton with lazy initialization
- Responsibilities: Fetch session history, search mem0, build context prompts, manage session lifecycle, track emotional state
- Core methods:
  - `get_context()` - Returns full prompt context for LLM
  - `add_message()` - Stores user/assistant message to session and mem0
  - `get_session()` - Retrieves or creates session for user/context
  - `_fetch_mem0_context()` - Semantic search with BM25 ranking

**ToolRegistry (singleton):**
- Purpose: Central registration and execution of all tools
- Location: `clara_core/tools.py`
- Pattern: Singleton with platform filtering
- Responsibilities: Register tools, provide OpenAI-formatted definitions, execute tools with handlers
- Core methods:
  - `register()` - Add new tool with handler
  - `get_tools()` - Get tools filtered by platform
  - `execute()` - Run tool handler and return result

**LLM Backends:**
- Purpose: Unified interface to multiple LLM providers
- Location: `clara_core/llm.py`
- Providers supported: OpenRouter, NanoGPT, Custom OpenAI, Anthropic (native SDK)
- Key functions:
  - `make_llm()` - Non-streaming completions
  - `make_llm_streaming()` - Streaming completions
  - `make_llm_with_tools()` - Tool calling (OpenAI format)
  - `make_llm_with_tools_anthropic()` - Native Anthropic tool calling
- Model tiers: "high" (Opus), "mid" (Sonnet, default), "low" (Haiku) with environment variable overrides per tier

**MCPServerManager (singleton):**
- Purpose: Install and manage external MCP (Model Context Protocol) servers
- Location: `clara_core/mcp/manager.py`
- Pattern: Singleton managing local and remote servers
- Responsibilities: Install from Smithery/npm/GitHub, manage server connections, bridge tools to ToolRegistry
- Supported sources: Smithery, npm packages, GitHub repos, Docker images, local paths

**PlatformAdapter (abstract base):**
- Purpose: Interface for platform-specific adapters to implement
- Location: `clara_core/platform.py`
- Methods: Convert platform messages to PlatformMessage, provide context, handle responses
- Implementations: `adapters/discord/adapter.py` (Strangler fig wrapping), `adapters/cli/adapter.py`, future: `adapters/slack/adapter.py`

**GatewayServer (singleton):**
- Purpose: WebSocket server for platform adapters
- Location: `gateway/server.py`
- Responsibilities: Accept adapter connections, route messages, stream responses, maintain heartbeats
- Related classes:
  - `MessageRouter` - Routes messages to processor
  - `SessionManager` - Tracks adapter sessions
  - `NodeRegistry` - Tracks connected nodes/adapters

**SandboxManager (unified interface):**
- Purpose: Abstracts code execution backends
- Location: `sandbox/manager.py`
- Implementations: Docker, Incus (containers), Incus (VMs), Remote API
- Auto-selection: Remote if configured, else Incus/Docker based on availability

## Entry Points

**Discord Bot:**
- Location: `discord_bot.py` main, `adapters/discord/main.py` adapter
- Triggers: `poetry run python discord_bot.py`
- Responsibilities:
  - Initialize Discord.py client
  - Handle Discord events (on_message, on_ready, etc.)
  - Manage message queuing and batching (active mode)
  - Build session/memory context
  - Stream LLM responses with tool execution
  - Support model tier selection (!high, !mid, !low prefixes)

**CLI Bot:**
- Location: `cli_bot.py`
- Triggers: `poetry run python cli_bot.py`
- Responsibilities: Interactive terminal interface, local file tools, session management

**Email Monitor:**
- Location: `email_monitor.py`, `email_service/`
- Triggers: Background service
- Responsibilities: Poll email accounts (Gmail OAuth or IMAP), apply rules, send Discord alerts

**Gateway Server:**
- Location: `gateway/main.py`, `gateway/__main__.py`
- Triggers: `poetry run python -m gateway`
- Responsibilities:
  - Accept adapter WebSocket connections
  - Route messages to processor
  - Stream responses back
  - Manage hooks and scheduled tasks
  - Event emission for extensibility

**API Service:**
- Location: `api_service/main.py` (separate repo/service)
- Triggers: Standalone FastAPI service
- Responsibilities: OAuth callbacks (Google), health checks, admin endpoints

## Error Handling

**Strategy:** Layered approach with fallbacks and graceful degradation

**Patterns:**
- Database errors: Migrations auto-fallback from Alembic to create_all()
- LLM errors: Retry logic, tier downgrade on rate limits
- Memory lookup: Graceful degradation if mem0 unavailable (session history only)
- Tool execution: Errors caught and formatted, response continues with error context
- Sandbox: Auto-select fallback (Docker → Incus → Remote)
- Email: Individual rule failures don't stop entire monitoring loop

## Cross-Cutting Concerns

**Logging:** Configured in `config/logging.py` with module-specific loggers. Discord log mirroring to channel optional. Multi-file output support.

**Validation:** Pydantic models in config, environment variable validation at startup, database schema validation via SQLAlchemy.

**Authentication:**
- Discord: Token-based (DISCORD_BOT_TOKEN)
- Google OAuth: Per-user connections stored in database with encrypted tokens
- Gateway: Optional shared secret (CLARA_GATEWAY_SECRET)
- LLM providers: API key-based or token-based per provider

**Concurrency:**
- Discord: Built on discord.py async/await
- Gateway: asyncio-based WebSocket with concurrent message processing
- Database: Connection pooling (QueuePool for PostgreSQL, SQLite automatic)
- Thread pools: BLOCKING_EXECUTOR in gateway for I/O operations

---

*Architecture analysis: 2026-01-27*
