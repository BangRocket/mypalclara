"""Per-user tool permission system.

Controls which tools each user can access. Dangerous tools (sandbox, shell,
subagent spawning) require explicit trust via TRUSTED_USER_IDS env var.
Subagents are never allowed to spawn more subagents or access shell/sandbox.
"""

from __future__ import annotations

import os
from typing import Any

RESTRICTED_TOOLS: frozenset[str] = frozenset(
    {
        "execute_python",
        "install_package",
        "run_shell",
        "write_file",
        "run_claude_code",
        "subagent_spawn",
    }
)

SUBAGENT_BLOCKED: frozenset[str] = frozenset(
    {
        "subagent_spawn",
        "subagent_kill",
        "subagent_steer",
        "run_shell",
        "execute_python",
        "run_claude_code",
    }
)


class ToolPermissions:
    """Manages per-user tool access control.

    Args:
        trusted_users: Set of user IDs allowed to run restricted tools.
            If None, loaded from TRUSTED_USER_IDS env var (comma-separated).
        user_deny: Optional per-user deny lists mapping user_id to frozenset
            of tool names that user is explicitly blocked from using.
    """

    def __init__(
        self,
        trusted_users: set[str] | None = None,
        user_deny: dict[str, frozenset[str]] | None = None,
    ) -> None:
        if trusted_users is not None:
            self._trusted = trusted_users
        else:
            raw = os.getenv("TRUSTED_USER_IDS", "")
            self._trusted = {uid.strip() for uid in raw.split(",") if uid.strip()}

        self._user_deny: dict[str, frozenset[str]] = user_deny or {}

    def can_execute(self, tool_name: str, user_id: str, is_subagent: bool = False) -> bool:
        """Check whether a user/context is allowed to run a tool.

        Args:
            tool_name: Name of the tool to check.
            user_id: The user requesting execution.
            is_subagent: True if the caller is a subagent.

        Returns:
            True if execution is permitted, False otherwise.
        """
        # Subagent context: block escalation tools unconditionally
        if is_subagent and tool_name in SUBAGENT_BLOCKED:
            return False

        # Per-user deny list
        denied = self._user_deny.get(user_id, frozenset())
        if tool_name in denied:
            return False

        # Restricted tools require trust
        if tool_name in RESTRICTED_TOOLS:
            return user_id in self._trusted

        # Everything else is allowed
        return True


# Module-level singleton
_permissions_instance: ToolPermissions | None = None


def get_permissions() -> ToolPermissions:
    """Return the module-level ToolPermissions singleton.

    Creates an instance on first call using TRUSTED_USER_IDS env var.
    """
    global _permissions_instance
    if _permissions_instance is None:
        _permissions_instance = ToolPermissions()
    return _permissions_instance
