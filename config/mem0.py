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
    ENABLE_GRAPH_MEMORY,
    GRAPH_STORE_PROVIDER,
    KUZU_DATA_DIR,
    MEM0,
    MEM0_DATABASE_URL,
    MEM0_MODEL,
    MEM0_PROVIDER,
    NEO4J_PASSWORD,
    NEO4J_URL,
    NEO4J_USERNAME,
    QDRANT_DATA_DIR,
    ROOK,
    ROOK_DATABASE_URL,
    ROOK_MODEL,
    ROOK_PROVIDER,
    ClaraMemory,
    ClaraMemoryConfig,
    ClaraMemoryItem,
    ClaraMemoryValidationError,
    Memory,
    MemoryManager,
    MemoryType,
    config,
    load_initial_profile,
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
