"""Tests for UserVM database model."""

from __future__ import annotations

import pytest

from mypalclara.db.models import UserVM


class TestUserVMModel:
    def test_create_user_vm(self, db_session):
        vm = UserVM(
            user_id="discord-123",
            instance_name="clara-user-discord-123",
            instance_type="container",
        )
        db_session.add(vm)
        db_session.commit()
        db_session.refresh(vm)

        assert vm.id is not None
        assert vm.user_id == "discord-123"
        assert vm.instance_name == "clara-user-discord-123"
        assert vm.instance_type == "container"
        assert vm.status == "provisioning"
        assert vm.created_at is not None
        assert vm.last_accessed_at is not None
        assert vm.suspended_at is None

    def test_user_id_unique(self, db_session):
        vm1 = UserVM(user_id="discord-123", instance_name="clara-user-discord-123", instance_type="container")
        vm2 = UserVM(user_id="discord-123", instance_name="clara-user-discord-123-2", instance_type="container")
        db_session.add(vm1)
        db_session.commit()
        db_session.add(vm2)
        with pytest.raises(Exception):  # IntegrityError
            db_session.commit()

    def test_status_values(self, db_session):
        vm = UserVM(user_id="discord-456", instance_name="clara-user-discord-456", instance_type="vm")
        db_session.add(vm)
        db_session.commit()

        vm.status = "running"
        db_session.commit()
        assert vm.status == "running"

        vm.status = "suspended"
        db_session.commit()
        assert vm.status == "suspended"
