"""Tests for VM Manager — persistent per-user Docker container lifecycle."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mypalclara.core.vm_manager import VMManager, _sanitize_user_id


def _make_mock_container(status: str = "running") -> MagicMock:
    """Create a mock Docker container."""
    container = MagicMock()
    container.status = status
    container.start = MagicMock()
    container.stop = MagicMock()
    container.remove = MagicMock()
    container.exec_run = MagicMock(return_value=(0, b""))
    return container


def _make_mock_client(container: MagicMock | None = None) -> MagicMock:
    """Create a mock Docker client."""
    client = MagicMock()
    if container:
        client.containers.get.return_value = container
        client.containers.run.return_value = container
    return client


class TestVMManagerProvision:
    @pytest.mark.asyncio
    async def test_provision_creates_container(self):
        container = _make_mock_container()
        client = _make_mock_client(container)

        manager = VMManager()
        manager._client = client

        # containers.get raises NotFound to trigger creation
        from docker.errors import NotFound

        client.containers.get.side_effect = NotFound("not found")

        result = await manager.provision("discord-123")
        assert result is True
        client.containers.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_provision_sets_instance_name(self):
        container = _make_mock_container()
        client = _make_mock_client(container)

        manager = VMManager()
        manager._client = client

        from docker.errors import NotFound

        client.containers.get.side_effect = NotFound("not found")

        await manager.provision("discord-123")
        assert "discord-123" in manager._instances

    @pytest.mark.asyncio
    async def test_provision_already_exists_returns_true(self):
        manager = VMManager()
        manager._instances["discord-123"] = "clara-user-discord-123"
        result = await manager.provision("discord-123")
        assert result is True


class TestVMManagerSuspendResume:
    @pytest.mark.asyncio
    async def test_suspend_stops_container(self):
        container = _make_mock_container()
        client = _make_mock_client(container)

        manager = VMManager()
        manager._client = client
        manager._instances["discord-123"] = "clara-user-discord-123"
        manager._statuses["discord-123"] = "running"

        await manager.suspend("discord-123")
        container.stop.assert_called_once()
        assert manager._statuses["discord-123"] == "suspended"

    @pytest.mark.asyncio
    async def test_resume_starts_container(self):
        container = _make_mock_container(status="exited")
        client = _make_mock_client(container)

        manager = VMManager()
        manager._client = client
        manager._instances["discord-123"] = "clara-user-discord-123"
        manager._statuses["discord-123"] = "suspended"

        await manager.resume("discord-123")
        container.start.assert_called_once()
        assert manager._statuses["discord-123"] == "running"

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
        with patch.object(manager, "_vm_exists", new_callable=AsyncMock, return_value=True):
            with patch.object(manager, "_ensure_seeded", new_callable=AsyncMock):
                with patch.object(manager, "resume", new_callable=AsyncMock) as mock:
                    await manager.ensure_vm("discord-123")
                    mock.assert_called_once_with("discord-123")

    @pytest.mark.asyncio
    async def test_ensure_noop_if_running(self):
        manager = VMManager()
        manager._instances["discord-123"] = "clara-user-discord-123"
        manager._statuses["discord-123"] = "running"
        with patch.object(manager, "_vm_exists", new_callable=AsyncMock, return_value=True):
            with patch.object(manager, "_ensure_seeded", new_callable=AsyncMock):
                with patch.object(manager, "provision", new_callable=AsyncMock) as mock_p:
                    with patch.object(manager, "resume", new_callable=AsyncMock) as mock_r:
                        await manager.ensure_vm("discord-123")
                        mock_p.assert_not_called()
                        mock_r.assert_not_called()

    @pytest.mark.asyncio
    async def test_ensure_reprovisions_if_deleted_externally(self):
        manager = VMManager()
        manager._instances["discord-123"] = "clara-user-discord-123"
        manager._statuses["discord-123"] = "running"
        with patch.object(manager, "_vm_exists", new_callable=AsyncMock, return_value=False):
            with patch.object(manager, "provision", new_callable=AsyncMock) as mock_p:
                await manager.ensure_vm("discord-123")
                mock_p.assert_called_once_with("discord-123")


class TestVMManagerExec:
    @pytest.mark.asyncio
    async def test_exec_runs_command_in_container(self):
        container = _make_mock_container()
        container.exec_run.return_value = (0, b"hello")
        client = _make_mock_client(container)

        manager = VMManager()
        manager._client = client
        manager._instances["discord-123"] = "clara-user-discord-123"
        manager._statuses["discord-123"] = "running"

        with patch.object(manager, "_vm_exists", new_callable=AsyncMock, return_value=True):
            with patch.object(manager, "_ensure_seeded", new_callable=AsyncMock):
                result = await manager.exec_in_vm("discord-123", ["echo", "hello"])
                assert result == "hello"

    @pytest.mark.asyncio
    async def test_exec_ensures_vm_first(self):
        container = _make_mock_container()
        container.exec_run.return_value = (0, b"ok")
        client = _make_mock_client(container)

        manager = VMManager()
        manager._client = client
        manager._instances["discord-123"] = "clara-user-discord-123"
        manager._statuses["discord-123"] = "running"

        with patch.object(manager, "ensure_vm", new_callable=AsyncMock) as mock_ensure:
            with patch.object(manager, "_exec_direct", new_callable=AsyncMock, return_value="ok"):
                await manager.exec_in_vm("discord-123", ["ls"])
                mock_ensure.assert_called_once()


class TestVMManagerReadWriteFile:
    @pytest.mark.asyncio
    async def test_read_file_from_container(self):
        manager = VMManager()
        manager._instances["discord-123"] = "clara-user-discord-123"
        manager._statuses["discord-123"] = "running"
        with patch.object(manager, "exec_in_vm", new_callable=AsyncMock, return_value="file content"):
            result = await manager.read_file("discord-123", "/home/clara/workspace/USER.md")
            assert result == "file content"

    @pytest.mark.asyncio
    async def test_write_file_to_container(self):
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

        container = _make_mock_container()
        client = _make_mock_client(container)

        from docker.errors import NotFound

        client.containers.get.side_effect = NotFound("not found")

        manager = VMManager(session_factory=lambda: db_session)
        manager._client = client

        await manager.provision("discord-789")

        vm = db_session.query(UserVM).filter_by(user_id="discord-789").first()
        assert vm is not None
        assert vm.status == "running"
        assert "discord-789" in vm.instance_name

    @pytest.mark.asyncio
    async def test_suspend_updates_db(self, db_session):
        from mypalclara.db.models import UserVM

        container = _make_mock_container()
        client = _make_mock_client(container)

        from docker.errors import NotFound

        # First call raises NotFound (provision creates), subsequent calls return container
        client.containers.get.side_effect = [NotFound("not found"), container, container]

        manager = VMManager(session_factory=lambda: db_session)
        manager._client = client

        await manager.provision("discord-789")
        # Reset side_effect for suspend's docker_get call
        client.containers.get.side_effect = None
        client.containers.get.return_value = container
        await manager.suspend("discord-789")

        vm = db_session.query(UserVM).filter_by(user_id="discord-789").first()
        assert vm.status == "suspended"
        assert vm.suspended_at is not None

    @pytest.mark.asyncio
    async def test_resume_updates_db(self, db_session):
        from mypalclara.db.models import UserVM

        container = _make_mock_container()
        client = _make_mock_client(container)

        from docker.errors import NotFound

        client.containers.get.side_effect = [NotFound("not found"), container, container]

        manager = VMManager(session_factory=lambda: db_session)
        manager._client = client

        await manager.provision("discord-789")
        client.containers.get.side_effect = None
        client.containers.get.return_value = container
        await manager.suspend("discord-789")
        await manager.resume("discord-789")

        vm = db_session.query(UserVM).filter_by(user_id="discord-789").first()
        assert vm.status == "running"

    @pytest.mark.asyncio
    async def test_load_from_db_on_init(self, db_session):
        from mypalclara.db.models import UserVM

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
