# Codebase Structure

**Analysis Date:** 2026-01-24

## Directory Layout

```
mypalclara/
├── clara_core/                 # Core Clara platform (shared by all services)
│   ├── __init__.py             # Platform initialization, singleton exports
│   ├── config.py               # ClaraConfig dataclass, env variable loading
│   ├── llm.py                  # LLM provider abstraction (OpenRouter, NanoGPT, OpenAI, Anthropic)
│   ├── memory.py               # MemoryManager singleton, session/mem0 integration
│   ├── tools.py                # ToolRegistry singleton, tool definitions and execution
│   ├── platform.py             # PlatformAdapter abstraction, PlatformMessage/Context
│   ├── emotional_context.py    # Sentiment tracking for conversation continuity
│   ├── topic_recurrence.py     # Topic extraction and tracking patterns
│   ├── sentiment.py            # Sentiment analysis utilities
│   ├── discord/                # Discord-specific implementation
│   │   ├── __init__.py         # Slash command registration (setup_slash_commands)
│   │   ├── commands.py         # Discord slash command handlers
│   │   ├── views.py            # Discord UI components (buttons, select menus)
│   │   └── embeds.py           # Discord embed formatting
│   ├── mcp/                    # Model Context Protocol plugin system
│   │   ├── __init__.py         # MCPServerManager singleton, init/shutdown
│   │   ├── manager.py          # Server lifecycle management
│   │   ├── client.py           # MCP client wrapper (stdio & HTTP transports)
│   │   ├── local_server.py     # Local MCP server subprocess management with hot reload
│   │   ├── remote_server.py    # Remote MCP server HTTP client
│   │   ├── models.py           # MCPServer SQLAlchemy model, config storage
│   │   ├── installer.py        # Installation from Smithery, npm, GitHub, Docker, local paths
│   │   ├── registry_adapter.py # Bridge between MCP tools and ToolRegistry
│   │   └── oauth.py            # OAuth flow for hosted Smithery servers
│   ├── core_tools/             # Built-in Clara tools (always available)
│   │   ├── __init__.py
│   │   ├── mcp_management.py   # mcp_install, mcp_list, mcp_status, etc.
│   │   ├── chat_history.py     # Session and message retrieval tools
│   │   └── system_logs.py      # System information and log viewing
│   └── services/               # Platform-independent services
│       ├── __init__.py
│       └── backup.py           # Database backup utilities
├── discord_bot.py              # Main Discord bot entry point with async runtime
├── email_monitor.py            # Email monitoring service for IMAP accounts
├── organic_response_system.py  # Proactive conversation system (optional)
├── proactive_engine.py         # Legacy proactive messaging (superseded by ORS)
├── db/                         # Database models and configuration
│   ├── __init__.py
│   ├── connection.py           # SQLAlchemy engine setup (SQLite/PostgreSQL)
│   ├── models.py               # SQLAlchemy models: Project, Session, Message, ChannelSummary, ChannelConfig, LogEntry, etc.
│   └── channel_config.py       # Channel-specific behavior config (active/mention/off mode)
├── config/                     # Application configuration
│   ├── __init__.py
│   ├── bot.py                  # Bot-specific configuration constants
│   ├── logging.py              # Logging setup with file/console/database/Discord handlers
│   └── mem0.py                 # mem0 client initialization with Qdrant/pgvector/Neo4j
├── tools/                      # Tool registration and loading system
│   ├── __init__.py             # Tool module initialization
│   ├── _base.py                # ToolDef and ToolContext base classes
│   ├── _loader.py              # Dynamic tool module discovery and loading
│   └── _registry.py            # Tool registration to ToolRegistry
├── sandbox/                    # Code execution sandbox system
│   ├── __init__.py
│   ├── manager.py              # SandboxManager (auto-selects local or remote)
│   ├── docker.py               # Local Docker sandbox with container pooling
│   └── remote_client.py        # Remote sandbox HTTP client
├── storage/                    # File storage system
│   ├── __init__.py
│   └── local_files.py          # Local filesystem storage with per-user directories
├── email_service/              # Email monitoring implementation
│   ├── __init__.py
│   ├── monitor.py              # Email polling and rule evaluation
│   ├── credentials.py          # OAuth and IMAP credential storage
│   ├── rules_engine.py         # Email rule matching and priority scoring
│   ├── presets.py              # Pre-built rule presets (job_hunting, urgent, etc.)
│   └── providers/              # Email provider implementations
├── release_dashboard/          # Release management dashboard
│   ├── main.py                 # FastAPI app for staging → main promotion
│   └── ...
├── sandbox_service/            # Self-hosted remote sandbox service
│   ├── main.py                 # FastAPI sandbox API server
│   └── ...
├── backup_service/             # Database backup service to S3-compatible storage
│   ├── backup.py               # Backup/restore logic
│   └── ...
├── scripts/                    # Utility scripts
│   ├── bump_version.py         # CalVer version management
│   ├── bootstrap_memory.py     # Load initial user profile to mem0
│   ├── migrate_to_postgres.py  # Data migration from SQLite to PostgreSQL
│   ├── restart_bot.py          # Graceful bot restart with optional delay
│   └── ...
├── vendor/                     # Vendored dependencies
│   └── mem0/                   # mem0 library (patched for anthropic_base_url support)
├── personalities/              # Clara personality profiles and traits
├── .planning/                  # GSD codebase documentation
│   └── codebase/               # This directory: ARCHITECTURE.md, STRUCTURE.md, etc.
├── tests/                      # Unit and integration tests (minimal coverage)
├── .githooks/                  # Git hooks for automatic version bumping
├── inputs/                     # User input files (e.g., user_profile.txt for bootstrap)
├── generated/                  # Generated files (profile_bio.json, etc.)
├── clara_files/                # Local user file storage (per-user directories)
├── pyproject.toml              # Poetry dependencies and project config
├── VERSION                     # Current version (CalVer: YYYY.WW.N)
├── CLAUDE.md                   # Project instructions for Claude Code
├── README.md                   # Project overview
└── docker-compose.yml          # Docker Compose config for local development
```

