# Coding Conventions

**Analysis Date:** 2026-01-24

## Naming Patterns

**Files:**
- Snake_case for all Python files (e.g., `discord_bot.py`, `memory_manager.py`)
- Underscore prefix for private/internal modules (e.g., `_base.py`, `_registry.py`, `_loader.py`)
- Descriptive names reflecting purpose (e.g., `channel_config.py`, `emotional_context.py`)

**Functions:**
- Snake_case for all functions (e.g., `get_logger()`, `make_llm()`, `_format_message_timestamp()`)
- Underscore prefix for private/internal functions (e.g., `_get_openrouter_client()`, `_has_generated_memories()`)
- Descriptive names indicating action/return (e.g., `execute_python()`, `compute_emotional_arc()`, `finalize_conversation_emotional_context()`)

**Variables:**
- Snake_case for local variables and parameters (e.g., `user_id`, `channel_id`, `message_content`)
- UPPERCASE for module-level constants (e.g., `CONTEXT_MESSAGE_COUNT`, `DEFAULT_TIMEZONE`, `MIN_MESSAGES_FOR_ARC`)
- Private module variables use underscore prefix (e.g., `_conversation_sentiments`, `_openrouter_client`)

**Types:**
- PascalCase for classes (e.g., `ToolDef`, `ToolContext`, `EmotionalSummary`, `ToolRegistry`)
- Type hints with modern Python syntax (e.g., `dict[str, Any]`, `list[str] | None` instead of `Optional`)
- Literal types for constants (e.g., `ModelTier = Literal["high", "mid", "low"]`)

## Code Style

**Formatting:**
- Line length: 120 characters (configured in `pyproject.toml`)
- Indentation: 4 spaces (Python standard)
- Tool: Ruff for formatting and linting

**Linting:**
- Ruff configuration in `pyproject.toml` with:
  - `select = ["E", "F", "I"]` - Error, Pyflakes, Import checks
  - `ignore = ["E501", "E402", "E741", "F401", "F841"]` - Length, import order, ambiguous names, unused imports/vars
- Per-file ignores:
  - `__init__.py` ignores F401 (unused imports - intentional re-exports)
  - `tools/*.py` ignores E501 (line length for descriptive tool definitions)
  - `sandbox/*.py` ignores E501 (line length for complex tool definitions)

**Code Format Example:**
```python
from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from sqlalchemy.orm import Session as OrmSession

logger = get_logger("module_name")

# Module constants
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3

def public_function(param: str) -> dict[str, Any]:
    """Public function with docstring."""
    return {"result": param}

def _private_function() -> None:
    """Private function with underscore prefix."""
    pass
```

## Import Organization

**Order:**
1. `from __future__ import annotations` (at very top)
2. Standard library imports (sorted alphabetically)
3. Third-party imports (sorted alphabetically)
4. Local/relative imports (sorted alphabetically)
5. TYPE_CHECKING conditional imports (for type hints only)

**Path Aliases:**
- No path aliases configured - uses absolute imports from project root
- Clara core modules imported as `from clara_core import ...`
- Database models imported as `from db.models import ...`
- Configuration imported as `from config.logging import ...`

**Example Import Block:**
```python
from __future__ import annotations

import asyncio
import json
import os
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Generator, Literal

from anthropic import Anthropic
from openai import OpenAI
from PIL import Image

from clara_core import MemoryManager, ToolRegistry
from config.logging import get_logger
from db.models import Message, Session

if TYPE_CHECKING:
    from sqlalchemy.orm import Session as OrmSession
```

## Error Handling

**Patterns:**
- Try-except blocks with specific exception types (avoid bare `except:`)
- Log errors with `logger.error()` including `exc_info=True` for full traceback
- Raise exceptions with descriptive messages when caller needs to know about failure
- Fallback to defaults when safe (e.g., timezone handling, configuration loading)

**Pattern Example:**
```python
try:
    result = some_risky_operation()
except ValueError as e:
    logger.error(f"Invalid value: {e}", exc_info=True)
    return None
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise RuntimeError(f"Operation failed: {e}") from e
```

**Common Practices:**
- Validate inputs at function entry: `if not api_key: raise RuntimeError("API key required")`
- Use try-finally for resource cleanup (database sessions, file handles)
- Log warnings for degraded functionality (e.g., missing optional dependencies)
- Wrap external service calls in try-except to prevent cascade failures

