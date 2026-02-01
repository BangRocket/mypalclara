"""Session key generation for route-based sessions.

Generates unique session keys based on scoping configuration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clara_core.channels.types import MsgContext


@dataclass
class SessionKey:
    """Parsed session key components."""

    scope: str
    channel_type: str
    account_id: str | None
    channel_id: str | None
    user_id: str

    @property
    def full_key(self) -> str:
        """Get the full session key string."""
        parts = [self.scope, self.channel_type]
        if self.account_id:
            parts.append(self.account_id)
        if self.channel_id:
            parts.append(self.channel_id)
        parts.append(self.user_id)
        return ":".join(parts)


def generate_session_key(scope: str, context: "MsgContext") -> str:
    """Generate a session key based on scope and context.

    Session scoping determines how sessions are isolated:
    - main: All messages share one session per user
    - per-peer: One session per user (regardless of channel)
    - per-channel-peer: One session per user per channel
    - per-account-channel-peer: Full isolation

    Args:
        scope: Session scope (main, per-peer, per-channel-peer, per-account-channel-peer)
        context: The message context

    Returns:
        Session key string
    """
    channel_type = str(context.channel_type.value)
    account_id = context.account_id or "default"
    channel_id = context.channel_id or "default"
    user_id = context.user_id

    match scope:
        case "main":
            # Shared session: just channel type and user
            return f"main:{channel_type}:{user_id}"

        case "per-peer":
            # One session per user
            return f"peer:{channel_type}:{user_id}"

        case "per-channel-peer":
            # One session per user per channel
            return f"channel:{channel_type}:{channel_id}:{user_id}"

        case "per-account-channel-peer":
            # Full isolation
            return f"full:{channel_type}:{account_id}:{channel_id}:{user_id}"

        case _:
            # Default to per-peer
            return f"peer:{channel_type}:{user_id}"


def parse_session_key(key: str) -> SessionKey | None:
    """Parse a session key string into components.

    Args:
        key: The session key string

    Returns:
        SessionKey or None if parsing fails
    """
    parts = key.split(":")
    if len(parts) < 3:
        return None

    scope = parts[0]
    channel_type = parts[1]

    match scope:
        case "main":
            if len(parts) != 3:
                return None
            return SessionKey(
                scope=scope,
                channel_type=channel_type,
                account_id=None,
                channel_id=None,
                user_id=parts[2],
            )

        case "peer":
            if len(parts) != 3:
                return None
            return SessionKey(
                scope=scope,
                channel_type=channel_type,
                account_id=None,
                channel_id=None,
                user_id=parts[2],
            )

        case "channel":
            if len(parts) != 4:
                return None
            return SessionKey(
                scope=scope,
                channel_type=channel_type,
                account_id=None,
                channel_id=parts[2],
                user_id=parts[3],
            )

        case "full":
            if len(parts) != 5:
                return None
            return SessionKey(
                scope=scope,
                channel_type=channel_type,
                account_id=parts[2],
                channel_id=parts[3],
                user_id=parts[4],
            )

        case _:
            return None
