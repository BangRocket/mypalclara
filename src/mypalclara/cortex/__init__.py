"""
Cortex - Clara's memory system.

Cortex is not a service Clara queries. It's how she remembers.

Architecture:
- Redis: Fast access (identity, session, working memory)
- Postgres/pgvector: Long-term semantic search
"""

from mypalclara.cortex.manager import CortexManager, cortex_manager

__all__ = ["cortex_manager", "CortexManager"]
