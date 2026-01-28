# Codebase Structure

**Analysis Date:** 2026-01-27

## Directory Layout

```
/Users/heidornj/Code/mypalclara/
├── .githooks/                  # Git hooks for auto version bumping
├── .github/workflows/          # GitHub Actions workflows (CI/CD)
├── .mcp_servers/               # MCP servers (Smithery, npm installs)
├── adapters/                   # Platform adapters (Discord, CLI, Web)
│   ├── base.py                 # GatewayClient base class for WebSocket
│   ├── protocol.py             # Shared protocol types
│   ├── discord/                # Discord platform implementation
│   │   ├── adapter.py          # DiscordAdapter (Strangler fig pattern)
│   │   ├── gateway_client.py   # DiscordGatewayClient for WebSocket
│   │   ├── main.py             # Discord bot startup
│   │   └── __main__.py         # Entry point
│   ├── cli/                    # CLI platform implementation
│   │   ├── adapter.py          # CLIAdapter
│   │   ├── gateway_client.py   # CLIGatewayClient
│   │   ├── shell_executor.py   # Shell command execution
│   │   ├── approval.py         # User confirmation prompts
│   │   ├── logging.py          # CLI-specific logging
│   │   └── main.py             # CLI startup
│   └── web/                    # Web platform (FastAPI)
│       ├── routes/             # HTTP endpoints
│       └── __init__.py         # Web adapter setup
├── backup_service/             # Database backup to S3
├── clara_core/                 # Core platform logic (platform-agnostic)
│   ├── __init__.py             # Public API exports
│   ├── config.py               # ClaraConfig dataclass + init_platform()
│   ├── llm.py                  # LLM backends (OpenRouter, Anthropic, etc.)
│   ├── memory.py               # MemoryManager singleton + context building
│   ├── tools.py                # ToolRegistry singleton + ToolDefinition
│   ├── platform.py             # PlatformAdapter, PlatformMessage abstractions
│   ├── emotional_context.py    # Sentiment tracking for continuity
│   ├── sentiment.py            # Sentiment analysis utilities
│   ├── topic_recurrence.py     # Topic extraction and storage
│   ├── core_tools/             # Built-in tools available to all platforms
│   │   ├── code_execution.py   # Docker/Incus sandbox tools
│   │   ├── memory_tools.py     # mem0 read/write tools
│   │   ├── file_tools.py       # Local file operations
│   │   └── ...                 # Other core tools
│   ├── discord/                # Discord-specific setup (slash commands, utils)
│   │   ├── setup.py            # Slash command registration
│   │   ├── utils.py            # Image resizing, time formatting
│   │   └── cogs/               # Discord.py cogs (command groups)
│   ├── mcp/                    # MCP (Model Context Protocol) integration
│   │   ├── __init__.py         # Public API
│   │   ├── client.py           # MCPClient for stdio/HTTP transports
│   │   ├── manager.py          # MCPServerManager singleton
│   │   ├── installer.py        # Installation from various sources
│   │   ├── local_server.py     # Local stdio server management
│   │   ├── remote_server.py    # Remote HTTP server management
│   │   ├── registry_adapter.py # Bridge MCP tools to ToolRegistry
│   │   └── models.py           # MCPServer SQLAlchemy model
│   └── services/               # Platform services
│       ├── google_workspace.py # Google Sheets/Drive/Docs/Calendar
│       └── github.py           # GitHub API integration
├── clara_files/                # User file storage (local)
├── cli_bot.py                  # CLI entry point (interactive terminal)
├── discord_bot.py              # Discord bot entry point (4384 lines, main driver)
├── email_monitor.py            # Email monitoring service entry point
├── email_service/              # Email monitoring implementation
│   ├── credentials.py          # OAuth token storage and encryption
│   ├── monitor.py              # Email polling logic
│   ├── rules_engine.py         # Rule matching for alerts
│   └── presets.py              # Built-in filter presets
├── gateway/                    # WebSocket gateway for adapters
│   ├── __init__.py             # Public API exports
│   ├── __main__.py             # Entry point: python -m gateway
│   ├── main.py                 # Gateway startup and lifecycle
│   ├── server.py               # GatewayServer (WebSocket server)
│   ├── processor.py            # MessageProcessor (core message routing)
│   ├── llm_orchestrator.py     # LLM calling with tool orchestration
│   ├── tool_executor.py        # Tool execution wrapper
│   ├── router.py               # Message routing logic
│   ├── session.py              # SessionManager + NodeRegistry
│   ├── protocol.py             # Protocol message types
│   ├── events.py               # Event emission system
│   ├── hooks.py                # Hook registration and execution
│   ├── scheduler.py            # Cron/interval task scheduler
│   └── test_client.py          # Test utility for gateway
├── hooks/                      # Hook configuration (YAML)
├── config/                     # Configuration modules
│   ├── logging.py              # Logging setup with module loggers
│   ├── mem0.py                 # mem0 initialization
│   ├── bot.py                  # Bot-specific config
│   └── __init__.py             # Config package
├── db/                         # Database layer
│   ├── __init__.py             # SessionLocal export
│   ├── connection.py           # SQLAlchemy engine setup (PostgreSQL/SQLite)
│   ├── models.py               # SQLAlchemy models (Project, Session, Message, etc.)
│   ├── channel_config.py       # Channel configuration retrieval
│   └── migrations/             # Alembic migrations (auto-generated)
├── docs/                       # Documentation
├── generated/                  # Generated memory JSON (bootstrapping)
├── inputs/                     # User inputs (user_profile.txt)
├── mcp_servers/                # MCP server definitions
│   └── local/                  # Local stdio servers
│       ├── filesystem/         # File system MCP
│       ├── playwright/         # Web automation MCP
│       ├── github/             # GitHub MCP
│       └── tavily/             # Web search MCP
├── personalities/              # Clara personality definitions
├── release_dashboard/          # Release management dashboard (separate service)
├── sandbox/                    # Code execution backends
│   ├── __init__.py             # Public API
│   ├── manager.py              # UnifiedSandboxManager (auto-select)
│   ├── docker.py               # DockerSandboxManager
│   ├── incus.py                # IncusSandboxManager (containers/VMs)
│   └── remote_client.py        # Remote sandbox API client
├── sandbox_service/            # Standalone remote sandbox service
├── storage/                    # File storage backends
│   ├── local_files.py          # LocalFileManager + S3FileManager
│   └── __init__.py
├── scripts/                    # Utility scripts
│   ├── bootstrap_memory.py     # Generate memories from user_profile.txt
│   ├── bump_version.py         # Version management
│   ├── clear_dbs.py            # Clear all data
│   ├── migrate.py              # Database migration runner
│   ├── migrate_to_postgres.py  # Data migration helper
│   ├── restart_bot.py          # Bot restart with optional delay
│   └── imessage_import.py      # Import chat history
├── tests/                      # Test suite
│   ├── gateway/                # Gateway tests
│   └── __init__.py
├── tools/                      # Tool registry and loading
│   ├── __init__.py             # Tool system exports
│   ├── _base.py                # BaseTool class
│   ├── _loader.py              # Dynamic tool loading
│   ├── _registry.py            # Tool registration
│   ├── cli_files.py            # CLI file tools
│   └── cli_shell.py            # CLI shell tools
├── vendor/                     # Vendored dependencies
│   └── mem0/                   # mem0 with anthropic_base_url fix
├── api_service/                # OAuth callback service (separate deployment)
├── .env.example                # Environment variables template
├── .env                        # Local environment (gitignored)
├── docker-compose.yml          # Docker Compose with profiles
├── Dockerfile                  # Discord bot image
├── VERSION                     # CalVer version (auto-bumped)
├── pyproject.toml              # Poetry dependencies + metadata
├── poetry.lock                 # Locked dependency versions
├── CLAUDE.md                   # Developer instructions (this file!)
└── README.md
```

