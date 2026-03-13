"""Tests for branch-scoped memory operations.

All tests mock ROOK so no running Qdrant/pgvector instance is needed.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from mypalclara.core.memory.branch_memory import (
    add_memory_for_branch,
    discard_branch_memories,
    promote_branch_memories,
    search_memory_for_branch,
)


@pytest.fixture()
def mock_rook():
    """Return a MagicMock standing in for the ROOK singleton."""
    rook = MagicMock()
    # Default return values
    rook.add.return_value = {"results": []}
    rook.search.return_value = {"results": []}
    rook.get_all.return_value = {"results": []}
    rook.delete.return_value = {"message": "Memory deleted successfully!"}
    return rook


# ---------------------------------------------------------------------------
# add_memory_for_branch
# ---------------------------------------------------------------------------


class TestAddMemoryForBranch:
    def test_with_branch_id_passes_metadata(self, mock_rook):
        """When branch_id is provided, it should appear in metadata."""
        with patch("mypalclara.core.memory.ROOK", mock_rook):
            add_memory_for_branch("hello", user_id="u1", branch_id="br-1")

        mock_rook.add.assert_called_once()
        call_kwargs = mock_rook.add.call_args
        assert call_kwargs.kwargs["metadata"]["branch_id"] == "br-1"
        assert call_kwargs.kwargs["user_id"] == "u1"
        assert call_kwargs.kwargs["messages"] == "hello"

    def test_without_branch_id_no_branch_in_metadata(self, mock_rook):
        """When branch_id is None, metadata should not contain branch_id."""
        with patch("mypalclara.core.memory.ROOK", mock_rook):
            add_memory_for_branch("hello", user_id="u1")

        call_kwargs = mock_rook.add.call_args
        assert "branch_id" not in call_kwargs.kwargs["metadata"]

    def test_preserves_existing_metadata(self, mock_rook):
        """Caller-supplied metadata keys are preserved alongside branch_id."""
        with patch("mypalclara.core.memory.ROOK", mock_rook):
            add_memory_for_branch("hello", user_id="u1", branch_id="br-1", metadata={"extra": "val"})

        call_kwargs = mock_rook.add.call_args
        assert call_kwargs.kwargs["metadata"]["extra"] == "val"
        assert call_kwargs.kwargs["metadata"]["branch_id"] == "br-1"

    def test_forwards_extra_kwargs(self, mock_rook):
        """Extra kwargs (like agent_id) are forwarded to ROOK.add."""
        with patch("mypalclara.core.memory.ROOK", mock_rook):
            add_memory_for_branch("hello", user_id="u1", agent_id="clara")

        call_kwargs = mock_rook.add.call_args
        assert call_kwargs.kwargs["agent_id"] == "clara"

    def test_returns_none_when_rook_unavailable(self):
        """Returns None when ROOK is not initialized."""
        with patch("mypalclara.core.memory.ROOK", None):
            result = add_memory_for_branch("hello", user_id="u1")

        assert result is None


# ---------------------------------------------------------------------------
# search_memory_for_branch
# ---------------------------------------------------------------------------


class TestSearchMemoryForBranch:
    def test_with_branch_id_filters_results(self, mock_rook):
        """With branch_id, results from other branches are excluded."""
        mock_rook.search.return_value = {
            "results": [
                {"id": "m1", "memory": "global fact", "metadata": None},
                {"id": "m2", "memory": "branch fact", "metadata": {"branch_id": "br-1"}},
                {"id": "m3", "memory": "other branch", "metadata": {"branch_id": "br-other"}},
            ]
        }
        with patch("mypalclara.core.memory.ROOK", mock_rook):
            result = search_memory_for_branch("query", user_id="u1", branch_id="br-1")

        # Only global (m1) and matching branch (m2) should remain
        assert len(result["results"]) == 2
        ids = {r["id"] for r in result["results"]}
        assert ids == {"m1", "m2"}

    def test_without_branch_id_returns_all(self, mock_rook):
        """Without branch_id, no post-filtering is applied."""
        mock_rook.search.return_value = {
            "results": [
                {"id": "m1", "memory": "fact1"},
                {"id": "m2", "memory": "fact2"},
            ]
        }
        with patch("mypalclara.core.memory.ROOK", mock_rook):
            result = search_memory_for_branch("query", user_id="u1")

        assert len(result["results"]) == 2

    def test_search_calls_rook_with_correct_args(self, mock_rook):
        """Verifies the ROOK.search call uses the right parameters."""
        with patch("mypalclara.core.memory.ROOK", mock_rook):
            search_memory_for_branch("what color?", user_id="u1", limit=10)

        mock_rook.search.assert_called_once_with(query="what color?", user_id="u1", limit=10)

    def test_handles_empty_results(self, mock_rook):
        """Empty result set is handled gracefully."""
        mock_rook.search.return_value = {"results": []}
        with patch("mypalclara.core.memory.ROOK", mock_rook):
            result = search_memory_for_branch("query", user_id="u1", branch_id="br-1")

        assert result == {"results": []}

    def test_returns_empty_when_rook_unavailable(self):
        """Returns empty results when ROOK is not initialized."""
        with patch("mypalclara.core.memory.ROOK", None):
            result = search_memory_for_branch("query", user_id="u1")

        assert result == {"results": []}

    def test_global_memories_without_metadata_key_are_kept(self, mock_rook):
        """Memories that lack a metadata dict entirely are treated as global."""
        mock_rook.search.return_value = {
            "results": [
                {"id": "m1", "memory": "old memory"},  # no metadata key at all
                {"id": "m2", "memory": "branch", "metadata": {"branch_id": "br-1"}},
            ]
        }
        with patch("mypalclara.core.memory.ROOK", mock_rook):
            result = search_memory_for_branch("query", user_id="u1", branch_id="br-1")

        assert len(result["results"]) == 2


# ---------------------------------------------------------------------------
# promote_branch_memories
# ---------------------------------------------------------------------------


class TestPromoteBranchMemories:
    def test_promotes_each_memory(self, mock_rook):
        """Searches for branch memories and updates each to remove branch_id."""
        mock_rook.get_all.return_value = {
            "results": [
                {"id": "mem-1", "memory": "fact A", "metadata": {"branch_id": "br-1"}},
                {"id": "mem-2", "memory": "fact B", "metadata": {"branch_id": "br-1"}},
            ]
        }

        # Mock vector_store.get to return payload objects
        def make_record(mem_id):
            return SimpleNamespace(
                id=mem_id,
                payload={"data": "some fact", "user_id": "u1", "branch_id": "br-1"},
            )

        mock_rook.vector_store.get.side_effect = lambda vector_id: make_record(vector_id)

        with patch("mypalclara.core.memory.ROOK", mock_rook):
            count = promote_branch_memories(user_id="u1", branch_id="br-1")

        assert count == 2
        mock_rook.get_all.assert_called_once_with(user_id="u1", filters={"branch_id": "br-1"})

        # Each memory's payload should be updated without branch_id
        # Uses set_payload (not update) to avoid destroying the stored embedding
        assert mock_rook.vector_store.set_payload.call_count == 2
        for call in mock_rook.vector_store.set_payload.call_args_list:
            payload = call.kwargs["payload"]
            assert "branch_id" not in payload
            # Original fields preserved
            assert payload["data"] == "some fact"
            assert payload["user_id"] == "u1"

    def test_returns_zero_when_no_memories(self, mock_rook):
        """Returns 0 when no branch-scoped memories exist."""
        mock_rook.get_all.return_value = {"results": []}

        with patch("mypalclara.core.memory.ROOK", mock_rook):
            count = promote_branch_memories(user_id="u1", branch_id="br-1")

        assert count == 0
        mock_rook.vector_store.set_payload.assert_not_called()

    def test_returns_zero_when_rook_unavailable(self):
        """Returns 0 when ROOK is not initialized."""
        with patch("mypalclara.core.memory.ROOK", None):
            count = promote_branch_memories(user_id="u1", branch_id="br-1")

        assert count == 0


# ---------------------------------------------------------------------------
# discard_branch_memories
# ---------------------------------------------------------------------------


class TestDiscardBranchMemories:
    def test_deletes_each_memory(self, mock_rook):
        """Searches for branch memories and deletes each one."""
        mock_rook.get_all.return_value = {
            "results": [
                {"id": "mem-1", "memory": "fact A"},
                {"id": "mem-2", "memory": "fact B"},
                {"id": "mem-3", "memory": "fact C"},
            ]
        }

        with patch("mypalclara.core.memory.ROOK", mock_rook):
            count = discard_branch_memories(user_id="u1", branch_id="br-1")

        assert count == 3
        mock_rook.get_all.assert_called_once_with(user_id="u1", filters={"branch_id": "br-1"})
        assert mock_rook.delete.call_count == 3

        deleted_ids = {call.args[0] for call in mock_rook.delete.call_args_list}
        assert deleted_ids == {"mem-1", "mem-2", "mem-3"}

    def test_returns_zero_when_no_memories(self, mock_rook):
        """Returns 0 when no branch-scoped memories exist."""
        mock_rook.get_all.return_value = {"results": []}

        with patch("mypalclara.core.memory.ROOK", mock_rook):
            count = discard_branch_memories(user_id="u1", branch_id="br-1")

        assert count == 0
        mock_rook.delete.assert_not_called()

    def test_returns_zero_when_rook_unavailable(self):
        """Returns 0 when ROOK is not initialized."""
        with patch("mypalclara.core.memory.ROOK", None):
            count = discard_branch_memories(user_id="u1", branch_id="br-1")

        assert count == 0
