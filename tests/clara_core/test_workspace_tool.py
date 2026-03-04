"""Tests for workspace file tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

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


def _setup_vm_user(monkeypatch, user_id: str, vm_files: dict[str, str]):
    """Helper: register a user with a mock VM manager.

    Args:
        monkeypatch: pytest monkeypatch
        user_id: user to register
        vm_files: dict of filename -> content in the VM workspace
    """
    import mypalclara.core.core_tools.workspace_tool as mod

    # Build mock VM manager
    mock_vm = MagicMock()

    async def mock_exec(uid, cmd):
        # Handle stat listing
        cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
        if "stat" in cmd_str:
            lines = []
            for name, content in vm_files.items():
                lines.append(f"{name} {len(content)}")
            return "\n".join(lines)
        # Handle test -f
        if "test" in cmd_str and "-f" in cmd_str:
            path = cmd[-1] if isinstance(cmd, list) else ""
            filename = path.rsplit("/", 1)[-1]
            if filename in vm_files:
                return ""
            raise RuntimeError("file not found")
        return ""

    async def mock_read(uid, path):
        filename = path.rsplit("/", 1)[-1]
        if filename in vm_files:
            return vm_files[filename]
        raise RuntimeError(f"cat: {path}: No such file or directory")

    async def mock_write(uid, path, content):
        filename = path.rsplit("/", 1)[-1]
        vm_files[filename] = content

    mock_vm.exec_in_vm = mock_exec
    mock_vm.read_file = mock_read
    mock_vm.write_file = mock_write

    monkeypatch.setattr(mod, "_vm_manager", mock_vm)
    monkeypatch.setattr(mod, "_vm_users", {user_id})

    return mock_vm


class TestWorkspaceVMRouting:
    """Test that workspace tools route through VM manager for VM users."""

    @pytest.mark.asyncio
    async def test_list_from_vm(self, monkeypatch):
        vm_files = {"USER.md": "Name: Alice", "MEMORY.md": "Some memories"}
        _setup_vm_user(monkeypatch, "vm-user", vm_files)

        ctx = ToolContext(user_id="vm-user")
        result = await _handle_workspace_list({}, ctx)
        assert "VM" in result
        assert "USER.md" in result
        assert "MEMORY.md" in result

    @pytest.mark.asyncio
    async def test_read_from_vm(self, monkeypatch):
        vm_files = {"USER.md": "Name: Alice"}
        _setup_vm_user(monkeypatch, "vm-user", vm_files)

        ctx = ToolContext(user_id="vm-user")
        result = await _handle_workspace_read({"filename": "USER.md"}, ctx)
        assert "Name: Alice" in result

    @pytest.mark.asyncio
    async def test_read_nonexistent_in_vm(self, monkeypatch):
        _setup_vm_user(monkeypatch, "vm-user", {})

        ctx = ToolContext(user_id="vm-user")
        result = await _handle_workspace_read({"filename": "NOPE.md"}, ctx)
        assert "Error" in result
        assert "not found" in result

    @pytest.mark.asyncio
    async def test_global_files_from_shared_not_vm(self, monkeypatch):
        """SOUL.md always comes from shared workspace, even for VM users."""
        vm_files = {"SOUL.md": "VM soul - should not be read"}
        _setup_vm_user(monkeypatch, "vm-user", vm_files)

        ctx = ToolContext(user_id="vm-user")
        result = await _handle_workspace_read({"filename": "SOUL.md"}, ctx)
        # Should read from shared WORKSPACE_DIR, not VM
        assert "VM soul" not in result
        assert "Clara" in result  # Real SOUL.md content

    @pytest.mark.asyncio
    async def test_write_to_vm(self, monkeypatch):
        vm_files = {"NOTES.md": "old notes"}
        _setup_vm_user(monkeypatch, "vm-user", vm_files)

        ctx = ToolContext(user_id="vm-user")
        result = await _handle_workspace_write({"filename": "NOTES.md", "content": "new notes"}, ctx)
        assert "Updated" in result or "VM" in result
        assert vm_files["NOTES.md"] == "new notes"

    @pytest.mark.asyncio
    async def test_append_to_vm(self, monkeypatch):
        vm_files = {"NOTES.md": "line one"}
        _setup_vm_user(monkeypatch, "vm-user", vm_files)

        ctx = ToolContext(user_id="vm-user")
        result = await _handle_workspace_write(
            {"filename": "NOTES.md", "content": "line two", "mode": "append"}, ctx
        )
        assert "Appended" in result
        assert "line one" in vm_files["NOTES.md"]
        assert "line two" in vm_files["NOTES.md"]

    @pytest.mark.asyncio
    async def test_create_in_vm(self, monkeypatch):
        vm_files: dict[str, str] = {}
        _setup_vm_user(monkeypatch, "vm-user", vm_files)

        ctx = ToolContext(user_id="vm-user")
        result = await _handle_workspace_create({"filename": "NEW.md", "content": "hello"}, ctx)
        assert "Created" in result
        assert vm_files["NEW.md"] == "hello"

    @pytest.mark.asyncio
    async def test_create_existing_in_vm_blocked(self, monkeypatch):
        vm_files = {"EXISTS.md": "already here"}
        _setup_vm_user(monkeypatch, "vm-user", vm_files)

        ctx = ToolContext(user_id="vm-user")
        result = await _handle_workspace_create({"filename": "EXISTS.md", "content": "new"}, ctx)
        assert "Error" in result
        assert "already exists" in result

    @pytest.mark.asyncio
    async def test_no_vm_uses_filesystem(self, tmp_path, monkeypatch):
        """Users without a VM fall back to shared filesystem workspace."""
        import mypalclara.core.core_tools.workspace_tool as mod

        monkeypatch.setattr(mod, "_vm_manager", None)
        monkeypatch.setattr(mod, "_vm_users", set())
        monkeypatch.setattr(mod, "WORKSPACE_DIR", tmp_path)

        (tmp_path / "TEST.md").write_text("filesystem content")

        ctx = ToolContext(user_id="no-vm-user")
        result = await _handle_workspace_read({"filename": "TEST.md"}, ctx)
        assert "filesystem content" in result