## Directory Purposes

**adapters/:**
- Purpose: Platform-specific implementations that connect to Clara Core
- Contains: Discord, CLI, Web adapter code + gateway client for WebSocket
- Key files: `base.py` (GatewayClient), `protocol.py` (shared types)
- Pattern: Each adapter has `adapter.py` (PlatformAdapter impl), `main.py` (startup), `gateway_client.py` (WebSocket)

**clara_core/:**
- Purpose: Platform-independent business logic
- Contains: LLM backends, MemoryManager, ToolRegistry, MCP integration, platform abstractions
- Key exports: `init_platform()`, `MemoryManager`, `ToolRegistry`
- Sub-packages: `discord/` (slash commands), `mcp/` (server management), `services/` (Google, GitHub), `core_tools/` (built-in tools)

**gateway/:**
- Purpose: Central message routing hub for platform adapters
- Contains: WebSocket server, message processor, LLM orchestrator, tool executor, hooks/scheduler
- Entry point: `python -m gateway`
- Key classes: `GatewayServer`, `MessageProcessor`, `LLMOrchestrator`, `ToolExecutor`

**db/:**
- Purpose: Database access layer
- Contains: SQLAlchemy models, connection setup (PostgreSQL/SQLite), migrations
- Key models: `Project`, `Session`, `Message`, `ChannelSummary`, `ChannelConfig`, `MCPServer`, email-related tables

