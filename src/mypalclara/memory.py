"""
Memory adapter - wraps the cortex package for use in mypalclara.

Provides a singleton `memory_manager` that integrates with the LangGraph nodes.

Environment variables are loaded automatically by cortex's pydantic-settings:
- CORTEX_REDIS_HOST, CORTEX_REDIS_PORT, CORTEX_REDIS_PASSWORD
- CORTEX_POSTGRES_HOST, CORTEX_POSTGRES_PORT, CORTEX_POSTGRES_USER, etc.
- CORTEX_EMBEDDING_API_KEY, CORTEX_EMBEDDING_MODEL
- CORTEX_NEO4J_URI, CORTEX_NEO4J_USER, CORTEX_NEO4J_PASSWORD
- CORTEX_ENABLE_GRAPH_MEMORY
"""

import logging
from typing import Optional

from cortex import CortexConfig, MemoryManager
from cortex import MemoryContext as CortexMemoryContext

from mypalclara.models.state import MemoryContext, QuickContext

logger = logging.getLogger(__name__)

# Lazy initialization - created on first use
_memory_manager: MemoryManager | None = None


def _get_manager() -> MemoryManager:
    """Get or create the memory manager singleton."""
    global _memory_manager
    if _memory_manager is None:
        config = CortexConfig()
        _memory_manager = MemoryManager(config)
    return _memory_manager


def _convert_to_mypalclara_context(cortex_ctx: CortexMemoryContext) -> MemoryContext:
    """Convert cortex MemoryContext to mypalclara MemoryContext format."""
    # Convert identity dict to list of fact strings
    identity_facts = [
        f"{k}: {v}" for k, v in cortex_ctx.identity.items()
        if k not in ("updated_at", "created_at")
    ]

    # Convert Memory objects to dicts
    working_memories = [
        {
            "content": m.content,
            "score": m.importance,
            "emotional_score": m.emotional_score,
        }
        for m in cortex_ctx.working
    ]

    retrieved_memories = [
        {
            "content": m.content,
            "category": m.memory_type.value if m.memory_type else None,
            "importance": m.importance,
            "similarity": getattr(m, "similarity", None),
        }
        for m in cortex_ctx.retrieved
    ]

    return MemoryContext(
        user_id=cortex_ctx.user_id,
        user_name=cortex_ctx.session.get("user_name", "unknown"),
        identity_facts=identity_facts,
        session=cortex_ctx.session,
        working_memories=working_memories,
        retrieved_memories=retrieved_memories,
        project_context=cortex_ctx.project,
    )


async def get_quick_context(user_id: str) -> QuickContext:
    """Get lightweight context for reflexive decisions."""
    # Use cortex's get_context with minimal query for quick access
    cortex_ctx = await _get_manager().get_context(user_id, query="")

    identity_facts = [
        f"{k}: {v}" for k, v in cortex_ctx.identity.items()
        if k not in ("updated_at", "created_at")
    ]

    return QuickContext(
        user_id=cortex_ctx.user_id,
        user_name=cortex_ctx.session.get("user_name", "unknown"),
        identity_facts=identity_facts,
        session=cortex_ctx.session,
        last_interaction=cortex_ctx.session.get("last_active"),
    )


async def get_full_context(
    user_id: str,
    query: str,
    project_id: Optional[str] = None,
) -> MemoryContext:
    """Get full memory context for a conversation turn."""
    cortex_ctx = await _get_manager().get_context(
        user_id, query=query, project_id=project_id
    )
    return _convert_to_mypalclara_context(cortex_ctx)


async def remember(
    user_id: str,
    content: str,
    importance: float = 0.5,
    category: Optional[str] = None,
    metadata: Optional[dict] = None,
):
    """Store a memory."""
    return await _get_manager().store(
        user_id=user_id,
        content=content,
        importance=importance,
        category=category,
        metadata=metadata or {},
    )


async def update_session(user_id: str, updates: dict):
    """Update session state."""
    return await _get_manager().update_session(user_id, updates)


async def initialize():
    """Initialize memory system connections."""
    await _get_manager().initialize()
    logger.info("[memory] Cortex memory system initialized")


async def close():
    """Close memory system connections."""
    manager = _get_manager()
    await manager.close()
    logger.info("[memory] Cortex memory system closed")
