"""Channel adapter interfaces.

Defines the ~15 optional adapters that channels can implement.
Each adapter handles a specific aspect of channel functionality.
Channels implement only the adapters they need.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, AsyncIterator, Callable, Protocol

if TYPE_CHECKING:
    from clara_core.channels.types import MsgContext


# =============================================================================
# Configuration Adapters
# =============================================================================


class ChannelConfigAdapter(Protocol):
    """Handles channel-specific configuration.

    Responsible for:
    - Loading channel configuration
    - Validating config values
    - Providing defaults
    """

    def get_config(self) -> dict[str, Any]:
        """Get current channel configuration."""
        ...

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        """Validate configuration, return list of errors."""
        ...

    def get_default_config(self) -> dict[str, Any]:
        """Get default configuration values."""
        ...


class ChannelSetupAdapter(Protocol):
    """Handles channel setup and onboarding.

    Responsible for:
    - Initial channel setup flow
    - Account connection
    - Credential management
    """

    async def run_setup(self) -> bool:
        """Run interactive setup flow. Returns True if successful."""
        ...

    async def verify_setup(self) -> tuple[bool, str]:
        """Verify setup is complete. Returns (success, message)."""
        ...

    def get_setup_instructions(self) -> str:
        """Get human-readable setup instructions."""
        ...


class ChannelPairingAdapter(Protocol):
    """Handles device/user pairing for remote access.

    Responsible for:
    - Generating pairing codes
    - Validating pairing requests
    - Managing paired devices
    """

    async def generate_pairing_code(self) -> str:
        """Generate a pairing code for device linking."""
        ...

    async def validate_pairing(self, code: str, device_info: dict[str, Any]) -> bool:
        """Validate a pairing attempt."""
        ...

    async def list_paired_devices(self) -> list[dict[str, Any]]:
        """List all paired devices."""
        ...

    async def revoke_pairing(self, device_id: str) -> bool:
        """Revoke a device pairing."""
        ...


# =============================================================================
# Security Adapters
# =============================================================================


@dataclass
class SecurityPolicy:
    """Security policy for a channel."""

    # DM policy: "pairing" (allowlist), "open", "disabled"
    dm_policy: str = "open"

    # Allowed user/group IDs (if dm_policy is "pairing")
    allow_from: list[str] | None = None

    # Require @mention in groups
    require_mention: bool = True

    # Access groups for command gating
    access_groups: dict[str, list[str]] | None = None


class ChannelSecurityAdapter(Protocol):
    """Handles channel security and access control.

    Responsible for:
    - Access control decisions
    - Rate limiting
    - Allowlist/blocklist management
    """

    def get_policy(self) -> SecurityPolicy:
        """Get current security policy."""
        ...

    def is_allowed(self, user_id: str, channel_id: str | None = None) -> bool:
        """Check if a user is allowed to interact."""
        ...

    def check_rate_limit(self, user_id: str) -> tuple[bool, int]:
        """Check rate limit. Returns (allowed, retry_after_seconds)."""
        ...

    async def add_to_allowlist(self, user_id: str) -> bool:
        """Add user to allowlist."""
        ...

    async def remove_from_allowlist(self, user_id: str) -> bool:
        """Remove user from allowlist."""
        ...


# =============================================================================
# Gateway Adapters
# =============================================================================


class ChannelGatewayAdapter(Protocol):
    """Handles gateway connection for the channel.

    Responsible for:
    - Connecting to the Clara gateway
    - Message routing
    - Connection lifecycle
    """

    async def connect(self, gateway_url: str) -> bool:
        """Connect to the gateway."""
        ...

    async def disconnect(self) -> None:
        """Disconnect from the gateway."""
        ...

    @property
    def is_connected(self) -> bool:
        """Check if connected to gateway."""
        ...

    async def send_to_gateway(self, context: "MsgContext") -> str:
        """Send a message to the gateway. Returns request ID."""
        ...


# =============================================================================
# Message Handling Adapters
# =============================================================================


@dataclass
class OutboundMessage:
    """Outbound message to send through a channel."""

    content: str
    channel_id: str
    thread_id: str | None = None
    reply_to: str | None = None
    attachments: list[dict[str, Any]] | None = None
    embeds: list[dict[str, Any]] | None = None
    components: list[dict[str, Any]] | None = None


class ChannelOutboundAdapter(Protocol):
    """Handles sending messages through the channel.

    Responsible for:
    - Message delivery
    - Attachment handling
    - Rich content formatting
    """

    async def send_message(self, message: OutboundMessage) -> Any:
        """Send a message. Returns platform message object."""
        ...

    async def edit_message(
        self, message_id: str, channel_id: str, new_content: str
    ) -> bool:
        """Edit an existing message."""
        ...

    async def delete_message(self, message_id: str, channel_id: str) -> bool:
        """Delete a message."""
        ...

    async def add_reaction(
        self, message_id: str, channel_id: str, emoji: str
    ) -> bool:
        """Add a reaction to a message."""
        ...


class ChannelMessagingAdapter(Protocol):
    """Handles inbound message processing.

    Responsible for:
    - Message normalization
    - Event handling
    - Message batching
    """

    def normalize_message(self, raw_message: Any) -> "MsgContext":
        """Normalize a platform message to MsgContext."""
        ...

    async def process_message(self, context: "MsgContext") -> None:
        """Process an incoming message."""
        ...

    def register_handler(
        self, event_type: str, handler: Callable[..., Any]
    ) -> None:
        """Register a message event handler."""
        ...


class ChannelStreamingAdapter(Protocol):
    """Handles streaming responses.

    Responsible for:
    - Typing indicators
    - Chunked message delivery
    - Progress updates
    """

    async def start_typing(self, channel_id: str) -> None:
        """Start typing indicator."""
        ...

    async def stop_typing(self, channel_id: str) -> None:
        """Stop typing indicator."""
        ...

    async def stream_response(
        self, channel_id: str, chunks: AsyncIterator[str]
    ) -> str:
        """Stream response chunks. Returns final message ID."""
        ...

    async def update_message(
        self, message_id: str, channel_id: str, content: str
    ) -> None:
        """Update a streaming message with new content."""
        ...


class ChannelThreadingAdapter(Protocol):
    """Handles message threading and replies.

    Responsible for:
    - Thread creation
    - Reply chain management
    - Thread metadata
    """

    async def create_thread(
        self, channel_id: str, message_id: str, name: str | None = None
    ) -> str:
        """Create a thread from a message. Returns thread ID."""
        ...

    async def get_thread_messages(
        self, thread_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Get messages in a thread."""
        ...

    async def reply_in_thread(
        self, thread_id: str, content: str
    ) -> Any:
        """Send a reply in a thread."""
        ...