**config/:**
- Purpose: Application configuration
- Contains: Logging setup, mem0 initialization, bot config, centralized ClaraConfig
- Key functions: `init_logging()`, `load_dotenv()`, mem0 provider setup

**sandbox/:**
- Purpose: Code execution backends
- Contains: Docker, Incus, Remote sandbox managers
- Pattern: UnifiedSandboxManager auto-selects based on configuration and availability

**storage/:**
- Purpose: File storage backends
- Contains: Local file manager, S3-compatible storage
- Usage: Persist user files, save Discord attachments

**scripts/:**
- Purpose: Maintenance and utility scripts
- Contains: Version bumping, DB migrations, memory bootstrapping, data import/export
- Key scripts: `bump_version.py` (CalVer), `migrate.py` (Alembic), `bootstrap_memory.py` (mem0 init)

**tools/:**
- Purpose: Tool registration and loading system
- Contains: BaseTool class, dynamic loader, registry, CLI-specific tools
- Pattern: Dynamically load tools, register with ToolRegistry

## Key File Locations

**Entry Points:**
- `discord_bot.py`: Main Discord bot (4384 lines, handles all Discord events)
- `cli_bot.py`: CLI entry point
- `email_monitor.py`: Email monitoring service
- `gateway/__main__.py`: Gateway server entry point

**Configuration:**
- `.env`: Environment variables (gitignored)
- `.env.example`: Template
- `VERSION`: CalVer version string (auto-bumped after commits)
- `pyproject.toml`: Poetry dependencies + metadata
- `docker-compose.yml`: Local dev setup with profiles

**Core Logic:**
- `clara_core/memory.py`: MemoryManager (session handling, mem0 integration, context building)
- `clara_core/llm.py`: LLM backends abstraction (OpenRouter, Anthropic, etc.)
- `clara_core/tools.py`: ToolRegistry singleton
- `config/mem0.py`: mem0 initialization
- `db/models.py`: SQLAlchemy models for persistence

**Testing:**
- `tests/gateway/`: Gateway unit tests
- Test files follow pattern: `test_*.py` or `*_test.py`

## Naming Conventions

**Files:**
- Snake case: `memory_manager.py`, `llm_backends.py`, `discord_bot.py`
- Test files: `test_processor.py`, `test_hooks.py`
- Entry points: `__main__.py` for module execution

