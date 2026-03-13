"""Branch-scoped memory operations.

Provides functions to add, search, promote, and discard memories
scoped to specific conversation branches.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("clara.memory.branch")


def add_memory_for_branch(
    messages,
    user_id: str,
    branch_id: str | None = None,
    **kwargs: Any,
):
    """Add memories, optionally scoped to a branch.

    Args:
        messages: Message content (str, dict, or list of dicts).
        user_id: User identifier.
        branch_id: If provided, memories are scoped to this branch.
                   If None, memories are global (no branch_id in metadata).
        **kwargs: Forwarded to ``ROOK.add()``.

    Returns:
        Result dict from the memory system, or None if ROOK is unavailable.
    """
    from mypalclara.core.memory import ROOK

    if ROOK is None:
        logger.warning("ROOK not available, skipping add_memory_for_branch")
        return None

    metadata: dict[str, Any] = kwargs.pop("metadata", None) or {}
    if branch_id is not None:
        metadata["branch_id"] = branch_id

    return ROOK.add(messages=messages, user_id=user_id, metadata=metadata, **kwargs)


def search_memory_for_branch(
    query: str,
    user_id: str,
    branch_id: str | None = None,
    **kwargs: Any,
):
    """Search memories, returning global + branch-scoped results.

    When *branch_id* is provided the search runs against all of the user's
    memories and then post-filters to exclude memories that belong to a
    *different* branch.  This yields:

    * Global memories (no ``branch_id`` in metadata)
    * Memories scoped to the requested *branch_id*

    The post-filter approach is used because the underlying vector stores
    (Qdrant / pgvector) do not uniformly support OR-style filter clauses.

    Args:
        query: Search query string.
        user_id: User identifier.
        branch_id: If provided, include branch-scoped memories for this
                   branch alongside global memories.
        **kwargs: Forwarded to ``ROOK.search()``.

    Returns:
        Result dict from the memory system, or ``{"results": []}`` if
        ROOK is unavailable.
    """
    from mypalclara.core.memory import ROOK

    if ROOK is None:
        logger.warning("ROOK not available, skipping search_memory_for_branch")
        return {"results": []}

    result = ROOK.search(query=query, user_id=user_id, **kwargs)

    if branch_id is not None and result.get("results"):
        filtered = []
        for mem in result["results"]:
            mem_branch = (mem.get("metadata") or {}).get("branch_id")
            # Keep if global (no branch_id) or matches requested branch
            if mem_branch is None or mem_branch == branch_id:
                filtered.append(mem)
        result["results"] = filtered

    return result


def promote_branch_memories(user_id: str, branch_id: str) -> int:
    """Promote branch-scoped memories to global during merge.

    Finds all memories tagged with *branch_id* for this user and removes
    the ``branch_id`` from their metadata so they become globally visible.

    Args:
        user_id: User identifier.
        branch_id: The branch whose memories should be promoted.

    Returns:
        The number of memories promoted.
    """
    from mypalclara.core.memory import ROOK

    if ROOK is None:
        logger.warning("ROOK not available, skipping promote_branch_memories")
        return 0

    all_memories = ROOK.get_all(user_id=user_id, filters={"branch_id": branch_id})
    memories = all_memories.get("results", [])

    promoted = 0
    for mem in memories:
        mem_id = mem["id"]
        # Get the raw record from the vector store so we can update its payload
        existing = ROOK.vector_store.get(vector_id=mem_id)
        if existing and existing.payload:
            updated_payload = dict(existing.payload)
            updated_payload.pop("branch_id", None)
            ROOK.vector_store.set_payload(vector_id=mem_id, payload=updated_payload)
            promoted += 1

    logger.info("Promoted %d branch memories to global (branch=%s, user=%s)", promoted, branch_id, user_id)
    return promoted


def discard_branch_memories(user_id: str, branch_id: str) -> int:
    """Discard branch-scoped memories when a branch is deleted.

    Finds all memories tagged with *branch_id* for this user and deletes
    them from the memory system.

    Args:
        user_id: User identifier.
        branch_id: The branch whose memories should be discarded.

    Returns:
        The number of memories discarded.
    """
    from mypalclara.core.memory import ROOK

    if ROOK is None:
        logger.warning("ROOK not available, skipping discard_branch_memories")
        return 0

    all_memories = ROOK.get_all(user_id=user_id, filters={"branch_id": branch_id})
    memories = all_memories.get("results", [])

    discarded = 0
    for mem in memories:
        ROOK.delete(mem["id"])
        discarded += 1

    logger.info("Discarded %d branch memories (branch=%s, user=%s)", discarded, branch_id, user_id)
    return discarded
