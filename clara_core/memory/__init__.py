"""Clara Memory System — backed by vendored mem0.

Usage:
    from clara_core.memory import ROOK, Memory

    if ROOK:
        ROOK.add("User prefers dark mode", user_id="user-123")
        results = ROOK.search("preferences", user_id="user-123")
"""

# Cache
from clara_core.memory.cache import GraphCache, RedisCache

# Configuration and singleton
from clara_core.memory.config import (
    ENABLE_GRAPH_MEMORY,
    FALKORDB_GRAPH_NAME,
    FALKORDB_HOST,
    FALKORDB_PASSWORD,
    FALKORDB_PORT,
    GRAPH_STORE_PROVIDER,
    KUZU_DATA_DIR,
    MEM0,  # Backward compatibility alias for ROOK
    MEM0_DATABASE_URL,  # Backward compatibility alias
    MEM0_MODEL,  # Backward compatibility alias
    MEM0_PROVIDER,  # Backward compatibility alias
    QDRANT_DATA_DIR,
    ROOK,
    ROOK_DATABASE_URL,
    ROOK_MODEL,
    ROOK_PROVIDER,
    config,
)
from vendor.mem0 import Memory

# Backward compatibility alias
ClaraMemory = Memory

# Re-export MemoryManager for convenience (actual implementation in memory_manager.py)
try:
    from clara_core.memory_manager import MemoryManager, load_initial_profile
except ImportError:
    MemoryManager = None
    load_initial_profile = None

__all__ = [
    # Core
    "Memory",
    "ClaraMemory",
    # Singleton
    "ROOK",
    "MEM0",
    "config",
    # Settings (ROOK_* preferred)
    "ROOK_PROVIDER",
    "ROOK_MODEL",
    "ROOK_DATABASE_URL",
    # Settings (MEM0_* backward compatibility)
    "MEM0_PROVIDER",
    "MEM0_MODEL",
    "MEM0_DATABASE_URL",
    # Other settings
    "ENABLE_GRAPH_MEMORY",
    "GRAPH_STORE_PROVIDER",
    "QDRANT_DATA_DIR",
    "KUZU_DATA_DIR",
    "FALKORDB_HOST",
    "FALKORDB_PORT",
    "FALKORDB_PASSWORD",
    "FALKORDB_GRAPH_NAME",
    # Cache
    "RedisCache",
    "GraphCache",
    # Backward compatibility
    "MemoryManager",
    "load_initial_profile",
]
