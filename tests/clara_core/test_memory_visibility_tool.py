"""Tests for memory visibility tools."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mypalclara.tools._base import ToolContext

CTX = ToolContext(user_id="discord-123")


class TestSetVisibility:
    @pytest.mark.asyncio
    async def test_set_visibility_public(self):
        from mypalclara.core.core_tools.memory_visibility_tool import _handle_set_visibility

        with patch("mypalclara.core.core_tools.memory_visibility_tool._get_memory") as mock_mem:
            mock_mem.return_value = MagicMock()
            result = await _handle_set_visibility({"memory_id": "mem-123", "visibility": "public"}, CTX)
            assert "public" in result.lower()
            mock_mem.return_value.update_memory_visibility.assert_called_once_with("mem-123", "public")

    @pytest.mark.asyncio
    async def test_set_visibility_invalid(self):
        from mypalclara.core.core_tools.memory_visibility_tool import _handle_set_visibility

        result = await _handle_set_visibility({"memory_id": "mem-123", "visibility": "secret"}, CTX)
        assert "error" in result.lower()

    @pytest.mark.asyncio
    async def test_set_visibility_private(self):
        from mypalclara.core.core_tools.memory_visibility_tool import _handle_set_visibility

        with patch("mypalclara.core.core_tools.memory_visibility_tool._get_memory") as mock_mem:
            mock_mem.return_value = MagicMock()
            result = await _handle_set_visibility({"memory_id": "mem-123", "visibility": "private"}, CTX)
            assert "private" in result.lower()


class TestListPublic:
    @pytest.mark.asyncio
    async def test_list_public_memories(self):
        from mypalclara.core.core_tools.memory_visibility_tool import _handle_list_public

        mock_result = {
            "results": [
                MagicMock(memory="Likes Python", id="m1"),
                MagicMock(memory="Works at Acme", id="m2"),
            ]
        }
        with patch("mypalclara.core.core_tools.memory_visibility_tool._get_memory") as mock_mem:
            mock_mem.return_value = MagicMock()
            mock_mem.return_value.search.return_value = mock_result
            result = await _handle_list_public({}, CTX)
            assert "Likes Python" in result
            assert "Works at Acme" in result

    @pytest.mark.asyncio
    async def test_list_public_empty(self):
        from mypalclara.core.core_tools.memory_visibility_tool import _handle_list_public

        with patch("mypalclara.core.core_tools.memory_visibility_tool._get_memory") as mock_mem:
            mock_mem.return_value = MagicMock()
            mock_mem.return_value.search.return_value = {"results": []}
            result = await _handle_list_public({}, CTX)
            assert "no public" in result.lower()
