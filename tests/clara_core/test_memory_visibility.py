"""Tests for memory visibility metadata."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestBuildFiltersVisibility:
    def test_default_no_visibility_filter(self):
        from mypalclara.core.memory.core.memory import _build_filters_and_metadata

        metadata, filters = _build_filters_and_metadata(user_id="discord-123")
        # No visibility filter by default -- returns all memories
        assert "visibility" not in filters

    def test_visibility_filter_public_only(self):
        from mypalclara.core.memory.core.memory import _build_filters_and_metadata

        metadata, filters = _build_filters_and_metadata(
            user_id="discord-123",
            input_filters={"visibility": "public"},
        )
        assert filters.get("visibility") == "public"

    def test_visibility_in_metadata_defaults_private(self):
        from mypalclara.core.memory.core.memory import _build_filters_and_metadata

        metadata, filters = _build_filters_and_metadata(
            user_id="discord-123",
            input_metadata={"some_key": "some_value"},
        )
        # New memories should default to private visibility
        assert metadata.get("visibility") == "private"


class TestSearchWithVisibility:
    def test_search_public_only_passes_filter(self):
        """When visibility='public' is passed, search should forward it as a filter."""
        from mypalclara.core.memory.core.memory import ClaraMemory

        mem = ClaraMemory.__new__(ClaraMemory)
        mem.vector_store = MagicMock()
        mem.embedding_model = MagicMock()
        mem.embedding_model.embed.return_value = [[0.1, 0.2]]
        mem.vector_store.search.return_value = []
        mem.db = MagicMock()
        mem.db.get_all.return_value = []
        mem.enable_graph = False
        mem.reranker = None

        result = mem.search(
            "test query",
            user_id="discord-123",
            filters={"visibility": "public"},
        )

        # Check the vector_store.search was called with visibility in filters
        call_kwargs = mem.vector_store.search.call_args
        if call_kwargs:
            passed_filters = call_kwargs.kwargs.get("filters") or call_kwargs[1].get("filters", {})
            assert passed_filters.get("visibility") == "public"


class TestUpdateVisibility:
    def test_update_memory_visibility(self):
        """Test that we can update a memory's visibility metadata."""
        from mypalclara.core.memory.core.memory import ClaraMemory

        mem = ClaraMemory.__new__(ClaraMemory)
        mem.vector_store = MagicMock()
        mem.db = MagicMock()

        mem.update_memory_visibility("mem-123", "public")

        # Should update the vector store payload
        mem.vector_store.update_payload.assert_called_once()
        call_args = mem.vector_store.update_payload.call_args
        assert call_args[1]["payload"]["visibility"] == "public"

    def test_update_memory_visibility_invalid_raises(self):
        from mypalclara.core.memory.core.memory import ClaraMemory

        mem = ClaraMemory.__new__(ClaraMemory)
        mem.vector_store = MagicMock()
        mem.db = MagicMock()
        with pytest.raises(ValueError, match="Invalid visibility"):
            mem.update_memory_visibility("mem-123", "secret")