## Logging

**Framework:** Python's built-in `logging` module via custom `get_logger()` from `config.logging`

**Patterns:**
- Get logger at module level: `logger = get_logger("module_name")`
- Module names are short tags: "api", "discord", "mem0", "llm", "email", "tools", "db", "sandbox", "organic"
- Log levels: DEBUG (detailed), INFO (normal ops), WARNING (degraded), ERROR (failures), CRITICAL (fatal)
- Include context with `extra` dict: `logger.info("Event", extra={"user_id": user_id, "session_id": session_id})`

**Logging Patterns:**
```python
logger = get_logger("module_name")

logger.info("Operation started", extra={"user_id": user_id})
logger.warning("Fallback used", extra={"reason": "primary_method_failed"})
logger.error(f"Operation failed: {e}", exc_info=True)
logger.debug("Internal state", extra={"state": state_dict})
```

**Special Features:**
- Structured logging with ANSI colors in console output
- Context tags automatically extracted from LogRecord attributes
- Database persistence with async handler (non-blocking)
- Discord integration: logs can be mirrored to `DISCORD_LOG_CHANNEL_ID` if set

## Comments

**When to Comment:**
- Complex algorithm explanations (WHY, not WHAT)
- Non-obvious design decisions or tradeoffs
- References to external resources (RFC, issue links, design docs)
- Workarounds for known issues/limitations with ticket numbers
- Configuration context (e.g., "Railway and other hosts use postgres:// prefix")

**What NOT to comment:**
- Obvious code that reads itself
- What the next line does (code should be self-documenting)
- Redundant comments that repeat the code

**JSDoc/TSDoc (Docstrings):**
- Use for all public functions and classes
- Format: Summary line, optional blank line, detailed description, Args/Returns sections
- Include type information in docstrings (especially for complex types)

**Docstring Pattern:**
```python
def track_message_sentiment(
    user_id: str,
    channel_id: str,
    message_content: str,
) -> float:
    """Track sentiment for a message in an active conversation.

    Analyzes message text using VADER sentiment analyzer and stores
    results in per-conversation tracking for arc computation.

    Args:
        user_id: The user sending the message
        channel_id: The channel/DM where the message was sent
        message_content: The message text to analyze

    Returns:
        The compound sentiment score (-1.0 to +1.0)
    """
```

## Function Design

**Size:** Prefer functions under 50 lines; break complex logic into helper functions

**Parameters:**
- Use dataclasses for multiple related parameters (e.g., `ToolContext`, `EmotionalSummary`)
- Avoid single-letter parameter names except in loops
- Type hints required for all parameters and return values

**Return Values:**
- Use dataclass instances for complex returns (not tuples)
- Return None explicitly for no-op functions
- Use `tuple[type, type]` for multiple returns (rare, prefer dataclass instead)
- Union types (e.g., `dict | None`) for optional returns

**Function Organization Example:**
```python
@dataclass
class OperationResult:
    """Result of an operation."""
    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None

def perform_operation(config: Config, user_id: str) -> OperationResult:
    """Perform operation with given configuration."""
    try:
        result = _do_work(config, user_id)
        return OperationResult(success=True, data=result)
    except ValueError as e:
        return OperationResult(success=False, error=str(e))
```

## Module Design

**Exports:**
- Public API explicitly listed in module docstring
- Use `__all__` to document public interface
- Private functions/classes use underscore prefix
- Singleton classes expose `.get_instance()` class method

**Singleton Pattern:**
```python
class Singleton:
    """Thread-safe singleton."""
    _instance: ClassVar[Singleton | None] = None

    @classmethod
    def get_instance(cls) -> Singleton:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset instance (for testing)."""
        cls._instance = None
```

**Barrel Files:**
- `__init__.py` files re-export public API with `__all__`
- Include module docstring explaining package purpose
- Import and expose singletons (e.g., `from .memory import MemoryManager`)

**Barrel File Pattern:**
```python
"""Clara Core - Shared infrastructure for Clara platform."""

from __future__ import annotations

from clara_core.memory import MemoryManager
from clara_core.tools import ToolRegistry

__all__ = [
    "MemoryManager",
    "ToolRegistry",
]
```

---

*Convention analysis: 2026-01-24*
