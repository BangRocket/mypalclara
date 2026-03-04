"""Tests for VM Manager — persistent per-user VM lifecycle."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from mypalclara.core.vm_manager import VMManager


class TestVMManagerProvision:
    @pytest.mark.asyncio
    async def test_provision_creates_instance(self):
        manager = VMManager()
        with patch.object(manager, "_run_incus", new_callable=AsyncMock, return_value="") as mock_run:
            result = await manager.provision("discord-123")
            assert result is True
            calls = [str(c) for c in mock_run.call_args_list]
            assert any("launch" in c for c in calls)

    @pytest.mark.asyncio
    async def test_provision_sets_instance_name(self):
        manager = VMManager()
        with patch.object(manager, "_run_incus", new_callable=AsyncMock, return_value=""):
            await manager.provision("discord-123")
            assert "discord-123" in manager._instances

    @pytest.mark.asyncio
    async def test_provision_already_exists_returns_true(self):
        manager = VMManager()
        manager._instances["discord-123"] = "clara-user-discord-123"
        with patch.object(manager, "_run_incus", new_callable=AsyncMock, return_value="RUNNING"):
            result = await manager.provision("discord-123")
            assert result is True


class TestVMManagerSuspendResume:
    @pytest.mark.asyncio
    async def test_suspend_pauses_instance(self):
        manager = VMManager()
        manager._instances["discord-123"] = "clara-user-discord-123"
        with patch.object(manager, "_run_incus", new_callable=AsyncMock, return_value="") as mock_run:
            await manager.suspend("discord-123")
            calls = [str(c) for c in mock_run.call_args_list]
            assert any("pause" in c for c in calls)

    @pytest.mark.asyncio
    async def test_resume_starts_instance(self):
        manager = VMManager()
        manager._instances["discord-123"] = "clara-user-discord-123"
        with patch.object(manager, "_run_incus", new_callable=AsyncMock, return_value="") as mock_run:
            await manager.resume("discord-123")
            calls = [str(c) for c in mock_run.call_args_list]
            assert any("start" in c for c in calls)

    @pytest.mark.asyncio
    async def test_suspend_unknown_user_raises(self):
        manager = VMManager()
        with pytest.raises(ValueError, match="No VM found"):
            await manager.suspend("nonexistent")


class TestVMManagerEnsure:
    @pytest.mark.asyncio
    async def test_ensure_provisions_if_not_exists(self):
        manager = VMManager()
        with patch.object(manager, "provision", new_callable=AsyncMock, return_value=True) as mock:
            await manager.ensure_vm("discord-123")
            mock.assert_called_once_with("discord-123")

    @pytest.mark.asyncio
    async def test_ensure_resumes_if_suspended(self):
        manager = VMManager()
        manager._instances["discord-123"] = "clara-user-discord-123"
        manager._statuses["discord-123"] = "suspended"
        with patch.object(manager, "resume", new_callable=AsyncMock) as mock:
            await manager.ensure_vm("discord-123")
            mock.assert_called_once_with("discord-123")

    @pytest.mark.asyncio
    async def test_ensure_noop_if_running(self):
        manager = VMManager()
        manager._instances["discord-123"] = "clara-user-discord-123"
        manager._statuses["discord-123"] = "running"
        with patch.object(manager, "provision", new_callable=AsyncMock) as mock_p:
            with patch.object(manager, "resume", new_callable=AsyncMock) as mock_r:
                await manager.ensure_vm("discord-123")
                mock_p.assert_not_called()
                mock_r.assert_not_called()


class TestVMManagerExec:
    @pytest.mark.asyncio
    async def test_exec_runs_command_in_vm(self):
        manager = VMManager()
        manager._instances["discord-123"] = "clara-user-discord-123"
        manager._statuses["discord-123"] = "running"
        with patch.object(manager, "_run_incus", new_callable=AsyncMock, return_value="hello"):
            result = await manager.exec_in_vm("discord-123", ["echo", "hello"])
            assert result == "hello"

    @pytest.mark.asyncio
    async def test_exec_ensures_vm_first(self):
        manager = VMManager()
        with patch.object(manager, "ensure_vm", new_callable=AsyncMock) as mock_ensure:
            with patch.object(manager, "_run_incus", new_callable=AsyncMock, return_value="ok"):
                manager._instances["discord-123"] = "clara-user-discord-123"
                manager._statuses["discord-123"] = "running"
                await manager.exec_in_vm("discord-123", ["ls"])
                mock_ensure.assert_called_once()


class TestVMManagerReadWriteFile:
    @pytest.mark.asyncio
    async def test_read_file_from_vm(self):
        manager = VMManager()
        manager._instances["discord-123"] = "clara-user-discord-123"
        manager._statuses["discord-123"] = "running"
        with patch.object(manager, "exec_in_vm", new_callable=AsyncMock, return_value="file content"):
            result = await manager.read_file("discord-123", "/home/clara/workspace/USER.md")
            assert result == "file content"

    @pytest.mark.asyncio
    async def test_write_file_to_vm(self):
        manager = VMManager()
        manager._instances["discord-123"] = "clara-user-discord-123"
        manager._statuses["discord-123"] = "running"
        with patch.object(manager, "exec_in_vm", new_callable=AsyncMock, return_value="") as mock_exec:
            await manager.write_file("discord-123", "/home/clara/workspace/USER.md", "new content")
            mock_exec.assert_called_once()
