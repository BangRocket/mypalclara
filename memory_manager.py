"""Memory management for Clara.

This module provides backward-compatible exports from clara_core.memory.
New code should import directly from clara_core.

Deprecated:
    Import from clara_core instead:
        from clara_core import MemoryManager, load_initial_profile
"""

from __future__ import annotations

# Re-export everything from clara_core.memory for backward compatibility
from clara_core.memory import (
    CONTEXT_MESSAGE_COUNT,
    MAX_SEARCH_QUERY_CHARS,
    SUMMARY_INTERVAL,
    MemoryManager,
    load_initial_profile,
)

__all__ = [
    "MemoryManager",
    "load_initial_profile",
    "CONTEXT_MESSAGE_COUNT",
    "SUMMARY_INTERVAL",
    "MAX_SEARCH_QUERY_CHARS",
]
