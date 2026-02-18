"""Rook - Clara's memory system configuration.

This module re-exports from clara_core.memory for convenience.
All memory functionality is now in clara_core.memory/.

Usage:
    from config.rook import ROOK, ClaraMemory
    # or
    from clara_core.memory import ROOK, ClaraMemory
"""

from __future__ import annotations

# Re-export everything from clara_core.memory
from clara_core.memory import (
    ROOK,
    ClaraMemory,
    ClaraMemoryConfig,
    ClaraMemoryItem,
    ClaraMemoryValidationError,
    MemoryType,
    config,
)
from clara_core.memory.config import (
    ENABLE_GRAPH_MEMORY,
    GRAPH_STORE_PROVIDER,
    KUZU_DATA_DIR,
    NEO4J_PASSWORD,
    NEO4J_URL,
    NEO4J_USERNAME,
    QDRANT_DATA_DIR,
    ROOK_DATABASE_URL,
    ROOK_MODEL,
    ROOK_PROVIDER,
)

__all__ = [
    "ROOK",
    "ClaraMemory",
    "ClaraMemoryItem",
    "ClaraMemoryConfig",
    "ClaraMemoryValidationError",
    "MemoryType",
    "config",
    "ROOK_PROVIDER",
    "ROOK_MODEL",
    "ROOK_DATABASE_URL",
    "ENABLE_GRAPH_MEMORY",
    "GRAPH_STORE_PROVIDER",
    "QDRANT_DATA_DIR",
    "KUZU_DATA_DIR",
    "NEO4J_URL",
    "NEO4J_USERNAME",
    "NEO4J_PASSWORD",
]
