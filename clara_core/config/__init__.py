"""Unified configuration for Clara.

Usage:
    from clara_core.config import get_settings

    s = get_settings()
    s.llm.provider         # "anthropic"
    s.discord.bot_token    # "..."
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from clara_core.config._settings import ClaraSettings

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger("clara_core.config")

_settings: ClaraSettings | None = None
_initialized: bool = False


def get_settings() -> ClaraSettings:
    """Return the singleton ClaraSettings instance (created on first call)."""
    global _settings
    if _settings is None:
        _settings = ClaraSettings()
    return _settings


def reset_settings() -> None:
    """Force re-creation of the settings singleton (useful for tests)."""
    global _settings, _initialized
    _settings = None
    _initialized = False


# Backward compatibility alias
def get_config() -> ClaraSettings:
    """Alias for get_settings() — backward compatibility."""
    return get_settings()


def init_platform(
    on_memory_event: "Callable[[str, dict], None] | None" = None,
) -> None:
    """Initialize the Clara platform.

    Call this once at application startup to:
    1. Load configuration
    2. Initialize database
    3. Initialize MemoryManager singleton
    4. Initialize ToolRegistry singleton
    5. Optionally load initial profile
    """
    global _initialized

    from clara_core.llm import make_llm
    from clara_core.memory_manager import MemoryManager, load_initial_profile
    from clara_core.tools import ToolRegistry
    from db.connection import init_db

    if _initialized:
        logger.debug("Platform already initialized, skipping")
        return

    settings = get_settings()
    logger.info("Initializing platform...")

    init_db()

    llm = make_llm()
    MemoryManager.initialize(llm_callable=llm, on_memory_event=on_memory_event)

    ToolRegistry.initialize()

    if not settings.memory.skip_profile_load:
        load_initial_profile(settings.user_id)

    _initialized = True
    logger.info("Platform initialized successfully")
