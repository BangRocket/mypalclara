"""Tests for per-user tool permissions."""

from __future__ import annotations

import pytest

from mypalclara.core.security.tool_permissions import (
    RESTRICTED_TOOLS,
    SUBAGENT_BLOCKED,
    ToolPermissions,
    get_permissions,
)


class TestToolPermissions:
    """Test the ToolPermissions class."""

    def test_default_allows_safe_tools(self):
        """Unrestricted tools are allowed for any user."""
        perms = ToolPermissions(trusted_users=set())
        assert perms.can_execute("format_discord_message", "random-user") is True
        assert perms.can_execute("list_local_files", "random-user") is True
        assert perms.can_execute("web_search", "random-user") is True

    def test_restricted_tools_blocked_for_untrusted(self):
        """Restricted tools are denied for users not in the trusted set."""
        perms = ToolPermissions(trusted_users={"trusted-alice"})
        for tool in RESTRICTED_TOOLS:
            assert perms.can_execute(tool, "untrusted-bob") is False, f"{tool} should be blocked for untrusted user"

    def test_trusted_users_can_run_restricted_tools(self):
        """Trusted users can execute restricted tools."""
        perms = ToolPermissions(trusted_users={"trusted-alice"})
        for tool in RESTRICTED_TOOLS:
            assert perms.can_execute(tool, "trusted-alice") is True, f"{tool} should be allowed for trusted user"

    def test_subagent_blocks_escalation_even_for_trusted(self):
        """Subagent context blocks dangerous tools regardless of trust level."""
        perms = ToolPermissions(trusted_users={"trusted-alice"})
        for tool in SUBAGENT_BLOCKED:
            assert (
                perms.can_execute(tool, "trusted-alice", is_subagent=True) is False
            ), f"{tool} should be blocked in subagent context"

    def test_subagent_allows_safe_tools(self):
        """Subagent context still allows non-blocked tools."""
        perms = ToolPermissions(trusted_users=set())
        assert perms.can_execute("format_discord_message", "any-user", is_subagent=True) is True

    def test_custom_deny_list(self):
        """Per-user deny list blocks specific tools even for trusted users."""
        perms = ToolPermissions(
            trusted_users={"alice"},
            user_deny={"alice": frozenset({"web_search", "list_local_files"})},
        )
        assert perms.can_execute("web_search", "alice") is False
        assert perms.can_execute("list_local_files", "alice") is False
        # Other tools still work
        assert perms.can_execute("format_discord_message", "alice") is True

    def test_trusted_users_from_env(self, monkeypatch):
        """TRUSTED_USER_IDS env var populates the trusted set."""
        monkeypatch.setenv("TRUSTED_USER_IDS", "user-a, user-b, user-c")
        perms = ToolPermissions()
        assert perms.can_execute("execute_python", "user-a") is True
        assert perms.can_execute("execute_python", "user-b") is True
        assert perms.can_execute("execute_python", "unknown") is False

    def test_empty_env_means_no_trusted(self, monkeypatch):
        """Empty TRUSTED_USER_IDS means no one is trusted."""
        monkeypatch.setenv("TRUSTED_USER_IDS", "")
        perms = ToolPermissions()
        assert perms.can_execute("execute_python", "anyone") is False

    def test_no_env_means_no_trusted(self, monkeypatch):
        """Missing TRUSTED_USER_IDS means no one is trusted."""
        monkeypatch.delenv("TRUSTED_USER_IDS", raising=False)
        perms = ToolPermissions()
        assert perms.can_execute("run_shell", "anyone") is False

    def test_singleton_accessor(self, monkeypatch):
        """get_permissions() returns a singleton."""
        # Reset the module-level singleton
        import mypalclara.core.security.tool_permissions as mod

        mod._permissions_instance = None
        monkeypatch.setenv("TRUSTED_USER_IDS", "singleton-user")
        p1 = get_permissions()
        p2 = get_permissions()
        assert p1 is p2
        assert p1.can_execute("execute_python", "singleton-user") is True
        # Clean up
        mod._permissions_instance = None
