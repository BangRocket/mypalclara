# Coding Conventions

**Analysis Date:** 2026-01-27

## Naming Patterns

**Files:**
- Module files: `snake_case.py` (e.g., `discord_bot.py`, `memory_manager.py`, `llm.py`)
- Test files: `test_*.py` (e.g., `test_events.py`, `test_scheduler.py`, `test_hooks.py`)
- Package init: `__init__.py` - commonly used for re-exports and singleton access
- Config files: Named by domain (e.g., `config/bot.py`, `config/logging.py`, `config/mem0.py`)

**Functions:**
- Private helpers: Prefixed with `_` (e.g., `_load_personality()`, `_extract_name()`, `_worker()`)
- Public functions: `snake_case` with descriptive names (e.g., `get_logger()`, `make_llm()`, `init_platform()`)
- Async functions: Same `snake_case` convention, prefixed with `async def` (e.g., `async def emit()`, `async def execute()`)
- Handler functions: Named `handler()` in closures or `{operation}_handler()` for specific operations (e.g., `_web_search_handler()`)
- Setter/getter patterns: Use explicit names like `set_session_factory()`, `get_instance()`, `get_logger()`

**Classes:**
- `PascalCase` (e.g., `MemoryManager`, `ToolRegistry`, `EventEmitter`, `HookManager`)
- Dataclasses: Explicit `@dataclass` decorator (e.g., `ToolDefinition`, `Event`, `ScheduledTask`)
- Singletons: Include `_instance: ClassVar["ClassName | None"] = None` pattern with `get_instance()` and `initialize()` methods
- Enums: `PascalCase` for enum class, UPPERCASE for values (e.g., `EventType.GATEWAY_STARTUP`, `TaskType.INTERVAL`)

**Variables:**
- `snake_case` for all module and function-level variables
- Constants: UPPERCASE_WITH_UNDERSCORES (e.g., `DEFAULT_TIER`, `CONTEXT_MESSAGE_COUNT`, `MAX_SEARCH_QUERY_CHARS`)
- Private module state: Prefixed with `_` (e.g., `_instance`, `_db_handler`, `_discord_handler`, `_initialized`)
- Loop variables in comprehensions: Single letters acceptable (e.g., `for i in range(...)`)

**Module-level loggers:**
- Instantiated at module top with `logger = get_logger(__name__)` or module-specific name
- Tag-based naming: `logger = get_logger("mem0")`, `logger = get_logger("thread")`, `logger = get_logger("discord")`
- Examples: `config/logging.py` lines 16, 19-21; `clara_core/tools.py` line 16; `clara_core/llm.py` (implicit in modules)

## Code Style

**Formatting:**
- Line length: 120 characters (set in `pyproject.toml` `[tool.ruff] line-length = 120`)
- Indentation: 4 spaces (Python standard)
- Trailing commas: Used in multi-line structures (e.g., function signatures, lists, dicts)
- Blank lines: 2 between top-level functions/classes, 1 between methods within a class

**Linting:**
- Tool: `ruff` for both formatting and linting
- Run formatting: `poetry run ruff format .`
- Run lint checks: `poetry run ruff check .`
- Configuration: `pyproject.toml [tool.ruff]` section (lines 88-110)
  - Enabled rules: E (errors), F (PyFlakes), I (import sorting)
  - Ignored rules: E501 (line too long), E402 (module imports not at top), E741 (ambiguous names), F401 (unused imports in `__init__.py`), F841 (unused variables)
  - Per-file ignores: E501 ignored in `tools/*.py` and `sandbox/*.py` (long tool definitions allowed)

**Import Organization:**

Order (observed across codebase):
1. `from __future__ import annotations` (always first, enables PEP 563 for type hints)
2. Standard library imports: `import os`, `from pathlib import Path`, `from typing import TYPE_CHECKING`
3. TYPE_CHECKING block: `if TYPE_CHECKING: from some_module import SomeClass`
4. Third-party imports: `from anthropic import Anthropic`, `from openai import OpenAI`, `import discord`
5. Relative imports: `from clara_core import ...`, `from config.logging import ...`, `from db import ...`

**Path Aliases:**
- Used via relative imports with package structure
- No explicit alias configuration in `pyproject.toml`
- Imports resolve based on package names: `clara_core`, `config`, `db`, `gateway`, `sandbox`, `adapters`

Example (from `discord_bot.py`):
```python
from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from adapters.discord.adapter import DiscordAdapter

from dotenv import load_dotenv
load_dotenv()

import asyncio
import json
# ... more imports
from clara_core import MemoryManager, make_llm
from config.logging import get_logger
from db import SessionLocal
```

## Error Handling

**Patterns:**
- Raise specific exceptions for known error cases: `ValueError`, `RuntimeError`, `ImportError`
- Catch broad exceptions in critical paths with logging: `except Exception as e:` followed by `logger.error()`
- Re-raise with context when needed: `raise RuntimeError("message")` with descriptive text
- Silent catches for optional imports: `except ImportError: pass` (e.g., `tools.py` lines 304, 353, 395)

Examples:
- `tools.py:87-89`: Raise `RuntimeError` when singleton not initialized
- `tools.py:129`: Raise `ValueError` for duplicate tool names
- `logging.py:130`: Catch broad `Exception`, log to stderr, continue processing
- `logging.py:175-178`: Try queue operation, drop on failure without exception