## Directory Purposes

**clara_core/**
- Purpose: Shared core platform infrastructure used by all services
- Contains: Platform abstraction, singleton managers, LLM backend, memory system, tool registry, MCP system
- Key files: `__init__.py` (exports singletons), `memory.py` (MemoryManager), `tools.py` (ToolRegistry), `llm.py` (provider abstraction)

**discord_bot.py**
- Purpose: Main Discord bot with message handling, tool integration, streaming responses
- Contains: 4000+ lines of event handlers, command definitions, response streaming logic, sandbox integration
- Key concepts: Message queuing/batching for high-volume channels, image resizing for vision, graceful shutdown

**db/**
- Purpose: SQLAlchemy models and database connection
- Contains: ORM models (Project, Session, Message, ChannelSummary, ChannelConfig) and connection setup
- Key files: `models.py` (all models), `connection.py` (engine setup), `channel_config.py` (Discord channel behavior)

**config/**
- Purpose: Application configuration and initialization
- Contains: Environment variable loading, logging setup, mem0 client initialization
- Key files: `logging.py` (hierarchical loggers), `mem0.py` (mem0 client), `bot.py` (bot constants)

**tools/**
- Purpose: Tool registration and dynamic loading system
- Contains: Tool definition schema, dynamic loader, registry integration
- Key files: `_base.py` (ToolDef/ToolContext), `_loader.py` (module discovery), `_registry.py` (registration)

**sandbox/**
- Purpose: Code execution environment (local Docker or remote API)
- Contains: Docker manager, remote client, unified manager interface
- Key files: `docker.py` (local Docker implementation), `remote_client.py` (HTTP client)

**storage/local_files.py**
- Purpose: Persistent local file storage with per-user organization
- Contains: File upload/download, directory management, size limits
- Key features: Discord attachment auto-saving, file listing and deletion

**email_service/**
- Purpose: Email monitoring with rule-based alerting
- Contains: IMAP monitor, OAuth/password-based credentials, rule engine, presets
- Key files: `monitor.py` (polling loop), `rules_engine.py` (rule matching), `presets.py` (built-in rules)

**scripts/**
- Purpose: Utility scripts for development and operations
- Contains: Version management, database migration, memory bootstrapping, bot restart
- Key files: `bump_version.py` (CalVer auto-bump), `bootstrap_memory.py` (user profile import)

**vendor/mem0/**
- Purpose: Vendored mem0 library with patches
- Contains: Memory system implementation (unmodified from upstream except for bug fixes)
- Note: Patched to support Anthropic's `anthropic_base_url` parameter

## Key File Locations

**Entry Points:**
- `discord_bot.py`: Discord bot main entry (`main()` → `async_main()` → `run_bot()`)
- `email_monitor.py`: Email service entry point
- `organic_response_system.py`: ORS loop entry point
- `release_dashboard/main.py`: Release management dashboard entry
- `sandbox_service/main.py`: Remote sandbox API entry

**Configuration:**
- `VERSION`: Current version in CalVer format (YYYY.WW.N)
- `pyproject.toml`: Poetry dependencies and project metadata
- `.env` (git-ignored): Environment variables for local development
- `clara_core/config.py`: Runtime config loading from environment

**Core Logic:**
- `clara_core/memory.py`: Session/mem0 integration, context retrieval, prompt building
- `clara_core/llm.py`: LLM provider abstraction, tier system, tool format conversion
- `clara_core/tools.py`: Tool registry, definitions, async execution
- `clara_core/mcp/manager.py`: MCP server lifecycle

**Models:**
- `db/models.py`: SQLAlchemy models - Project, Session, Message, ChannelSummary, ChannelConfig, LogEntry, EmailAccount, EmailRule, MCPServer, etc.

**Testing:**
- `tests/`: Currently minimal; pytest runner configured in pyproject.toml
- No test files committed yet (tests directory empty)

## Naming Conventions

**Files:**
- Python modules: `snake_case.py` (e.g., `memory.py`, `llm.py`, `email_monitor.py`)
- Private/internal modules: Prefix with `_` (e.g., `_base.py`, `_loader.py`)
- Main entry points: `{service}.py` or `main.py` (e.g., `discord_bot.py`, `email_monitor.py`)

**Directories:**
- Core packages: `snake_case/` (e.g., `clara_core/`, `email_service/`, `sandbox/`)
- Feature packages: `snake_case/` with submodules (e.g., `clara_core/mcp/`, `clara_core/discord/`)
- External packages: `snake_case/` (e.g., `storage/`, `tools/`)
- Generated: `generated/`, `clara_files/` (output directories)

**Functions:**
- Sync functions: `snake_case()` (e.g., `get_version()`, `init_platform()`)
- Async functions: `async snake_case()` (e.g., `async_main()`, `send_message()`)
- Internal/private: Prefix with `_` (e.g., `_fetch_mem0_context()`, `_format_message()`)
- Class methods: `snake_case()` (e.g., `get_instance()`, `initialize()`)

**Variables:**
- Constants: `UPPER_CASE` (e.g., `CONTEXT_MESSAGE_COUNT`, `BOT_TOKEN`)
- Module-level config: `UPPER_CASE` (e.g., `DEFAULT_TIER`, `TOOL_FORMAT`)
- Regular variables: `snake_case` (e.g., `session_id`, `memory_context`)

**Types:**
- Classes: `PascalCase` (e.g., `MemoryManager`, `ToolRegistry`, `PlatformAdapter`)
- Type aliases: `PascalCase` or `snake_case` depending on convention (e.g., `ModelTier`, `MessageRole`)

## Where to Add New Code

**New Tool:**
1. Create tool handler in `tools/{tool_category}.py` or `clara_core/core_tools/{name}.py`
2. Define `ToolDef` with name, description, parameters (OpenAI schema)
3. Register in `_registry.py` via `ToolRegistry.register()`
4. For MCP tools: Server tools auto-register via `registry_adapter.py`

**New Discord Command:**
1. Add slash command handler to `clara_core/discord/commands.py`
2. Register in `setup_slash_commands()` via `@client.slash_command()`
3. For simple commands: may live in `discord_bot.py::DiscordBot` class as message handler

**New Model/Database Table:**
1. Create SQLAlchemy model in `db/models.py`
2. Add imports to `db/__init__.py` for exports
3. Run alembic migration (if setup) or manual SQL for production

**New LLM Provider:**
1. Add provider client initialization to `clara_core/llm.py`
2. Add default models to `DEFAULT_MODELS` dict
3. Create `make_llm_*` function following existing pattern (OpenAI SDK for OpenAI-compatible, Anthropic SDK for Anthropic)
4. Add environment variable loading to `clara_core/config.py`

**New Memory Feature:**
1. Extend `MemoryManager` in `clara_core/memory.py` with new method
2. Add mem0 integration if semantic memory needed
3. Update prompt building in `_build_system_prompt()` if needed

**New Email Service Feature:**
1. Add to `email_service/rules_engine.py` for rule evaluation
2. Or extend `email_service/providers/` with new provider
3. Register in email monitor initialization

**Utilities/Helpers:**
- Shared helpers: `config/` (logging, config) or standalone modules at root
- Platform-specific: `clara_core/{platform}/`
- Tool-related: `tools/` or `clara_core/core_tools/`

## Special Directories

**vendor/mem0/:**
- Purpose: Vendored mem0 library (for development/patching without waiting for upstream)
- Generated: No (checked into git)
- Committed: Yes
- Note: Patched for Anthropic base URL support; excluded from linting via pyproject.toml

**generated/:**
- Purpose: Output from profile bootstrapping (profile_bio.json, interaction_style.json, etc.)
- Generated: Yes (by `scripts/bootstrap_memory.py`)
- Committed: No (in .gitignore)

**clara_files/:**
- Purpose: Per-user local file storage with subdirectories per user_id
- Generated: Yes (created on first file upload)
- Committed: No (in .gitignore)

**.planning/codebase/:**
- Purpose: GSD codebase documentation (this directory)
- Generated: Yes (by GSD mappers)
- Committed: Yes
- Contains: ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, CONCERNS.md, INTEGRATIONS.md, STACK.md

**.mcp_servers/:**
- Purpose: Installed MCP servers (cloned repos, configs, auth tokens)
- Generated: Yes (by MCP installer)
- Committed: No (in .gitignore)
- Structure: `local/` (subprocess-based), `remote/` (HTTP), `.oauth/` (tokens)

---

*Structure analysis: 2026-01-24*
