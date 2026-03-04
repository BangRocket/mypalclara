"""Tests for per-user workspace loading from VM.

Per-user workspace files (USER.md, MEMORY.md, etc.) are loaded from the VM
into PromptBuilder._user_workspace_cache. In DMs (privacy_scope="full"),
these files are included in the prompt. In group channels
(privacy_scope="public_only"), they are excluded.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mypalclara.core.llm.messages import SystemMessage, UserMessage
from mypalclara.core.prompt_builder import PromptBuilder

_MOCK_PERSONA = "You are Clara."
_WORKSPACE_PATCH = patch.object(
    PromptBuilder, "_load_workspace_persona", return_value=_MOCK_PERSONA
)


def _make_prompt_builder() -> PromptBuilder:
    """Create a PromptBuilder with per-user workspace cache pre-populated."""
    pb = PromptBuilder(agent_id="test-agent")
    pb._user_workspace_cache = {
        "discord-123": {
            "USER.md": "Name: Alice\nTimezone: EST",
            "MEMORY.md": "Likes cats",
        },
    }
    return pb


class TestPerUserWorkspaceFull:
    """In DMs (privacy_scope='full'), per-user workspace content is included."""

    @_WORKSPACE_PATCH
    def test_full_scope_includes_user_workspace(self, _mock):
        pb = _make_prompt_builder()
        messages = pb.build_prompt(
            user_mems=[],
            proj_mems=[],
            thread_summary=None,
            recent_msgs=[],
            user_message="hello",
            privacy_scope="full",
            user_id="discord-123",
        )
        all_content = " ".join(m.content for m in messages)
        assert "Name: Alice" in all_content
        assert "Timezone: EST" in all_content

    @_WORKSPACE_PATCH
    def test_full_scope_includes_all_cached_files(self, _mock):
        pb = _make_prompt_builder()
        messages = pb.build_prompt(
            user_mems=[],
            proj_mems=[],
            thread_summary=None,
            recent_msgs=[],
            user_message="hello",
            privacy_scope="full",
            user_id="discord-123",
        )
        all_content = " ".join(m.content for m in messages)
        assert "Likes cats" in all_content

    @_WORKSPACE_PATCH
    def test_full_scope_labels_section(self, _mock):
        """The user workspace section should have a clear label."""
        pb = _make_prompt_builder()
        messages = pb.build_prompt(
            user_mems=[],
            proj_mems=[],
            thread_summary=None,
            recent_msgs=[],
            user_message="hello",
            privacy_scope="full",
            user_id="discord-123",
        )
        all_content = " ".join(m.content for m in messages)
        assert "USER WORKSPACE" in all_content


class TestPerUserWorkspacePublicOnly:
    """In group channels (privacy_scope='public_only'), per-user workspace is excluded."""

    @_WORKSPACE_PATCH
    def test_public_only_excludes_user_workspace(self, _mock):
        pb = _make_prompt_builder()
        messages = pb.build_prompt(
            user_mems=[],
            proj_mems=[],
            thread_summary=None,
            recent_msgs=[],
            user_message="hello",
            privacy_scope="public_only",
            user_id="discord-123",
        )
        all_content = " ".join(m.content for m in messages)
        assert "Name: Alice" not in all_content
        assert "Likes cats" not in all_content

    @_WORKSPACE_PATCH
    def test_public_only_no_workspace_section(self, _mock):
        pb = _make_prompt_builder()
        messages = pb.build_prompt(
            user_mems=[],
            proj_mems=[],
            thread_summary=None,
            recent_msgs=[],
            user_message="hello",
            privacy_scope="public_only",
            user_id="discord-123",
        )
        all_content = " ".join(m.content for m in messages)
        assert "USER WORKSPACE" not in all_content


class TestPerUserWorkspaceDefaults:
    """Default behavior when privacy_scope/user_id are not provided."""

    @_WORKSPACE_PATCH
    def test_default_scope_is_full(self, _mock):
        """When no privacy_scope is provided, default to 'full' (backward compat)."""
        pb = _make_prompt_builder()
        messages = pb.build_prompt(
            user_mems=[],
            proj_mems=[],
            thread_summary=None,
            recent_msgs=[],
            user_message="hello",
            user_id="discord-123",
        )
        all_content = " ".join(m.content for m in messages)
        # Default scope is "full", so user workspace should be included
        assert "Name: Alice" in all_content

    @_WORKSPACE_PATCH
    def test_no_user_id_no_workspace(self, _mock):
        """When user_id is None, no user workspace is included."""
        pb = _make_prompt_builder()
        messages = pb.build_prompt(
            user_mems=[],
            proj_mems=[],
            thread_summary=None,
            recent_msgs=[],
            user_message="hello",
            privacy_scope="full",
            user_id=None,
        )
        all_content = " ".join(m.content for m in messages)
        assert "Name: Alice" not in all_content

    @_WORKSPACE_PATCH
    def test_unknown_user_id_no_workspace(self, _mock):
        """When user_id is not in cache, no user workspace is included."""
        pb = _make_prompt_builder()
        messages = pb.build_prompt(
            user_mems=[],
            proj_mems=[],
            thread_summary=None,
            recent_msgs=[],
            user_message="hello",
            privacy_scope="full",
            user_id="discord-999",
        )
        all_content = " ".join(m.content for m in messages)
        assert "Name: Alice" not in all_content

    @_WORKSPACE_PATCH
    def test_empty_cache_no_workspace(self, _mock):
        """When _user_workspace_cache is empty, no workspace section appears."""
        pb = PromptBuilder(agent_id="test-agent")
        pb._user_workspace_cache = {}
        messages = pb.build_prompt(
            user_mems=[],
            proj_mems=[],
            thread_summary=None,
            recent_msgs=[],
            user_message="hello",
            privacy_scope="full",
            user_id="discord-123",
        )
        all_content = " ".join(m.content for m in messages)
        assert "USER WORKSPACE" not in all_content


class TestLoadUserWorkspace:
    """Test the async load_user_workspace method."""

    @pytest.mark.asyncio
    async def test_load_user_workspace_populates_cache(self):
        pb = PromptBuilder(agent_id="test-agent")

        vm_manager = AsyncMock()
        vm_manager.read_workspace_files.return_value = {
            "USER.md": "Name: Bob\nTimezone: PST",
        }

        await pb.load_user_workspace("discord-456", vm_manager)
        assert "discord-456" in pb._user_workspace_cache
        assert pb._user_workspace_cache["discord-456"]["USER.md"] == "Name: Bob\nTimezone: PST"

    @pytest.mark.asyncio
    async def test_load_user_workspace_replaces_existing(self):
        pb = PromptBuilder(agent_id="test-agent")
        pb._user_workspace_cache["discord-456"] = {"USER.md": "old content"}

        vm_manager = AsyncMock()
        vm_manager.read_workspace_files.return_value = {
            "USER.md": "Name: Bob (updated)",
        }

        await pb.load_user_workspace("discord-456", vm_manager)
        assert pb._user_workspace_cache["discord-456"]["USER.md"] == "Name: Bob (updated)"
