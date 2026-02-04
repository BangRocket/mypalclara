"""Backward compatibility layer for config.mem0.

This module re-exports from clara_core.memory for backward compatibility.
All memory functionality is now in clara_core.memory/.

New code should import directly from clara_core.memory:
    from clara_core.memory import MEM0, ClaraMemory
"""

from __future__ import annotations

import warnings

# Re-export everything from clara_core.memory
from clara_core.memory import (
    MEM0,
    ClaraMemory,
    ClaraMemoryItem,
    ClaraMemoryConfig,
    ClaraMemoryValidationError,
    MemoryType,
    Memory,  # Backward compatibility alias
    MemoryManager,
    load_initial_profile,
    config,
)

from clara_core.memory.config import (
    MEM0_PROVIDER,
    MEM0_MODEL,
    ENABLE_GRAPH_MEMORY,
    GRAPH_STORE_PROVIDER,
    QDRANT_DATA_DIR,
    KUZU_DATA_DIR,
    MEM0_DATABASE_URL,
    NEO4J_URL,
    NEO4J_USERNAME,
    NEO4J_PASSWORD,
)

# Issue a deprecation warning when this module is imported
warnings.warn(
    "config.mem0 is deprecated. Use clara_core.memory instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "MEM0",
    "ClaraMemory",
    "ClaraMemoryItem",
    "ClaraMemoryConfig",
    "ClaraMemoryValidationError",
    "MemoryType",
    "Memory",
    "config",
    "MEM0_PROVIDER",
    "MEM0_MODEL",
    "ENABLE_GRAPH_MEMORY",
    "GRAPH_STORE_PROVIDER",
    "QDRANT_DATA_DIR",
    "KUZU_DATA_DIR",
    "MEM0_DATABASE_URL",
    "NEO4J_URL",
    "NEO4J_USERNAME",
    "NEO4J_PASSWORD",
]
