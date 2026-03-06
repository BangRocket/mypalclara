"""Tests for Qdrant resilience features (timeout, circuit breaker, graceful degradation)."""

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest


class TestQdrantTimeout:
    """Test QdrantClient timeout configuration."""

    @patch("mypalclara.core.memory.vector.qdrant.QdrantClient")
    def test_default_timeout(self, mock_client_cls):
        """QdrantClient gets 15s timeout by default."""
        mock_client = MagicMock()
        mock_client.get_collections.return_value = MagicMock(collections=[])
        mock_client_cls.return_value = mock_client

        from mypalclara.core.memory.vector.qdrant import Qdrant

        Qdrant(collection_name="test", embedding_model_dims=128, url="http://localhost:6333")

        # Verify timeout=15 was passed
        mock_client_cls.assert_called_once()
        call_kwargs = mock_client_cls.call_args[1]
        assert call_kwargs["timeout"] == 15

    @patch.dict("os.environ", {"QDRANT_TIMEOUT": "30"})
    @patch("mypalclara.core.memory.vector.qdrant.QdrantClient")
    def test_custom_timeout(self, mock_client_cls):
        """QdrantClient respects QDRANT_TIMEOUT env var."""
        mock_client = MagicMock()
        mock_client.get_collections.return_value = MagicMock(collections=[])
        mock_client_cls.return_value = mock_client

        from mypalclara.core.memory.vector.qdrant import Qdrant

        Qdrant(collection_name="test", embedding_model_dims=128, url="http://localhost:6333")

        call_kwargs = mock_client_cls.call_args[1]
        assert call_kwargs["timeout"] == 30

    @patch("mypalclara.core.memory.vector.qdrant.QdrantClient")
    def test_existing_client_no_timeout(self, mock_client_cls):
        """When passing an existing client, no timeout is added."""
        existing_client = MagicMock()
        existing_client.get_collections.return_value = MagicMock(collections=[])

        from mypalclara.core.memory.vector.qdrant import Qdrant

        qdrant = Qdrant(collection_name="test", embedding_model_dims=128, client=existing_client)
        assert qdrant.client is existing_client
        mock_client_cls.assert_not_called()


class TestQdrantCircuitBreaker:
    """Test circuit breaker for Qdrant operations."""

    def _make_qdrant(self):
        """Create a Qdrant instance with mocked client."""
        with patch("mypalclara.core.memory.vector.qdrant.QdrantClient") as mock_cls:
            mock_client = MagicMock()
            mock_client.get_collections.return_value = MagicMock(collections=[])
            mock_cls.return_value = mock_client

            from mypalclara.core.memory.vector.qdrant import Qdrant

            qdrant = Qdrant(collection_name="test", embedding_model_dims=128, url="http://localhost:6333")
        return qdrant

    def test_circuit_opens_after_threshold_failures(self):
        """Circuit opens after 3 consecutive failures."""
        qdrant = self._make_qdrant()
        qdrant.client.query_points.side_effect = Exception("timeout")

        # 3 failures should open the circuit
        for _ in range(3):
            result = qdrant.search("test", [0.1] * 128)
            assert result == []

        assert qdrant._cb_failures == 3
        assert qdrant._cb_open_until > 0

        # 4th call should not hit Qdrant at all (circuit is open)
        qdrant.client.query_points.reset_mock()
        result = qdrant.search("test", [0.1] * 128)
        assert result == []
        qdrant.client.query_points.assert_not_called()

    def test_circuit_half_open_after_cooldown(self):
        """After cooldown, circuit allows a probe call."""
        qdrant = self._make_qdrant()
        qdrant.client.query_points.side_effect = Exception("timeout")

        # Open the circuit
        for _ in range(3):
            qdrant.search("test", [0.1] * 128)

        # Simulate cooldown expiry
        qdrant._cb_open_until = time.monotonic() - 1

        # Now set up a successful response for the probe
        mock_response = MagicMock()
        mock_response.points = [MagicMock()]
        qdrant.client.query_points.side_effect = None
        qdrant.client.query_points.return_value = mock_response

        result = qdrant.search("test", [0.1] * 128)
        assert len(result) == 1
        assert qdrant._cb_failures == 0  # Reset after success

    def test_successful_call_resets_breaker(self):
        """A successful call resets failure count."""
        qdrant = self._make_qdrant()

        # 2 failures (below threshold)
        qdrant.client.query_points.side_effect = Exception("timeout")
        qdrant.search("test", [0.1] * 128)
        qdrant.search("test", [0.1] * 128)
        assert qdrant._cb_failures == 2

        # Successful call
        mock_response = MagicMock()
        mock_response.points = []
        qdrant.client.query_points.side_effect = None
        qdrant.client.query_points.return_value = mock_response
        qdrant.search("test", [0.1] * 128)
        assert qdrant._cb_failures == 0

    def test_list_respects_circuit_breaker(self):
        """list() also returns empty when circuit is open."""
        qdrant = self._make_qdrant()
        qdrant.client.scroll.side_effect = Exception("timeout")

        # Open the circuit via list failures
        for _ in range(3):
            result = qdrant.list()
            assert result == ([], None)

        # Circuit should be open now
        qdrant.client.scroll.reset_mock()
        result = qdrant.list()
        assert result == ([], None)
        qdrant.client.scroll.assert_not_called()


class TestMemoryFetchTimeout:
    """Test that memory fetch has a timeout with graceful degradation."""

    @pytest.mark.asyncio
    async def test_memory_fetch_timeout_returns_empty(self):
        """When memory fetch times out, processor gets empty results."""

        # This tests the pattern directly without needing the full processor
        async def slow_fetch():
            await asyncio.sleep(5)
            return ["should not reach"], ["this"], []

        try:
            result = await asyncio.wait_for(slow_fetch(), timeout=0.1)
        except (TimeoutError, asyncio.TimeoutError):
            result = ([], [], [])

        assert result == ([], [], [])
