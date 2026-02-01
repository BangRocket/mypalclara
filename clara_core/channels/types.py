"""Core types for the channel plugin system.

Defines the ChannelPlugin interface and related types following OpenClaw's
plugin-first architecture. Each channel implements optional adapters for
different capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Generic, Protocol, TypeVar

if TYPE_CHECKING:
    from clara_core.channels.adapters import (
        ChannelCommandAdapter,
        ChannelConfigAdapter,
        ChannelGatewayAdapter,
        ChannelHeartbeatAdapter,
        ChannelMessagingAdapter,
        ChannelOutboundAdapter,
        ChannelPairingAdapter,
        ChannelSecurityAdapter,
        ChannelSetupAdapter,
        ChannelStatusAdapter,
        ChannelStreamingAdapter,
        ChannelThreadingAdapter,
        ChannelToolFactory,
    )


class ChannelId(str, Enum):
    """Known channel identifiers."""

    DISCORD = "discord"
    SLACK = "slack"
    TELEGRAM = "telegram"
    CLI = "cli"
    API = "api"
    MATRIX = "matrix"
    SIGNAL = "signal"
    WHATSAPP = "whatsapp"
    TEAMS = "teams"
    CUSTOM = "custom"


@dataclass
class ChannelMeta:
    """Metadata about a channel plugin.

    Provides display information and categorization for the channel.
    """

    # Human-readable name
    name: str

    # Short description of the channel
    description: str = ""

    # Icon identifier (emoji or icon name)
    icon: str = ""

    # Category for grouping (messaging, social, enterprise, etc.)
    category: str = "messaging"

    # Documentation URL
    docs_url: str | None = None

    # Whether this is a core channel vs extension
    is_core: bool = False

    # Version of the channel plugin
    version: str = "1.0.0"

    # Author information
    author: str | None = None


@dataclass
class ChannelCapabilities:
    """Declares what features a channel supports.

    Used for graceful degradation - if a capability is False,
    the system won't attempt to use that feature.
    """

    # Can receive incoming messages
    can_receive: bool = True

    # Can send outgoing messages
    can_send: bool = True

    # Supports streaming responses (typing indicators, chunked messages)
    streaming: bool = False

    # Supports message threading/replies
    threading: bool = False

    # Supports reactions/emoji
    reactions: bool = False

    # Supports file attachments
    attachments: bool = False

    # Supports inline images
    images: bool = False

    # Supports voice messages
    voice: bool = False

    # Supports rich embeds/cards
    embeds: bool = False

    # Supports buttons/interactive components
    components: bool = False

    # Supports slash commands
    slash_commands: bool = False

    # Supports presence/online status
    presence: bool = False

    # Supports typing indicators
    typing_indicator: bool = False

    # Supports message editing
    edit: bool = False

    # Supports message deletion
    delete: bool = False

    # Maximum message length (0 = unlimited)
    max_message_length: int = 0


@dataclass
class MsgContext:
    """Normalized message context.

    Provides a standardized format for incoming messages across all platforms.
    Platform-specific data is preserved in the metadata field.
    """

    # Unique message ID
    message_id: str

    # Channel identifier (ChannelId enum value)
    channel_type: ChannelId

    # Account/bot identifier for multi-account support
    account_id: str | None = None

    # Platform-specific channel/room ID
    channel_id: str | None = None

    # Thread/reply context ID
    thread_id: str | None = None

    # User information
    user_id: str = ""
    user_name: str | None = None
    user_display_name: str | None = None

    # Message content
    content: str = ""

    # Attachments (normalized format)
    attachments: list[dict[str, Any]] = field(default_factory=list)

    # Timestamp
    timestamp: datetime = field(default_factory=datetime.now)

    # Whether this is a direct message
    is_dm: bool = False

    # Whether the bot was mentioned
    is_mention: bool = False

    # Guild/server context (for Discord, Slack, etc.)
    guild_id: str | None = None
    guild_name: str | None = None

    # Platform-specific metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    # Original platform message object (for delegation)
    _original: Any = None


# Type variable for resolved account type
ResolvedAccount = TypeVar("ResolvedAccount")


class ChannelPlugin(Protocol, Generic[ResolvedAccount]):
    """Channel plugin interface.

    Each channel implements this protocol with optional adapters for
    different capabilities. Adapters are optional - if not provided,
    the corresponding feature is disabled for that channel.

    Example:
        class DiscordPlugin:
            id = ChannelId.DISCORD
            meta = ChannelMeta(name="Discord", icon="discord")
            capabilities = ChannelCapabilities(streaming=True, threading=True)

            config: DiscordConfigAdapter = ...
            gateway: DiscordGatewayAdapter = ...
            outbound: DiscordOutboundAdapter = ...
            streaming: DiscordStreamingAdapter = ...
    """

    # Required: Channel identifier
    id: ChannelId

    # Required: Channel metadata
    meta: ChannelMeta

    # Required: Declared capabilities
    capabilities: ChannelCapabilities

    # Optional adapters (~15 total, matching OpenClaw)
    # Configuration and setup
    config: "ChannelConfigAdapter | None"
    setup: "ChannelSetupAdapter | None"
    pairing: "ChannelPairingAdapter | None"

    # Security
    security: "ChannelSecurityAdapter | None"

    # Gateway connection
    gateway: "ChannelGatewayAdapter | None"

    # Message handling
    outbound: "ChannelOutboundAdapter | None"
    messaging: "ChannelMessagingAdapter | None"
    streaming: "ChannelStreamingAdapter | None"
    threading: "ChannelThreadingAdapter | None"

    # Status and monitoring
    status: "ChannelStatusAdapter | None"
    heartbeat: "ChannelHeartbeatAdapter | None"

    # Commands and tools
    commands: "ChannelCommandAdapter | None"
    agent_tools: "ChannelToolFactory | None"


@dataclass
class ChannelPluginImpl(Generic[ResolvedAccount]):
    """Concrete implementation of ChannelPlugin.

    Provides a base class for channel plugins with all adapters defaulting to None.
    Channels can override specific adapters as needed.
    """

    id: ChannelId
    meta: ChannelMeta
    capabilities: ChannelCapabilities

    # Optional adapters - all default to None
    config: "ChannelConfigAdapter | None" = None
    setup: "ChannelSetupAdapter | None" = None
    pairing: "ChannelPairingAdapter | None" = None
    security: "ChannelSecurityAdapter | None" = None
    gateway: "ChannelGatewayAdapter | None" = None
    outbound: "ChannelOutboundAdapter | None" = None
    messaging: "ChannelMessagingAdapter | None" = None
    streaming: "ChannelStreamingAdapter | None" = None
    threading: "ChannelThreadingAdapter | None" = None
    status: "ChannelStatusAdapter | None" = None
    heartbeat: "ChannelHeartbeatAdapter | None" = None
    commands: "ChannelCommandAdapter | None" = None
    agent_tools: "ChannelToolFactory | None" = None
