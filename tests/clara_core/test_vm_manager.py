"""Tests for VM Manager — persistent per-user VM lifecycle."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from mypalclara.core.vm_manager import VMManager, _sanitize_user_id


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

    @pytest.mark.asyncio
    async def test_write_file_rejects_delimiter_in_content(self):
        manager = VMManager()
        manager._instances["discord-123"] = "clara-user-discord-123"
        manager._statuses["discord-123"] = "running"
        with pytest.raises(ValueError, match="reserved delimiter"):
            await manager.write_file(
                "discord-123",
                "/home/clara/workspace/test.txt",
                "some CLARA_EOF content",
            )

    @pytest.mark.asyncio
    async def test_write_file_quotes_path(self):
        manager = VMManager()
        manager._instances["discord-123"] = "clara-user-discord-123"
        manager._statuses["discord-123"] = "running"
        with patch.object(manager, "exec_in_vm", new_callable=AsyncMock, return_value="") as mock_exec:
            await manager.write_file(
                "discord-123",
                "/home/clara/workspace/my file.txt",
                "content",
            )
            call_args = mock_exec.call_args[0]
            shell_cmd = call_args[1][2]  # The sh -c argument
            assert "'/home/clara/workspace/my file.txt'" in shell_cmd


class TestVMManagerDBPersistence:
    @pytest.mark.asyncio
    async def test_provision_creates_db_record(self, db_session):
        from mypalclara.db.models import UserVM

        manager = VMManager(session_factory=lambda: db_session)
        with patch.object(manager, "_run_incus", new_callable=AsyncMock, return_value=""):
            await manager.provision("discord-789")

        vm = db_session.query(UserVM).filter_by(user_id="discord-789").first()
        assert vm is not None
        assert vm.status == "running"
        assert "discord-789" in vm.instance_name

    @pytest.mark.asyncio
    async def test_suspend_updates_db(self, db_session):
        from mypalclara.db.models import UserVM

        manager = VMManager(session_factory=lambda: db_session)
        with patch.object(manager, "_run_incus", new_callable=AsyncMock, return_value=""):
            await manager.provision("discord-789")
            await manager.suspend("discord-789")

        vm = db_session.query(UserVM).filter_by(user_id="discord-789").first()
        assert vm.status == "suspended"
        assert vm.suspended_at is not None

    @pytest.mark.asyncio
    async def test_resume_updates_db(self, db_session):
        from mypalclara.db.models import UserVM

        manager = VMManager(session_factory=lambda: db_session)
        with patch.object(manager, "_run_incus", new_callable=AsyncMock, return_value=""):
            await manager.provision("discord-789")
            await manager.suspend("discord-789")
            await manager.resume("discord-789")

        vm = db_session.query(UserVM).filter_by(user_id="discord-789").first()
        assert vm.status == "running"

    @pytest.mark.asyncio
    async def test_load_from_db_on_init(self, db_session):
        from mypalclara.db.models import UserVM

        # Seed a VM record
        vm = UserVM(
            user_id="discord-999",
            instance_name="clara-user-discord-999",
            instance_type="container",
            status="suspended",
        )
        db_session.add(vm)
        db_session.commit()

        manager = VMManager(session_factory=lambda: db_session)
        await manager.load_from_db()
        assert "discord-999" in manager._instances
        assert manager._statuses["discord-999"] == "suspended"


class TestSanitizeUserId:
    def test_empty_user_id_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            _sanitize_user_id("")

    def test_all_invalid_chars_raises(self):
        with pytest.raises(ValueError, match="no valid characters"):
            _sanitize_user_id("@@@")

    def test_normal_id_passes(self):
        assert _sanitize_user_id("discord-123") == "discord-123"

    def test_special_chars_replaced(self):
        assert _sanitize_user_id("user@name.com") == "user-name-com"

    def test_leading_trailing_dashes_stripped(self):
        assert _sanitize_user_id("@user@") == "user"
