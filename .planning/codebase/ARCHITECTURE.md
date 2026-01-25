# Architecture

**Analysis Date:** 2026-01-24

## Pattern Overview

**Overall:** Multi-platform AI assistant with modular platform adapters, unified tool registry, and pluggable memory system.

**Key Characteristics:**
- Platform-agnostic core (`PlatformAdapter` abstraction) supporting Discord, API, and future platforms
- Singleton pattern for global state: `MemoryManager`, `ToolRegistry`, `MCPServerManager`
- LLM provider abstraction supporting multiple backends (OpenRouter, NanoGPT, Custom OpenAI, Anthropic native)
- Pluggable MCP (Model Context Protocol) system for extensible tool support
- Session-based conversation management with optional mem0 semantic memory integration
- Async-first architecture using Python's asyncio

## Layers

**Platform Layer:**
- Purpose: Abstract communication platform details (Discord, API, Slack, Telegram)
- Location: `clara_core/platform.py`, `clara_core/discord/`
- Contains: `PlatformAdapter` base class, `PlatformMessage`, `PlatformContext`, Discord-specific implementation
- Depends on: Core message types, no external platform dependencies until instantiation
- Used by: Main entry point (`discord_bot.py`), message dispatch logic

**Presentation/Discord Layer:**
- Purpose: Discord bot implementation with commands, slash commands, message handling, and UI elements
- Location: `discord_bot.py`, `clara_core/discord/`
- Contains: Discord bot event handlers, message parsing, streaming responses, embeds, slash commands
- Depends on: `MemoryManager`, `ToolRegistry`, LLM backends, platform layer
- Used by: Users via Discord, triggered by incoming messages and commands

**Memory/Persistence Layer:**
- Purpose: Session management, conversation history, and semantic memory via mem0
- Location: `clara_core/memory.py`, `db/models.py`, `config/mem0.py`
- Contains: `MemoryManager` singleton, SQLAlchemy models (Project, Session, Message, ChannelSummary), mem0 integration
- Depends on: SQLAlchemy ORM, mem0 library, LLM for extraction (via MemoryManager callback)
- Used by: All platform adapters for context retrieval and message storage

**Tool/Capability Layer:**
- Purpose: Central registry and execution of all Clara tools (code execution, file I/O, API calls, MCP tools)
- Location: `clara_core/tools.py`, `tools/`, `clara_core/core_tools/`
- Contains: `ToolRegistry` singleton, tool definitions, handlers for built-in tools
- Depends on: Sandbox system, storage system, external APIs (GitHub, Google, etc.)
- Used by: LLM backends when executing tool calls, Discord handlers for tool commands

**LLM Backend Layer:**
- Purpose: Unified abstraction over multiple LLM providers with tier-based model selection
- Location: `clara_core/llm.py`
- Contains: Provider clients (OpenAI SDK for OpenRouter/NanoGPT, Anthropic native SDK), model tiers (high/mid/low), tool format conversion
- Depends on: OpenAI and Anthropic Python SDKs, environment configuration
- Used by: `MemoryManager` (for prompt building and memory extraction), Discord handlers (for LLM chat calls), Tool system (for descriptions)

**MCP Plugin System:**
- Purpose: Dynamic loading and management of MCP servers that extend Clara's capabilities
- Location: `clara_core/mcp/`
- Contains: `MCPServerManager` singleton, MCP client/server implementations, Smithery installer, OAuth support
- Depends on: `mcp` SDK, git, external HTTP, file system
- Used by: `ToolRegistry` for tool registration, admin tools for server lifecycle management

**Sandbox/Code Execution Layer:**
- Purpose: Safe execution of user code via local Docker or remote sandbox API
- Location: `sandbox/`
- Contains: Docker manager, remote sandbox client, unified manager interface
- Depends on: Docker SDK, HTTP for remote API, environment configuration
- Used by: Tool registry when executing code_execution tool

**Storage Layer:**
- Purpose: Persistent file storage for user-uploaded and generated files
- Location: `storage/local_files.py`
- Contains: Local filesystem manager with per-user directories
- Depends on: File system, pathlib
- Used by: Tool handlers for file persistence and retrieval

**Configuration Layer:**
- Purpose: Centralized config management and initialization
- Location: `clara_core/config.py`, `config/`
- Contains: `ClaraConfig` dataclass, environment variable loading, logging setup, mem0 configuration
- Depends on: Environment variables, dotenv, Python logging
- Used by: All layers during initialization

## Data Flow

**Chat Request → Response Flow (Discord):**

