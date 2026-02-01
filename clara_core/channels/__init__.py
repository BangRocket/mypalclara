"""Clara Channel Plugin System.

Provides a unified abstraction for messaging platforms following the OpenClaw
channel plugin architecture. Each channel implements optional adapters for
different capabilities (streaming, threading, outbound messages, etc.).

This allows:
- Consistent interface across all platforms (Discord, Slack, Telegram, etc.)
- Graceful degradation when adapters aren't implemented
- Third-party channel development
- Feature parity across platforms
"""

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
from clara_core.channels.registry import ChannelRegistry, get_channel_registry
from clara_core.channels.types import (
    ChannelCapabilities,
    ChannelId,
    ChannelMeta,
    ChannelPlugin,
    MsgContext,
)

__all__ = [
    # Types
    "ChannelId",
    "ChannelMeta",
    "ChannelCapabilities",
    "ChannelPlugin",
    "MsgContext",
    # Adapters
    "ChannelConfigAdapter",
    "ChannelSetupAdapter",
    "ChannelPairingAdapter",
    "ChannelSecurityAdapter",
    "ChannelGatewayAdapter",
    "ChannelOutboundAdapter",
    "ChannelStatusAdapter",
    "ChannelCommandAdapter",
    "ChannelStreamingAdapter",
    "ChannelThreadingAdapter",
    "ChannelMessagingAdapter",
    "ChannelHeartbeatAdapter",
    "ChannelToolFactory",
    # Registry
    "ChannelRegistry",
    "get_channel_registry",
]
