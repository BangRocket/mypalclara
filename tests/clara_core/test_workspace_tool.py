"""Tests for workspace file tools."""

from __future__ import annotations

import pytest

from mypalclara.core.core_tools.workspace_tool import (
    READONLY_FILES,
    WORKSPACE_DIR,
    _handle_workspace_create,
    _handle_workspace_list,
    _handle_workspace_read,
    _handle_workspace_write,
    _sanitize_filename,
)
from mypalclara.tools._base import ToolContext

CTX = ToolContext(user_id="test-user")


class TestSanitizeFilename:
    def test_simple_name(self):
        assert _sanitize_filename("MEMORY.md") == "MEMORY.md"

    def test_path_traversal_blocked(self):
        assert _sanitize_filename("../etc/passwd") is None

    def test_absolute_path_stripped(self):
        assert _sanitize_filename("/etc/passwd") is None

    def test_subdirectory_blocked(self):
        assert _sanitize_filename("sub/file.md") is None

    def test_empty_string(self):
        assert _sanitize_filename("") is None

    def test_dotdot_in_name(self):
        assert _sanitize_filename("..") is None


class TestWorkspaceList:
    @pytest.mark.asyncio
    async def test_lists_existing_files(self):
        result = await _handle_workspace_list({}, CTX)
        assert "SOUL.md" in result
        assert "HEARTBEAT.md" in result
        assert "read-only" in result  # SOUL.md should be marked

    @pytest.mark.asyncio
    async def test_shows_readonly_marker(self):
        result = await _handle_workspace_list({}, CTX)
        # SOUL.md and IDENTITY.md should be marked read-only
        lines = result.split("\n")
        soul_line = [l for l in lines if "SOUL.md" in l][0]
        assert "read-only" in soul_line


class TestWorkspaceRead:
    @pytest.mark.asyncio
    async def test_read_existing_file(self):
        result = await _handle_workspace_read({"filename": "SOUL.md"}, CTX)
        assert "SOUL.md" in result
        assert "Clara" in result  # SOUL.md mentions Clara

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self):
        result = await _handle_workspace_read({"filename": "NONEXISTENT.md"}, CTX)
        assert "Error" in result
        assert "not found" in result

    @pytest.mark.asyncio
    async def test_read_path_traversal_blocked(self):
        result = await _handle_workspace_read({"filename": "../pyproject.toml"}, CTX)
        assert "Error" in result
        assert "Invalid" in result


class TestWorkspaceWrite:
    @pytest.mark.asyncio
    async def test_write_readonly_blocked(self):
        for name in READONLY_FILES:
            result = await _handle_workspace_write({"filename": name, "content": "hacked"}, CTX)
            assert "read-only" in result
            assert "Error" in result

    @pytest.mark.asyncio
    async def test_write_nonexistent_file(self):
        result = await _handle_workspace_write({"filename": "DOES_NOT_EXIST.md", "content": "test"}, CTX)
        assert "Error" in result
        assert "not found" in result

    @pytest.mark.asyncio
    async def test_overwrite_editable_file(self, tmp_path, monkeypatch):
        # Create a temp workspace dir with a test file
        import mypalclara.core.core_tools.workspace_tool as mod

        test_file = tmp_path / "TEST.md"
        test_file.write_text("original")
        monkeypatch.setattr(mod, "WORKSPACE_DIR", tmp_path)

        result = await _handle_workspace_write({"filename": "TEST.md", "content": "new content"}, CTX)
        assert "Updated" in result
        assert test_file.read_text() == "new content"

    @pytest.mark.asyncio
    async def test_append_mode(self, tmp_path, monkeypatch):
        import mypalclara.core.core_tools.workspace_tool as mod

        test_file = tmp_path / "TEST.md"
        test_file.write_text("line one")
        monkeypatch.setattr(mod, "WORKSPACE_DIR", tmp_path)

        result = await _handle_workspace_write({"filename": "TEST.md", "content": "line two", "mode": "append"}, CTX)
        assert "Appended" in result
        content = test_file.read_text()
        assert "line one" in content
        assert "line two" in content


class TestWorkspaceCreate:
    @pytest.mark.asyncio
    async def test_create_new_file(self, tmp_path, monkeypatch):
        import mypalclara.core.core_tools.workspace_tool as mod

        monkeypatch.setattr(mod, "WORKSPACE_DIR", tmp_path)

        result = await _handle_workspace_create({"filename": "PROJECTS.md", "content": "# Projects"}, CTX)
        assert "Created" in result
        assert (tmp_path / "PROJECTS.md").read_text() == "# Projects"

    @pytest.mark.asyncio
    async def test_create_existing_file_blocked(self, tmp_path, monkeypatch):
        import mypalclara.core.core_tools.workspace_tool as mod

        (tmp_path / "EXISTS.md").write_text("already here")
        monkeypatch.setattr(mod, "WORKSPACE_DIR", tmp_path)

        result = await _handle_workspace_create({"filename": "EXISTS.md"}, CTX)
        assert "Error" in result
        assert "already exists" in result

    @pytest.mark.asyncio
    async def test_create_non_md_blocked(self):
        result = await _handle_workspace_create({"filename": "script.py", "content": "import os"}, CTX)
        assert "Error" in result
        assert ".md" in result

    @pytest.mark.asyncio
    async def test_create_reserved_name_blocked(self):
        result = await _handle_workspace_create({"filename": "SOUL.md", "content": "hacked"}, CTX)
        assert "Error" in result
        assert "reserved" in result

    @pytest.mark.asyncio
    async def test_create_empty_content(self, tmp_path, monkeypatch):
        import mypalclara.core.core_tools.workspace_tool as mod

        monkeypatch.setattr(mod, "WORKSPACE_DIR", tmp_path)

        result = await _handle_workspace_create({"filename": "EMPTY.md"}, CTX)
        assert "Created" in result
        assert (tmp_path / "EMPTY.md").read_text() == ""


