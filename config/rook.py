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
    MEM0,  # Backward compatibility alias for ROOK
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
    ROOK_PROVIDER,
    ROOK_MODEL,
    ROOK_DATABASE_URL,
    MEM0_PROVIDER,  # Backward compatibility alias
    MEM0_MODEL,  # Backward compatibility alias
    MEM0_DATABASE_URL,  # Backward compatibility alias
    ENABLE_GRAPH_MEMORY,
    GRAPH_STORE_PROVIDER,
    QDRANT_DATA_DIR,
    KUZU_DATA_DIR,
    FALKORDB_HOST,
    FALKORDB_PORT,
    FALKORDB_PASSWORD,
    FALKORDB_GRAPH_NAME,
)

__all__ = [
    "ROOK",
    "MEM0",  # Backward compatibility
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
    "MEM0_PROVIDER",  # Backward compatibility
    "MEM0_MODEL",  # Backward compatibility
    "MEM0_DATABASE_URL",  # Backward compatibility
    "ENABLE_GRAPH_MEMORY",
    "GRAPH_STORE_PROVIDER",
    "QDRANT_DATA_DIR",
    "KUZU_DATA_DIR",
    "FALKORDB_HOST",
    "FALKORDB_PORT",
    "FALKORDB_PASSWORD",
    "FALKORDB_GRAPH_NAME",
]