**Directories:**
- Snake case: `clara_core/`, `email_service/`, `sandbox/`
- Acronyms lowercase: `mcp/`, `db/`

**Classes:**
- PascalCase: `MemoryManager`, `ToolRegistry`, `GatewayServer`, `MessageProcessor`
- Adapters: `*Adapter` (e.g., `DiscordAdapter`, `PlatformAdapter`)
- Managers: `*Manager` (e.g., `MCPServerManager`, `SessionManager`)

**Functions:**
- Snake case: `make_llm()`, `get_context()`, `init_platform()`
- Getters: `get_*()`, `_get_*()` for internal
- Setters: `set_*()`
- Predicates: `is_*()`, `has_*()`

**Variables:**
- Constants: UPPER_SNAKE_CASE (`DEFAULT_TIER`, `MAX_MEMORIES_PER_TYPE`)
- Module-level: snake_case (`session_logger`, `_openrouter_client`)

**Types:**
- TypeVar: PascalCase (`T`, `MessageType`)
- Protocols: `*Protocol` suffix
- Dataclasses: PascalCase (`ToolDefinition`, `PlatformMessage`)

## Where to Add New Code

**New Feature (e.g., scheduling, image generation):**
- Implementation: `clara_core/` (shared logic) or `clara_core/core_tools/` (if a tool)
- Discord-specific: `adapters/discord/` or `clara_core/discord/`
- Tests: `tests/` with same relative path
- Register with ToolRegistry if it's a tool

**New Platform Adapter (e.g., Slack, Telegram):**
- Create: `adapters/slack/` with:
  - `adapter.py` - Implement PlatformAdapter interface
  - `gateway_client.py` - Implement WebSocket client for gateway connection
  - `main.py` - Platform startup logic
  - `__main__.py` - Entry point
- Connect to gateway server in `gateway/main.py`

**New Tool:**
- If simple: Create in `clara_core/core_tools/` with ToolDefinition dataclass
- If complex: Create subdirectory with module structure
- Register with ToolRegistry in `__init__()` of the tool module
- Add to appropriate handler in `gateway/tool_executor.py` or auto-register

**New Database Model:**
- Add to `db/models.py`
- Create migration: `poetry run python scripts/migrate.py create "description"`
- Migration files auto-generated in `db/migrations/versions/`

**New Configuration Option:**
- Add field to `ClaraConfig` dataclass in `clara_core/config.py`
- Add environment variable loading in `init_platform()`
- Document in `CLAUDE.md`

**Shared Utilities:**
- Non-tool utilities: `clara_core/` as module-level functions
- Storage utilities: `storage/` package
- Sandbox utilities: `sandbox/` package

## Special Directories

**vendor/mem0/:**
- Purpose: Vendored mem0 library with anthropic_base_url fix
- Generated: No (checked in)
- Committed: Yes
- Notes: Contains fix for Anthropic proxy support (e.g., clewdr)

**clara_files/:**
- Purpose: Local file storage for user files
- Generated: Yes (auto-created on first use)
- Committed: No (gitignored)
- Structure: `clara_files/{user_id}/` per user

**.mcp_servers/:**
- Purpose: Installed MCP servers from Smithery, npm, GitHub, Docker
- Generated: Yes (auto-populated by installer)
- Committed: No (gitignored)
- Structure: `local/` (stdio servers), `hosted/` (Smithery HTTP), cloned repos

**db/migrations/:**
- Purpose: Alembic database migrations
- Generated: Yes (auto-created by `migrate.py create`)
- Committed: Yes
- Pattern: Timestamped files in `versions/`

**generated/:**
- Purpose: Output of memory bootstrapping process
- Generated: Yes (from `bootstrap_memory.py`)
- Committed: No (gitignored)
- Files: `profile_bio.json`, `interaction_style.json`, `project_seed.json`

---

*Structure analysis: 2026-01-27*