# =============================================================================
# Status and Monitoring Adapters
# =============================================================================


@dataclass
class ChannelStatus:
    """Status information for a channel."""

    is_connected: bool = False
    is_healthy: bool = False
    latency_ms: int | None = None
    last_message_at: str | None = None
    error: str | None = None
    metadata: dict[str, Any] | None = None


class ChannelStatusAdapter(Protocol):
    """Handles channel status reporting.

    Responsible for:
    - Health checks
    - Connection status
    - Metrics collection
    """

    async def get_status(self) -> ChannelStatus:
        """Get current channel status."""
        ...

    async def run_health_check(self) -> tuple[bool, str]:
        """Run a health check. Returns (healthy, message)."""
        ...


class ChannelHeartbeatAdapter(Protocol):
    """Handles channel heartbeat/keep-alive.

    Responsible for:
    - Periodic health pings
    - Connection keep-alive
    - Reconnection triggers
    """

    async def start_heartbeat(self, interval_seconds: int = 30) -> None:
        """Start heartbeat loop."""
        ...

    async def stop_heartbeat(self) -> None:
        """Stop heartbeat loop."""
        ...

    async def on_heartbeat_failed(self) -> None:
        """Called when heartbeat fails."""
        ...


# =============================================================================
# Commands and Tools Adapters
# =============================================================================


@dataclass
class ChannelCommand:
    """A channel-specific command."""

    name: str
    description: str
    handler: Callable[..., Any]
    options: list[dict[str, Any]] | None = None
    permissions: list[str] | None = None


class ChannelCommandAdapter(Protocol):
    """Handles channel-specific commands.

    Responsible for:
    - Command registration
    - Command execution
    - Permission checking
    """

    def get_commands(self) -> list[ChannelCommand]:
        """Get all registered commands."""
        ...

    async def execute_command(
        self, command: str, args: dict[str, Any], context: "MsgContext"
    ) -> Any:
        """Execute a command."""
        ...

    def has_permission(
        self, command: str, user_id: str, context: "MsgContext"
    ) -> bool:
        """Check if user has permission for a command."""
        ...


class ChannelToolFactory(Protocol):
    """Factory for channel-specific agent tools.

    Responsible for:
    - Creating tools that interact with the channel
    - Platform-specific actions (reactions, embeds, etc.)
    """

    def create_tools(self) -> list[dict[str, Any]]:
        """Create agent tools for this channel.

        Returns tool definitions in the standard format:
        [{"name": "...", "description": "...", "parameters": {...}, "handler": callable}]
        """
        ...