class TestWorkspaceUserScoping:
    """Test that workspace tools route to user VM workspace when available."""

    @pytest.mark.asyncio
    async def test_read_from_user_vm_workspace(self, tmp_path, monkeypatch):
        """When user has a VM, workspace_read reads from VM workspace."""
        import mypalclara.core.core_tools.workspace_tool as mod

        user_ws = tmp_path / "vm_workspace"
        user_ws.mkdir()
        (user_ws / "USER.md").write_text("Name: Alice")

        monkeypatch.setattr(mod, "_resolve_workspace_dir", lambda ctx: user_ws)

        ctx = ToolContext(user_id="discord-123")
        result = await _handle_workspace_read({"filename": "USER.md"}, ctx)
        assert "Name: Alice" in result

    @pytest.mark.asyncio
    async def test_write_to_user_vm_workspace(self, tmp_path, monkeypatch):
        """When user has a VM, workspace_write writes to VM workspace."""
        import mypalclara.core.core_tools.workspace_tool as mod

        user_ws = tmp_path / "vm_workspace"
        user_ws.mkdir()
        (user_ws / "USER.md").write_text("original")
        monkeypatch.setattr(mod, "_resolve_workspace_dir", lambda ctx: user_ws)

        ctx = ToolContext(user_id="discord-123")
        result = await _handle_workspace_write({"filename": "USER.md", "content": "Name: Bob"}, ctx)
        assert "Updated" in result
        assert (user_ws / "USER.md").read_text() == "Name: Bob"

    @pytest.mark.asyncio
    async def test_global_files_always_from_shared(self, tmp_path, monkeypatch):
        """SOUL.md and IDENTITY.md always come from the shared workspace."""
        import mypalclara.core.core_tools.workspace_tool as mod

        shared_ws = tmp_path / "shared"
        shared_ws.mkdir()
        (shared_ws / "SOUL.md").write_text("Global soul content")
        monkeypatch.setattr(mod, "WORKSPACE_DIR", shared_ws)

        user_ws = tmp_path / "vm_workspace"
        user_ws.mkdir()
        # Even if the user workspace has a SOUL.md, the shared one should be used
        (user_ws / "SOUL.md").write_text("User soul content - should not be read")
        monkeypatch.setattr(mod, "_resolve_workspace_dir", lambda ctx: user_ws)

        ctx = ToolContext(user_id="discord-123")
        result = await _handle_workspace_read({"filename": "SOUL.md"}, ctx)
        assert "Global soul content" in result
        assert "User soul content" not in result

    @pytest.mark.asyncio
    async def test_create_in_user_vm_workspace(self, tmp_path, monkeypatch):
        """When user has a VM, workspace_create writes to VM workspace."""
        import mypalclara.core.core_tools.workspace_tool as mod

        user_ws = tmp_path / "vm_workspace"
        user_ws.mkdir()
        monkeypatch.setattr(mod, "_resolve_workspace_dir", lambda ctx: user_ws)

        ctx = ToolContext(user_id="discord-123")
        result = await _handle_workspace_create({"filename": "NOTES.md", "content": "My notes"}, ctx)
        assert "Created" in result
        assert (user_ws / "NOTES.md").read_text() == "My notes"
        # Should NOT exist in the default WORKSPACE_DIR
        assert not (WORKSPACE_DIR / "NOTES.md").exists() or WORKSPACE_DIR == user_ws

    @pytest.mark.asyncio
    async def test_list_from_user_vm_workspace(self, tmp_path, monkeypatch):
        """When user has a VM, workspace_list lists from VM workspace."""
        import mypalclara.core.core_tools.workspace_tool as mod

        user_ws = tmp_path / "vm_workspace"
        user_ws.mkdir()
        (user_ws / "CUSTOM.md").write_text("custom file")
        monkeypatch.setattr(mod, "_resolve_workspace_dir", lambda ctx: user_ws)

        ctx = ToolContext(user_id="discord-123")
        result = await _handle_workspace_list({}, ctx)
        assert "CUSTOM.md" in result

    @pytest.mark.asyncio
    async def test_no_vm_falls_back_to_shared(self, tmp_path, monkeypatch):
        """When user has no VM, workspace resolves to shared WORKSPACE_DIR."""
        import mypalclara.core.core_tools.workspace_tool as mod
        from mypalclara.core.core_tools.workspace_tool import _resolve_workspace_dir

        shared_ws = tmp_path / "shared"
        shared_ws.mkdir()
        (shared_ws / "USER.md").write_text("Shared user")
        monkeypatch.setattr(mod, "WORKSPACE_DIR", shared_ws)
        # Clear any user workspace registrations
        monkeypatch.setattr(mod, "_user_workspace_dirs", {})

        ctx = ToolContext(user_id="unknown-user")
        resolved = _resolve_workspace_dir(ctx)
        assert resolved == shared_ws

    @pytest.mark.asyncio
    async def test_register_user_workspace(self, tmp_path, monkeypatch):
        """Registering a user workspace makes _resolve_workspace_dir return it."""
        import mypalclara.core.core_tools.workspace_tool as mod
        from mypalclara.core.core_tools.workspace_tool import (
            _resolve_workspace_dir,
            register_user_workspace,
        )

        user_ws = tmp_path / "vm_workspace"
        user_ws.mkdir()
        monkeypatch.setattr(mod, "_user_workspace_dirs", {})

        register_user_workspace("discord-123", user_ws)

        ctx = ToolContext(user_id="discord-123")
        resolved = _resolve_workspace_dir(ctx)
        assert resolved == user_ws