1. **Message Arrives**: Discord event triggers `on_message` handler in `discord_bot.py`
2. **Platform Abstraction**: Message converted to `PlatformMessage` object (user_id, content, attachments, etc.)
3. **Context Retrieval**: `MemoryManager.get_instance()` fetches recent session messages and mem0 semantic memories
4. **Prompt Building**: `MemoryManager` builds full prompt with Clara's persona, user profile, context, and recent memories
5. **LLM Call**: `make_llm_with_tools()` (or `make_llm_with_tools_anthropic()` for Anthropic) invokes LLM with:
   - System prompt (Clara's personality + instructions)
   - Chat history
   - Available tools definitions (from `ToolRegistry`)
   - Image attachments (if present, resized to 1568px)
6. **Tool Execution Loop**:
   - If LLM requests tool call: `ToolRegistry.execute()` runs handler (async)
   - Tool result fed back to LLM
   - LLM may request more tools or provide final response
7. **Response Streaming**: Response streamed to Discord in chunks, with typing indicator
8. **Persistence**: Message stored to database via `MemoryManager.add_message()`
9. **Memory Update**: New message context may trigger mem0 memory extraction (via `MemoryManager` callback)

**State Management:**

- **Session Context**: 15 recent messages loaded in memory per session (configurable `CONTEXT_MESSAGE_COUNT`)
- **Semantic Memory**: mem0 stores key facts/preferences, searched every request via LLM-generated query
- **Session Summary**: When session times out (30 min inactivity), LLM generates summary stored for next session continuity
- **Channel Summary**: Rolling Discord channel summary (optional, older messages compressed)
- **Model Tier**: Selected via message prefix (`!high`, `!mid`, `!low`) or auto-selected based on message complexity

**Message Storage:**

```
Session (time-bounded conversation)
  ├─ Messages (chat history)
  │   ├─ user: "What is quantum computing?"
  │   └─ assistant: "Quantum computing uses quantum mechanics..."
  └─ Context snapshot (json: recent 10 messages from previous session)
```

**MCP Server Lifecycle:**

1. **Install**: `mcp_install(source)` clones/downloads MCP server, stores config
2. **Start**: `MCPServerManager` spawns process (stdio) or connects HTTP
3. **Tool Registration**: Tools from server auto-registered in `ToolRegistry` with namespace prefix (`server_name__tool_name`)
4. **Execution**: Tool calls routed through `MCPServerManager` to appropriate server
5. **Hot Reload** (optional): File changes trigger restart automatically

## Key Abstractions

**MemoryManager:**
- Purpose: Orchestrates all memory operations - session retrieval, mem0 integration, prompt building
- Examples: `clara_core/memory.py`
- Pattern: Singleton with LLM callback for extraction. Provides `get_instance()`, `add_message()`, `fetch_memory_context()`, `get_session()`

**ToolRegistry:**
- Purpose: Centralized tool definitions and async execution with platform filtering
- Examples: `clara_core/tools.py`
- Pattern: Singleton with registration system. Tools define schemas, handlers are async callables. Built-in tools registered at init, MCP tools registered dynamically

**PlatformAdapter:**
- Purpose: Platform-specific implementation with unified interface
- Examples: `clara_core/platform.py` (base), Discord handler in `discord_bot.py` (send_message, send_typing_indicator)
- Pattern: Abstract base class with subclass per platform. Handles message formatting and platform-specific operations

**LLM Backend:**
- Purpose: Provider abstraction with model tier selection and tool format conversion
- Examples: `clara_core/llm.py`
- Pattern: Factory functions (`make_llm()`, `make_llm_with_tools()`) return configured client. Tier system maps (high/mid/low) to provider-specific models

**MCPServerManager:**
- Purpose: Lifecycle management of local and remote MCP servers
- Examples: `clara_core/mcp/manager.py`
- Pattern: Singleton managing process/HTTP connections. Local servers use stdio transport (watchdog for hot reload), remote use HTTP

## Entry Points

**Discord Bot:**
- Location: `discord_bot.py::main()` → `async_main()` → `run_bot()`
- Triggers: Direct invocation (`poetry run python discord_bot.py`)
- Responsibilities: Initialize platform, load config/env, setup Discord client, spawn bot and monitor server tasks, handle graceful shutdown

**Monitor Dashboard (Web):**
- Location: `discord_bot.py::run_monitor_server()`
- Triggers: When `DISCORD_MONITOR_ENABLED=true`, runs alongside bot on port 8001
- Responsibilities: FastAPI server providing bot status, activity logs, message history to web UI

**Email Monitor:**
- Location: `email_monitor.py::email_check_loop()`
- Triggers: Spawned as background task from Discord bot if `EMAIL_MONITORING_ENABLED=true`
- Responsibilities: Periodic IMAP polling, rule evaluation, Discord alert dispatching

**Organic Response System (ORS):**
- Location: `organic_response_system.py::ors_check_loop()`
- Triggers: Optional background loop if `ORS_ENABLED=true`
- Responsibilities: Assess user context, decide when to initiate proactive messages, schedule follow-ups

## Error Handling

**Strategy:** Exception-based with graceful degradation. Errors logged at multiple levels, users informed via Discord when tools fail.

**Patterns:**
- **Tool Failures**: Caught in tool execution, returned as tool result with error message shown to user
- **LLM Call Failures**: Logged, user receives error message in Discord, retry logic in some cases
- **Memory Failures**: Non-fatal - missing memories logged, bot continues with degraded context
- **Database Failures**: Logged with traceback, attempts reconnect on next operation
- **Sandbox Failures**: Falls back to local Docker if remote unavailable, disables code execution if Docker unavailable

## Cross-Cutting Concerns

**Logging:** Hierarchical logger system (`config/logging.py`) with named loggers per module. Can mirror to Discord channel via `DISCORD_LOG_CHANNEL_ID`. Database-backed for persistent audit trail via `LogEntry` model.

**Validation:**
- Configuration validation via `ClaraConfig` dataclass (Pydantic v2)
- Message size limits enforced: `DISCORD_MAX_CHARS`, `DISCORD_MAX_TOOL_RESULT_CHARS`
- File size limits for uploads: `CLARA_MAX_FILE_SIZE`
- Image dimension limits: `DISCORD_MAX_IMAGE_DIMENSION`

**Authentication:**
- Discord: Bot token in environment, per-channel/role access control via `ChannelConfig`
- MCP OAuth: Handled by `clara_core/mcp/oauth.py` for hosted Smithery servers
- External APIs: Per-API env vars (GitHub, Google, OpenRouter, etc.)

**Rate Limiting:**
- Message queuing in channels: Active mode batching for high-volume channels, position notifications for mentions/DMs
- MCP tool calls: Per-server rate limits (implementation in individual servers)
- Sandbox execution: Container idle timeout and memory/CPU limits

---

*Architecture analysis: 2026-01-24*
