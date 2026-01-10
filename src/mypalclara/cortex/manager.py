"""
Cortex Manager - Clara's memory system.

Cortex is not a service Clara queries. It's how she remembers.

Architecture:
- Redis: Fast access (identity, session, working memory)
- Postgres/pgvector: Long-term semantic search

Phase 1: Stub implementation with in-memory fallbacks
Phase 2: Full Redis + Postgres integration
"""

import logging
from datetime import datetime
from typing import Optional

from mypalclara.models.state import MemoryContext, QuickContext

logger = logging.getLogger(__name__)


class CortexManager:
    """
    Adapter for Cortex memory system.

    Cortex is Clara's memory - not a service she queries,
    but how she remembers.
    """

    def __init__(self):
        self.redis_client = None  # Initialize in setup
        self.pg_pool = None  # Initialize in setup
        self._initialized = False

        # In-memory fallbacks for Phase 1
        self._identity_store: dict[str, dict] = {}
        self._session_store: dict[str, dict] = {}
        self._working_store: dict[str, list] = {}

    async def initialize(self):
        """Initialize connections to Cortex storage."""
        if self._initialized:
            return

        # Phase 1: Use in-memory fallbacks
        # Phase 2 will add Redis and Postgres connections
        logger.info("[cortex] Initialized (in-memory mode)")
        self._initialized = True

    async def get_quick_context(self, user_id: str) -> QuickContext:
        """
        Fast retrieval for reflexive decisions.
        Identity + session only. No semantic search.
        """
        await self.initialize()

        # Get identity facts
        identity_data = self._identity_store.get(user_id, {})
        identity_facts = [f"{k}: {v}" for k, v in identity_data.items()]

        # Get session
        session_data = self._session_store.get(user_id, {})

        return QuickContext(
            user_id=user_id,
            user_name=session_data.get("user_name", "unknown"),
            identity_facts=identity_facts,
            session=session_data,
            last_interaction=session_data.get("last_active"),
        )

    async def get_full_context(
        self,
        user_id: str,
        query: str,
        project_id: Optional[str] = None,
    ) -> MemoryContext:
        """
        Full retrieval for conscious thought.
        Identity + session + working memory + semantic retrieval.
        """
        await self.initialize()

        # Get quick context first
        quick = await self.get_quick_context(user_id)

        # Get working memory (recent, emotionally weighted)
        working_items = self._working_store.get(user_id, [])
        working_memories = [{"content": item, "score": 0.5} for item in working_items[-20:]]

        # Semantic search in long-term memory (stub for Phase 1)
        retrieved_memories = await self._semantic_search(user_id=user_id, query=query, limit=20)

        # Get project context if applicable
        project_context = None
        if project_id:
            project_context = await self._get_project_context(project_id)

        return MemoryContext(
            user_id=user_id,
            user_name=quick.user_name,
            identity_facts=quick.identity_facts,
            session=quick.session,
            working_memories=working_memories,
            retrieved_memories=retrieved_memories,
            project_context=project_context,
        )

    async def remember(
        self,
        user_id: str,
        content: str,
        importance: float = 0.5,
        category: Optional[str] = None,
        metadata: Optional[dict] = None,
    ):
        """
        Store something Clara noticed or decided to remember.

        High importance = longer in working memory.
        Importance >= 1.0 = promote to identity layer (permanent).
        """
        await self.initialize()

        # Calculate TTL based on emotional importance
        ttl_minutes = self._importance_to_ttl(importance)

        # Identity-level facts (importance >= 1.0) go to permanent storage
        if ttl_minutes == -1:
            if user_id not in self._identity_store:
                self._identity_store[user_id] = {}
            field = category or f"fact_{hash(content) % 10000}"
            self._identity_store[user_id][field] = content
            logger.info(f"[cortex] Promoted to identity: {content[:50]}...")
        else:
            # Add to working memory
            if user_id not in self._working_store:
                self._working_store[user_id] = []
            self._working_store[user_id].append(content)
            # Keep only last 50 items in working memory
            self._working_store[user_id] = self._working_store[user_id][-50:]
            logger.info(f"[cortex] Remembered: {content[:50]}... (importance: {importance})")

    async def update_session(self, user_id: str, updates: dict):
        """Update session state."""
        await self.initialize()

        if user_id not in self._session_store:
            self._session_store[user_id] = {}

        # Filter None values
        clean_updates = {k: v for k, v in updates.items() if v is not None}
        self._session_store[user_id].update(clean_updates)

    def _importance_to_ttl(self, importance: float) -> int:
        """
        Convert importance score to TTL in minutes.

        | Score     | TTL       | Example                          |
        | --------- | --------- | -------------------------------- |
        | 0.0 - 0.2 | 30 min    | "User said ok"                   |
        | 0.2 - 0.4 | 90 min    | "Good conversation"              |
        | 0.4 - 0.6 | 180 min   | "Helped debug tricky issue"      |
        | 0.6 - 0.8 | 300 min   | "User shared something personal" |
        | 0.8 - 1.0 | 360 min   | "Major breakthrough"             |
        | >= 1.0    | PERMANENT | Promoted to identity layer       |
        """
        if importance >= 1.0:
            return -1  # Signal for identity promotion
        elif importance < 0.2:
            return 30
        elif importance < 0.4:
            return 90
        elif importance < 0.6:
            return 180
        elif importance < 0.8:
            return 300
        else:
            return 360

    async def _semantic_search(
        self,
        user_id: str,
        query: str,
        limit: int = 20,
    ) -> list[dict]:
        """Search long-term memory using embeddings."""
        # Phase 1: Return empty (no semantic search yet)
        # Phase 2: Implement with pgvector
        return []

    async def _store_longterm(
        self,
        user_id: str,
        content: str,
        category: Optional[str],
        metadata: dict,
    ):
        """Store in long-term memory with embedding."""
        # Phase 1: No-op
        # Phase 2: Implement with pgvector
        pass

    async def _get_project_context(self, project_id: str) -> Optional[dict]:
        """Get project-specific context."""
        # Phase 1: Return None
        # Phase 2: Implement project context retrieval
        return None


# Singleton instance
cortex_manager = CortexManager()