**Logging errors:**
- Use `logger.error()` with exception context: `logger.error(f"Error listing MCP servers: {e}")`
- Include function/context in message: `[commands]`, `[logging]`, `[api]` tags in error messages
- Never use bare `except` without intent to suppress

## Logging

**Framework:** Python standard `logging` module

**Module logger pattern** (from `config/logging.py`):
```python
from config.logging import get_logger

logger = get_logger("mem0")          # Module name as tag
thread_logger = get_logger("thread") # Specialized loggers per domain
memory_logger = get_logger("memory")
```

**Usage patterns:**
- `logger.info("Server started", extra={"user_id": "123"})` - Info with context
- `logger.error(f"Error: {e}")` - Errors with exceptions
- `logger.warning(f"Warning message")` - Warnings for unusual but recoverable issues
- `logger.debug(f"Debug info")` - Debug details (used sparingly in production)

**Tag-based coloring** (console output):
```python
TAG_COLORS = {
    "api": "\033[94m",      # Blue
    "mem0": "\033[95m",     # Magenta
    "thread": "\033[96m",   # Cyan
    "discord": "\033[93m",  # Yellow
    "db": "\033[92m",       # Green
    "llm": "\033[91m",      # Red
    "email": "\033[97m",    # White
    "tools": "\033[36m",    # Cyan
    "sandbox": "\033[35m",  # Magenta
    "organic": "\033[33m",  # Yellow
}
```

**Handlers:**
- Console handler: Colored output with tags and extra context (user_id, session_id, channel_id)
- Database handler: Async batching to PostgreSQL LogEntry table
- Discord handler: Mirrors logs to Discord channel with rate limiting (5 messages / 5 seconds)

## Comments

**When to Comment:**
- Complex algorithms or non-obvious logic: Explain the "why", not the "what"
- Configuration trade-offs: Why certain values were chosen
- Workarounds: Document why a non-standard approach is necessary
- Legal/licensing: File headers with project info

**Avoid Comments For:**
- Self-documenting code: Good function/variable names are preferred
- Obvious operations: `x = x + 1` doesn't need explanation
- Too much detail: Comments should be at higher abstraction level than code

**Module Docstrings:**
- Triple-quoted string at file top describing purpose and usage
- Format: `"""Purpose. Usage: ... Features: ..."""`
- Example (`discord_bot.py`):
```python
"""
Discord bot for Clara - Multi-user AI assistant with memory.

Inspired by llmcord's clean design, but integrates directly with Clara's
MemoryManager for full mem0 memory support.

Usage:
    poetry run python discord_bot.py [options]
...
"""
```

**Function Docstrings:**
- Triple-quoted docstrings on functions/classes with complex signatures
- Format: Single line summary, then Args/Returns/Raises sections
- Example (`config/logging.py` line 53-54):
```python
def _load_personality() -> str:
    """Load personality from file or env var, or use default."""
```

**JSDoc/Type Hints:**
- Use type hints in function signatures (e.g., `def register(self, name: str, handler: Callable[[dict, Any], Awaitable[str]]) -> None:`)
- Return type hints always included: `-> str:`, `-> dict:`, `-> None:`
- Generics used for complex types: `list[str]`, `dict[str, Any]`, `ClassVar["ClassName | None"]`

## Function Design

**Size:** Most functions stay under 50 lines; longer functions (100+) are complex orchestrators documented with clear sections

**Parameters:**
- Explicit over implicit: Function signatures clearly show what's needed
- Type hints mandatory for public APIs
- Default values for optional parameters: `session_factory=None`, `platform: str | None = None`
- Position-only not used; keyword-only used when API clarity matters

**Return Values:**
- Explicit returns with type hints
- None returns documented: `-> None:` for void operations
- Union types when multiple return types: `-> str | None:`, `-> list[str]`, `-> dict | None`
- Raise documented exceptions instead of returning error codes

**Async patterns:**
- Async functions clearly marked: `async def ...`
- Await all async calls: `result = await async_function()`
- No fire-and-forget patterns without explicit `asyncio.create_task()`

## Module Design

**Exports:**
- `__init__.py` files use `__all__` to declare public API (e.g., `clara_core/__init__.py` lines 49-78)
- Selective imports/re-exports in `__init__.py` expose clean API while hiding internals
- Example pattern:
```python
from clara_core.llm import make_llm, make_llm_streaming
from clara_core.memory import MemoryManager

__all__ = [
    "make_llm",
    "make_llm_streaming",
    "MemoryManager",
]
```

**Barrel Files (re-export pattern):**
- Used to flatten API: `from clara_core import MemoryManager` instead of `from clara_core.memory import MemoryManager`
- Common in `__init__.py` files for public packages
- Keeps internals hidden while allowing clean imports

**Singletons:**
- ClassVar pattern with `_instance` and `initialize()`/`get_instance()` methods
- Example (`tools.py` lines 78-103):
```python
class ToolRegistry:
    _instance: ClassVar["ToolRegistry | None"] = None

    @classmethod
    def get_instance(cls) -> "ToolRegistry":
        if cls._instance is None:
            raise RuntimeError("ToolRegistry not initialized...")
        return cls._instance

    @classmethod
    def initialize(cls) -> "ToolRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
```

**Module-level initialization:**
- Call `init_*()` functions at application startup (e.g., `init_platform()`, `init_logging()`, `init_mcp()`)
- Single responsibility per module: `memory.py` handles memory, `llm.py` handles LLM backends, etc.
- Lazy initialization for optional features: Feature disabled by default, enabled by configuration or explicit call

---

*Convention analysis: 2026-01-27*
