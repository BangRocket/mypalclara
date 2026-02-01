"""Route resolution for message handling.

Determines which agent/persona handles a message based on binding configuration.
Uses priority-based matching following OpenClaw's pattern.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING, Any

from config.logging import get_logger

if TYPE_CHECKING:
    from clara_core.channels.types import MsgContext

logger = get_logger("routing.resolve")


class BindingPriority(IntEnum):
    """Binding priority levels (higher = more specific).

    Matches OpenClaw's binding priority system.
    """

    # Most specific - direct match to user or group
    PEER = 100

    # Discord guild / Slack workspace
    GUILD = 80

    # Teams team
    TEAM = 70

    # Specific bot account
    ACCOUNT = 60

    # Any account on this channel
    CHANNEL = 40

    # Fallback
    DEFAULT = 0


class SessionScope(str):
    """Session scoping options.

    Determines how sessions are isolated between conversations.
    """

    # Shared session across all peers (simplest)
    MAIN = "main"

    # Isolated session per contact/user
    PER_PEER = "per-peer"

    # Per contact per channel (different sessions in #work vs #general)
    PER_CHANNEL_PEER = "per-channel-peer"

    # Full isolation: per account, per channel, per peer
    PER_ACCOUNT_CHANNEL_PEER = "per-account-channel-peer"


@dataclass
class AgentBinding:
    """Configuration for agent routing.

    Specifies when an agent should handle messages.
    """

    # Agent/persona identifier
    agent_id: str

    # Binding type and value
    # binding_type: one of "peer", "guild", "team", "account", "channel", "default"
    binding_type: str = "default"
    binding_value: str | None = None

    # Session scoping
    session_scope: str = SessionScope.PER_PEER

    # Priority override (uses BindingPriority default if not set)
    priority: int | None = None

    # Optional: Only match specific channels within the binding
    channel_filter: list[str] | None = None

    # Optional: Require @mention
    require_mention: bool = False

    # Optional: Custom system prompt override
    system_prompt: str | None = None

    # Optional: Model tier override
    model_tier: str | None = None

    # Additional metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_priority(self) -> int:
        """Get the effective priority for this binding."""
        if self.priority is not None:
            return self.priority

        priority_map = {
            "peer": BindingPriority.PEER,
            "guild": BindingPriority.GUILD,
            "team": BindingPriority.TEAM,
            "account": BindingPriority.ACCOUNT,
            "channel": BindingPriority.CHANNEL,
            "default": BindingPriority.DEFAULT,
        }
        return priority_map.get(self.binding_type, BindingPriority.DEFAULT)


@dataclass
class AgentRoute:
    """Result of route resolution."""

    # The binding that matched
    binding: AgentBinding

    # The agent ID to use
    agent_id: str

    # Generated session key
    session_key: str

    # Priority of the match
    priority: int

    # Whether this was a default fallback
    is_default: bool = False


class RouteResolver:
    """Resolves message routes based on bindings.

    Maintains a list of bindings and finds the best match for each message.
    """

    def __init__(self) -> None:
        """Initialize the route resolver."""
        self._bindings: list[AgentBinding] = []
        self._default_agent: str = "clara"

    def add_binding(self, binding: AgentBinding) -> None:
        """Add a routing binding.

        Args:
            binding: The binding to add
        """
        self._bindings.append(binding)
        # Keep bindings sorted by priority (highest first)
        self._bindings.sort(key=lambda b: b.get_priority(), reverse=True)

    def remove_binding(self, agent_id: str, binding_type: str, binding_value: str | None = None) -> bool:
        """Remove a routing binding.

        Args:
            agent_id: Agent ID
            binding_type: Binding type
            binding_value: Binding value (optional)

        Returns:
            True if removed
        """
        for i, b in enumerate(self._bindings):
            if (
                b.agent_id == agent_id
                and b.binding_type == binding_type
                and (binding_value is None or b.binding_value == binding_value)
            ):
                del self._bindings[i]
                return True
        return False

    def set_default_agent(self, agent_id: str) -> None:
        """Set the default agent for unmatched messages.

        Args:
            agent_id: The default agent ID
        """
        self._default_agent = agent_id

    def resolve(self, context: "MsgContext") -> AgentRoute:
        """Resolve the route for a message.

        Args:
            context: The message context

        Returns:
            The resolved route
        """
        from clara_core.routing.session_key import generate_session_key

        for binding in self._bindings:
            if self._matches(binding, context):
                session_key = generate_session_key(binding.session_scope, context)
                return AgentRoute(
                    binding=binding,
                    agent_id=binding.agent_id,
                    session_key=session_key,
                    priority=binding.get_priority(),
                    is_default=binding.binding_type == "default",
                )

        # Fallback to default
        default_binding = AgentBinding(
            agent_id=self._default_agent,
            binding_type="default",
        )
        session_key = generate_session_key(SessionScope.PER_PEER, context)
        return AgentRoute(
            binding=default_binding,
            agent_id=self._default_agent,
            session_key=session_key,
            priority=BindingPriority.DEFAULT,
            is_default=True,
        )

    def _matches(self, binding: AgentBinding, context: "MsgContext") -> bool:
        """Check if a binding matches a message context.

        Args:
            binding: The binding to check
            context: The message context

        Returns:
            True if the binding matches
        """
        # Check mention requirement
        if binding.require_mention and not context.is_mention:
            return False

        # Check channel filter
        if binding.channel_filter and context.channel_id:
            if context.channel_id not in binding.channel_filter:
                return False

        # Check binding type match
        match binding.binding_type:
            case "peer":
                return binding.binding_value == context.user_id

            case "guild":
                return binding.binding_value == context.guild_id

            case "team":
                # For Teams integration
                team_id = context.metadata.get("team_id")
                return binding.binding_value == team_id

            case "account":
                return binding.binding_value == context.account_id

            case "channel":
                return binding.binding_value == str(context.channel_type.value)

            case "default":
                return True

            case _:
                return False


# Global resolver instance
_resolver: RouteResolver | None = None


def get_resolver() -> RouteResolver:
    """Get the global route resolver."""
    global _resolver
    if _resolver is None:
        _resolver = RouteResolver()
    return _resolver


def resolve_route(context: "MsgContext") -> AgentRoute:
    """Resolve the route for a message.

    Convenience function that uses the global resolver.

    Args:
        context: The message context

    Returns:
        The resolved route
    """
    return get_resolver().resolve(context)
