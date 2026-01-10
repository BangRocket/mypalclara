"""
Cortex Manager - Clara's memory system.

Cortex is not a service Clara queries. It's how she remembers.

Architecture:
- Redis: Fast access (identity, session, working memory)
- Postgres/pgvector: Long-term semantic search

Falls back to in-memory storage if Redis is unavailable.
"""

import logging
from datetime import datetime
from typing import Optional

from mypalclara.config.settings import settings
from mypalclara.models.state import MemoryContext, QuickContext

logger = logging.getLogger(__name__)


class CortexManager:
    """
    Adapter for Cortex memory system.

    Cortex is Clara's memory - not a service she queries,
    but how she remembers.
    """

    def __init__(self):
        self.redis_client = None
        self.pg_pool = None
        self._initialized = False
        self._use_redis = False

        # In-memory fallbacks
        self._identity_store: dict[str, dict] = {}
        self._session_store: dict[str, dict] = {}
        self._working_store: dict[str, list[tuple[str, float, float]]] = {}  # (content, importance, timestamp)

    async def initialize(self):
        """Initialize connections to Cortex storage."""
        if self._initialized:
            return

        # Try to connect to Redis
        try:
            import redis.asyncio as redis

            self.redis_client = redis.Redis(
                host=settings.cortex_redis_host,
                port=settings.cortex_redis_port,
                decode_responses=True,
            )
            # Test connection
            await self.redis_client.ping()
            self._use_redis = True
            logger.info(f"[cortex] Connected to Redis at {settings.cortex_redis_host}:{settings.cortex_redis_port}")
        except Exception as e:
            logger.warning(f"[cortex] Redis unavailable ({e}), using in-memory fallback")
            self._use_redis = False
            self.redis_client = None

        # Try to connect to Postgres for semantic search
        try:
            import asyncpg

            self.pg_pool = await asyncpg.create_pool(
                host=settings.cortex_postgres_host,
                port=settings.cortex_postgres_port,
                user=settings.cortex_postgres_user,
                password=settings.cortex_postgres_password,
                database=settings.cortex_postgres_database,
                min_size=1,
                max_size=5,
            )
            logger.info(
                f"[cortex] Connected to Postgres at {settings.cortex_postgres_host}:{settings.cortex_postgres_port}"
            )
        except Exception as e:
            logger.warning(f"[cortex] Postgres unavailable ({e}), semantic search disabled")
            self.pg_pool = None

        self._initialized = True
        logger.info(f"[cortex] Initialized (redis={self._use_redis}, postgres={self.pg_pool is not None})")

    async def get_quick_context(self, user_id: str) -> QuickContext:
        """
        Fast retrieval for reflexive decisions.
        Identity + session only. No semantic search.
        Target: < 10ms
        """
        await self.initialize()

        if self._use_redis:
            return await self._get_quick_context_redis(user_id)
        else:
            return self._get_quick_context_memory(user_id)

    async def _get_quick_context_redis(self, user_id: str) -> QuickContext:
        """Get quick context from Redis."""
        # Get identity facts
        identity_key = f"identity:{user_id}"
        identity_data = await self.redis_client.hgetall(identity_key)
        identity_facts = [f"{k}: {v}" for k, v in identity_data.items()] if identity_data else []

        # Get session
        session_key = f"session:{user_id}"
        session_data = await self.redis_client.hgetall(session_key)
        session = dict(session_data) if session_data else {}

        return QuickContext(
            user_id=user_id,
            user_name=session.get("user_name", "unknown"),
            identity_facts=identity_facts,
            session=session,
            last_interaction=session.get("last_active"),
        )

    def _get_quick_context_memory(self, user_id: str) -> QuickContext:
        """Get quick context from in-memory store."""
        identity_data = self._identity_store.get(user_id, {})
        identity_facts = [f"{k}: {v}" for k, v in identity_data.items()]
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
        Target: < 500ms
        """
        await self.initialize()

        # Get quick context first
        quick = await self.get_quick_context(user_id)

        # Get working memory
        if self._use_redis:
            working_memories = await self._get_working_memory_redis(user_id)
        else:
            working_memories = self._get_working_memory_memory(user_id)

        # Semantic search in long-term memory
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

    async def _get_working_memory_redis(self, user_id: str) -> list[dict]:
        """Get working memory from Redis sorted set."""
        working_key = f"working:{user_id}"
        # Get items with scores (importance)
        items = await self.redis_client.zrevrange(working_key, 0, 20, withscores=True)
        return [{"content": item[0], "score": item[1]} for item in items] if items else []

    def _get_working_memory_memory(self, user_id: str) -> list[dict]:
        """Get working memory from in-memory store."""
        items = self._working_store.get(user_id, [])
        # Sort by importance (descending) and take top 20
        sorted_items = sorted(items, key=lambda x: x[1], reverse=True)[:20]
        return [{"content": item[0], "score": item[1]} for item in sorted_items]

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

        ttl_minutes = self._importance_to_ttl(importance)

        if self._use_redis:
            await self._remember_redis(user_id, content, importance, ttl_minutes, category)
        else:
            self._remember_memory(user_id, content, importance, ttl_minutes, category)

        # Also store in long-term (if Postgres available)
        if self.pg_pool:
            await self._store_longterm(user_id, content, category, metadata or {})

    async def _remember_redis(
        self,
        user_id: str,
        content: str,
        importance: float,
        ttl_minutes: int,
        category: Optional[str],
    ):
        """Store memory in Redis."""
        if ttl_minutes == -1:
            # Identity-level facts go to permanent hash
            identity_key = f"identity:{user_id}"
            field = category or f"fact_{hash(content) % 10000}"
            await self.redis_client.hset(identity_key, field, content)
            logger.info(f"[cortex] Promoted to identity: {content[:50]}...")
        else:
            # Working memory goes to sorted set with importance score
            working_key = f"working:{user_id}"
            await self.redis_client.zadd(working_key, {content: importance})
            # Set TTL on the whole set
            await self.redis_client.expire(working_key, ttl_minutes * 60)
            logger.info(f"[cortex] Remembered: {content[:50]}... (importance: {importance}, ttl: {ttl_minutes}m)")

    def _remember_memory(
        self,
        user_id: str,
        content: str,
        importance: float,
        ttl_minutes: int,
        category: Optional[str],
    ):
        """Store memory in in-memory store."""
        if ttl_minutes == -1:
            # Identity-level facts
            if user_id not in self._identity_store:
                self._identity_store[user_id] = {}
            field = category or f"fact_{hash(content) % 10000}"
            self._identity_store[user_id][field] = content
            logger.info(f"[cortex] Promoted to identity: {content[:50]}...")
        else:
            # Working memory
            if user_id not in self._working_store:
                self._working_store[user_id] = []
            timestamp = datetime.utcnow().timestamp()
            self._working_store[user_id].append((content, importance, timestamp))
            # Keep only last 50 items
            self._working_store[user_id] = self._working_store[user_id][-50:]
            logger.info(f"[cortex] Remembered: {content[:50]}... (importance: {importance})")

    async def update_session(self, user_id: str, updates: dict):
        """Update session state."""
        await self.initialize()

        # Filter None values
        clean_updates = {k: str(v) for k, v in updates.items() if v is not None}
        if not clean_updates:
            return

        if self._use_redis:
            session_key = f"session:{user_id}"
            await self.redis_client.hset(session_key, mapping=clean_updates)
            # Sessions expire after 24 hours of inactivity
            await self.redis_client.expire(session_key, 86400)
        else:
            if user_id not in self._session_store:
                self._session_store[user_id] = {}
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
        if not self.pg_pool:
            return []

        # TODO: Implement with pgvector
        # For now, return empty - Phase 2b will add embeddings
        return []

    async def _store_longterm(
        self,
        user_id: str,
        content: str,
        category: Optional[str],
        metadata: dict,
    ):
        """Store in long-term memory with embedding."""
        if not self.pg_pool:
            return

        # TODO: Implement with pgvector
        # For now, no-op - Phase 2b will add embeddings
        pass

    async def _get_project_context(self, project_id: str) -> Optional[dict]:
        """Get project-specific context."""
        # TODO: Implement project context retrieval
        return None

    async def close(self):
        """Close all connections."""
        if self.redis_client:
            await self.redis_client.close()
        if self.pg_pool:
            await self.pg_pool.close()
        logger.info("[cortex] Connections closed")


# Singleton instance
cortex_manager = CortexManager()
