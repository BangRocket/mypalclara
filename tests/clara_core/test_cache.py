"""Tests for Clara Memory cache layer."""

from unittest.mock import MagicMock, patch

import pytest


class TestRedisCache:
    """Tests for RedisCache class."""

    def test_cache_unavailable_when_no_redis_url(self):
        """Cache should be unavailable when REDIS_URL is not set."""
        with patch.dict("os.environ", {}, clear=True):
            # Clear any existing singleton
            from clara_core.memory.cache.redis_cache import RedisCache

            RedisCache.reset()

            cache = RedisCache()
            assert cache.available is False

    def test_get_embedding_returns_none_when_unavailable(self):
        """get_embedding should return None when Redis unavailable."""
        with patch.dict("os.environ", {}, clear=True):
            from clara_core.memory.cache.redis_cache import RedisCache

            RedisCache.reset()

            cache = RedisCache()
            result = cache.get_embedding("test text", "text-embedding-3-small")
            assert result is None

    def test_set_embedding_returns_false_when_unavailable(self):
        """set_embedding should return False when Redis unavailable."""
        with patch.dict("os.environ", {}, clear=True):
            from clara_core.memory.cache.redis_cache import RedisCache

            RedisCache.reset()

            cache = RedisCache()
            result = cache.set_embedding("test", "model", [0.1, 0.2, 0.3])
            assert result is False

    def test_get_search_results_returns_none_when_unavailable(self):
        """get_search_results should return None when Redis unavailable."""
        with patch.dict("os.environ", {}, clear=True):
            from clara_core.memory.cache.redis_cache import RedisCache

            RedisCache.reset()

            cache = RedisCache()
            result = cache.get_search_results("user-123", "query", "user")
            assert result is None

    def test_set_search_results_returns_false_when_unavailable(self):
        """set_search_results should return False when Redis unavailable."""
        with patch.dict("os.environ", {}, clear=True):
            from clara_core.memory.cache.redis_cache import RedisCache

            RedisCache.reset()

            cache = RedisCache()
            result = cache.set_search_results("user-123", "query", [{"memory": "test"}])
            assert result is False

    def test_get_key_memories_returns_none_when_unavailable(self):
        """get_key_memories should return None when Redis unavailable."""
        with patch.dict("os.environ", {}, clear=True):
            from clara_core.memory.cache.redis_cache import RedisCache

            RedisCache.reset()

            cache = RedisCache()
            result = cache.get_key_memories("user-123", "clara")
            assert result is None

    def test_invalidate_returns_zero_when_unavailable(self):
        """invalidate_user_cache should return 0 when Redis unavailable."""
        with patch.dict("os.environ", {}, clear=True):
            from clara_core.memory.cache.redis_cache import RedisCache

            RedisCache.reset()

            cache = RedisCache()
            result = cache.invalidate_user_cache("user-123")
            assert result == 0

    def test_singleton_pattern(self):
        """get_instance should return the same instance."""
        with patch.dict("os.environ", {}, clear=True):
            from clara_core.memory.cache.redis_cache import RedisCache

            RedisCache.reset()

            instance1 = RedisCache.get_instance()
            instance2 = RedisCache.get_instance()
            assert instance1 is instance2

    def test_embedding_key_generation(self):
        """Embedding key should be deterministic and unique."""
        with patch.dict("os.environ", {}, clear=True):
            from clara_core.memory.cache.redis_cache import RedisCache

            RedisCache.reset()

            cache = RedisCache()
            key1 = cache._embedding_key("hello world", "model-1")
            key2 = cache._embedding_key("hello world", "model-1")
            key3 = cache._embedding_key("hello world", "model-2")
            key4 = cache._embedding_key("different text", "model-1")

            # Same inputs should produce same key
            assert key1 == key2
            # Different model should produce different key
            assert key1 != key3
            # Different text should produce different key
            assert key1 != key4

    def test_search_key_generation(self):
        """Search key should include user_id, query hash, and type."""
        with patch.dict("os.environ", {}, clear=True):
            from clara_core.memory.cache.redis_cache import RedisCache

            RedisCache.reset()

            cache = RedisCache()
            hash1 = cache._hash_query("query", None)
            hash2 = cache._hash_query("query", {"filter": "value"})
            hash3 = cache._hash_query("different", None)

            # Same query, no filters
            assert hash1 == cache._hash_query("query", None)
            # Filters should change hash
            assert hash1 != hash2
            # Different query
            assert hash1 != hash3

    def test_stats_when_unavailable(self):
        """get_stats should return available=False when Redis unavailable."""
        with patch.dict("os.environ", {}, clear=True):
            from clara_core.memory.cache.redis_cache import RedisCache

            RedisCache.reset()

            cache = RedisCache()
            stats = cache.get_stats()
            assert stats["available"] is False


