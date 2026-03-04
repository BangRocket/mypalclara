"""Tests for privacy-filtered memory fetching.

When privacy_scope='public_only' (group channels), the memory retriever should
add a visibility='public' filter so that private memories are excluded.
When privacy_scope='full' (DMs), no visibility filter is applied.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestFetchWithPrivacyScope:
    """Test that privacy_scope flows from MemoryManager to MemoryRetriever."""

    def _make_memory_manager(self):
        """Create a MemoryManager with a mocked _memory_retriever."""
        from mypalclara.core.memory_manager import MemoryManager

        mm = MemoryManager.__new__(MemoryManager)
        mm._memory_retriever = MagicMock()
        mm._memory_retriever.fetch_mem0_context.return_value = (["mem1"], [], [])
        return mm

    def test_full_scope_no_visibility_filter(self):
        """In DMs (privacy_scope='full'), all memories are returned without visibility filter."""
        mm = self._make_memory_manager()

        user_mems, _, _ = mm.fetch_mem0_context("discord-123", "proj-1", "hello", privacy_scope="full")

        # Should delegate to retriever with privacy_scope="full"
        mm._memory_retriever.fetch_mem0_context.assert_called_once()
        call_kwargs = mm._memory_retriever.fetch_mem0_context.call_args
        assert call_kwargs.kwargs.get("privacy_scope") == "full"

    def test_public_only_scope_passed_through(self):
        """In group channels (privacy_scope='public_only'), scope is passed to retriever."""
        mm = self._make_memory_manager()

        mm.fetch_mem0_context("discord-123", "proj-1", "hello", privacy_scope="public_only")

        call_kwargs = mm._memory_retriever.fetch_mem0_context.call_args
        assert call_kwargs.kwargs.get("privacy_scope") == "public_only"

    def test_default_privacy_scope_is_full(self):
        """When privacy_scope is not specified, it defaults to 'full'."""
        mm = self._make_memory_manager()

        mm.fetch_mem0_context("discord-123", "proj-1", "hello")

        call_kwargs = mm._memory_retriever.fetch_mem0_context.call_args
        assert call_kwargs.kwargs.get("privacy_scope") == "full"


class TestRetrieverVisibilityFilter:
    """Test that the MemoryRetriever applies visibility filters to ROOK calls."""

    def _make_retriever(self):
        """Create a MemoryRetriever with mocked dependencies."""
        from mypalclara.core.memory_retriever import MemoryRetriever

        retriever = MemoryRetriever.__new__(MemoryRetriever)
        retriever.agent_id = "clara"
        retriever._on_memory_event = None
        retriever._dynamics_manager = MagicMock()
        retriever._dynamics_manager.rank_results_with_fsrs_batch.return_value = []
        return retriever

    @patch("mypalclara.core.memory.ROOK")
    def test_public_only_adds_visibility_filter_to_search(self, mock_rook):
        """When privacy_scope='public_only', ROOK.search gets visibility='public' filter."""
        mock_rook.search.return_value = {"results": []}
        mock_rook.get_all.return_value = {"results": []}

        retriever = self._make_retriever()

        retriever.fetch_mem0_context("discord-123", "proj-1", "hello", privacy_scope="public_only")

        # Check that ROOK.search calls included visibility filter
        for call in mock_rook.search.call_args_list:
            filters = call.kwargs.get("filters") or {}
            assert (
                filters.get("visibility") == "public"
            ), f"Expected visibility='public' in search filters, got: {filters}"

        # Check that get_all also included visibility filter
        for call in mock_rook.get_all.call_args_list:
            filters = call.kwargs.get("filters") or {}
            assert (
                filters.get("visibility") == "public"
            ), f"Expected visibility='public' in get_all filters, got: {filters}"

    @patch("mypalclara.core.memory.ROOK")
    def test_full_scope_no_visibility_filter_on_search(self, mock_rook):
        """When privacy_scope='full', ROOK.search does NOT get visibility filter."""
        mock_rook.search.return_value = {"results": []}
        mock_rook.get_all.return_value = {"results": []}

        retriever = self._make_retriever()

        retriever.fetch_mem0_context("discord-123", "proj-1", "hello", privacy_scope="full")

        # Check that ROOK.search calls do NOT include visibility filter
        for call in mock_rook.search.call_args_list:
            filters = call.kwargs.get("filters") or {}
            assert "visibility" not in filters, f"Expected no visibility filter in search, got: {filters}"

        # Check that get_all calls do NOT include visibility filter
        for call in mock_rook.get_all.call_args_list:
            filters = call.kwargs.get("filters") or {}
            assert "visibility" not in filters, f"Expected no visibility filter in get_all, got: {filters}"
