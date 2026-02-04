"""Backward compatibility shim for config.mem0.

DEPRECATED: Use config.rook or clara_core.memory instead.

This module redirects all imports to config.rook while issuing a deprecation warning.
"""

from __future__ import annotations

import warnings

# Issue deprecation warning
warnings.warn(
    "config.mem0 is deprecated. Use config.rook or clara_core.memory instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export everything from config.rook
from config.rook import (
    ROOK,
    MEM0,
    ClaraMemory,
    ClaraMemoryItem,
    ClaraMemoryConfig,
    ClaraMemoryValidationError,
    MemoryType,
    Memory,
    MemoryManager,
    load_initial_profile,
    config,
    ROOK_PROVIDER,
    ROOK_MODEL,
    ROOK_DATABASE_URL,
    MEM0_PROVIDER,
    MEM0_MODEL,
    MEM0_DATABASE_URL,
    ENABLE_GRAPH_MEMORY,
    GRAPH_STORE_PROVIDER,
    QDRANT_DATA_DIR,
    KUZU_DATA_DIR,
    NEO4J_URL,
    NEO4J_USERNAME,
    NEO4J_PASSWORD,
)

__all__ = [
    "ROOK",
    "MEM0",
    "ClaraMemory",
    "ClaraMemoryItem",
    "ClaraMemoryConfig",
    "ClaraMemoryValidationError",
    "MemoryType",
    "Memory",
    "config",
    "ROOK_PROVIDER",
    "ROOK_MODEL",
    "ROOK_DATABASE_URL",
    "MEM0_PROVIDER",
    "MEM0_MODEL",
    "MEM0_DATABASE_URL",
    "ENABLE_GRAPH_MEMORY",
    "GRAPH_STORE_PROVIDER",
    "QDRANT_DATA_DIR",
    "KUZU_DATA_DIR",
    "NEO4J_URL",
    "NEO4J_USERNAME",
    "NEO4J_PASSWORD",
]