class TestRedisCacheWithMock:
    """Tests for RedisCache with mocked Redis client."""

    def test_get_embedding_cache_hit(self):
        """get_embedding should return cached value on hit."""
        from clara_core.memory.cache.redis_cache import RedisCache

        RedisCache.reset()

        mock_client = MagicMock()
        mock_client.get.return_value = "[0.1, 0.2, 0.3]"
        mock_client.ping.return_value = True

        cache = RedisCache(client=mock_client)
        cache._initialized = True

        result = cache.get_embedding("test", "model")
        assert result == [0.1, 0.2, 0.3]

    def test_get_embedding_cache_miss(self):
        """get_embedding should return None on miss."""
        from clara_core.memory.cache.redis_cache import RedisCache

        RedisCache.reset()

        mock_client = MagicMock()
        mock_client.get.return_value = None
        mock_client.ping.return_value = True

        cache = RedisCache(client=mock_client)
        cache._initialized = True

        result = cache.get_embedding("test", "model")
        assert result is None

    def test_set_embedding_success(self):
        """set_embedding should call setex with correct TTL."""
        from clara_core.memory.cache.redis_cache import EMBEDDING_TTL, RedisCache

        RedisCache.reset()

        mock_client = MagicMock()
        mock_client.ping.return_value = True

        cache = RedisCache(client=mock_client)
        cache._initialized = True

        result = cache.set_embedding("test", "model", [0.1, 0.2])
        assert result is True
        mock_client.setex.assert_called_once()

        # Check TTL argument
        call_args = mock_client.setex.call_args
        assert call_args[0][1] == EMBEDDING_TTL

    def test_get_search_results_cache_hit(self):
        """get_search_results should return cached results on hit."""
        from clara_core.memory.cache.redis_cache import RedisCache

        RedisCache.reset()

        mock_client = MagicMock()
        mock_client.get.return_value = '[{"memory": "test", "id": "123"}]'
        mock_client.ping.return_value = True

        cache = RedisCache(client=mock_client)
        cache._initialized = True

        result = cache.get_search_results("user-123", "query", "user")
        assert result == [{"memory": "test", "id": "123"}]

    def test_set_search_results_with_filters(self):
        """set_search_results should handle filters in cache key."""
        from clara_core.memory.cache.redis_cache import RedisCache

        RedisCache.reset()

        mock_client = MagicMock()
        mock_client.ping.return_value = True

        cache = RedisCache(client=mock_client)
        cache._initialized = True

        result = cache.set_search_results(
            "user-123",
            "query",
            [{"memory": "test"}],
            filters={"project_id": "proj-1"},
        )
        assert result is True

    def test_invalidate_user_cache_deletes_keys(self):
        """invalidate_user_cache should delete matching keys."""
        from clara_core.memory.cache.redis_cache import RedisCache

        RedisCache.reset()

        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.scan_iter.return_value = iter(["key1", "key2"])
        mock_client.delete.return_value = 2

        cache = RedisCache(client=mock_client)
        cache._initialized = True

        result = cache.invalidate_user_cache("user-123")
        assert result >= 2  # At least 2 keys deleted

    def test_invalidate_search_cache_only(self):
        """invalidate_search_cache should only delete search keys."""
        from clara_core.memory.cache.redis_cache import RedisCache

        RedisCache.reset()

        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.scan_iter.return_value = iter(["clara:search:user-123:user:abc"])
        mock_client.delete.return_value = 1

        cache = RedisCache(client=mock_client)
        cache._initialized = True

        result = cache.invalidate_search_cache("user-123")
        assert result == 1

        # Verify only search pattern was used
        mock_client.scan_iter.assert_called_once()
        call_args = mock_client.scan_iter.call_args
        assert "search" in call_args[1]["match"]


