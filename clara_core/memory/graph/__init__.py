"""Graph memory implementations for Clara Memory System."""

from clara_core.memory.graph.factory import GraphStoreFactory


# Lazy imports to avoid requiring graph dependencies when not used
def get_falkordb_graph():
    """Get FalkorDB MemoryGraph class (requires falkordb dependency)."""
    from clara_core.memory.graph.falkordb import MemoryGraph

    return MemoryGraph


def get_kuzu_graph():
    """Get Kuzu MemoryGraph class (requires kuzu dependency)."""
    from clara_core.memory.graph.kuzu import MemoryGraph

    return MemoryGraph


__all__ = [
    "GraphStoreFactory",
    "get_falkordb_graph",
    "get_kuzu_graph",
]