class TestCachedEmbedding:
    """Tests for CachedEmbedding wrapper."""

    def test_cache_disabled_calls_embedder_directly(self):
        """When cache disabled, should call embedder directly."""
        from clara_core.memory.embeddings.cached import CachedEmbedding

        mock_embedder = MagicMock()
        mock_embedder.embed.return_value = [0.1, 0.2, 0.3]

        with patch.dict("os.environ", {"MEMORY_EMBEDDING_CACHE": "false"}):
            cached = CachedEmbedding(mock_embedder, enabled=False)
            result = cached.embed("test text")

        assert result == [0.1, 0.2, 0.3]
        mock_embedder.embed.assert_called_once_with("test text", None)

    def test_cache_hit_returns_cached(self):
        """On cache hit, should return cached value without calling embedder."""
        from clara_core.memory.cache.redis_cache import RedisCache
        from clara_core.memory.embeddings.cached import CachedEmbedding

        mock_embedder = MagicMock()
        mock_embedder.config.model = "test-model"

        mock_cache = MagicMock(spec=RedisCache)
        mock_cache.available = True
        mock_cache.get_embedding.return_value = [0.1, 0.2, 0.3]

        cached = CachedEmbedding(mock_embedder, cache=mock_cache, enabled=True)
        result = cached.embed("test text")

        assert result == [0.1, 0.2, 0.3]
        mock_embedder.embed.assert_not_called()

    def test_cache_miss_calls_embedder_and_caches(self):
        """On cache miss, should call embedder and cache result."""
        from clara_core.memory.cache.redis_cache import RedisCache
        from clara_core.memory.embeddings.cached import CachedEmbedding

        mock_embedder = MagicMock()
        mock_embedder.config.model = "test-model"
        mock_embedder.embed.return_value = [0.4, 0.5, 0.6]

        mock_cache = MagicMock(spec=RedisCache)
        mock_cache.available = True
        mock_cache.get_embedding.return_value = None  # Cache miss

        cached = CachedEmbedding(mock_embedder, cache=mock_cache, enabled=True)
        result = cached.embed("test text")

        assert result == [0.4, 0.5, 0.6]
        mock_embedder.embed.assert_called_once()
        mock_cache.set_embedding.assert_called_once()

    def test_stats_tracking(self):
        """Stats should track hits and misses."""
        from clara_core.memory.cache.redis_cache import RedisCache
        from clara_core.memory.embeddings.cached import CachedEmbedding

        mock_embedder = MagicMock()
        mock_embedder.config.model = "test-model"
        mock_embedder.embed.return_value = [0.1, 0.2]

        mock_cache = MagicMock(spec=RedisCache)
        mock_cache.available = True

        cached = CachedEmbedding(mock_embedder, cache=mock_cache, enabled=True)

        # First call - cache miss
        mock_cache.get_embedding.return_value = None
        cached.embed("text1")

        # Second call - cache hit
        mock_cache.get_embedding.return_value = [0.1, 0.2]
        cached.embed("text2")

        stats = cached.get_stats()
        assert stats["misses"] == 1
        assert stats["hits"] == 1
        assert stats["hit_rate"] == 0.5

    def test_config_delegation(self):
        """config property should delegate to wrapped embedder."""
        from clara_core.memory.embeddings.cached import CachedEmbedding

        mock_embedder = MagicMock()
        mock_embedder.config = {"model": "test-model"}

        cached = CachedEmbedding(mock_embedder, enabled=False)
        assert cached.config == {"model": "test-model"}
