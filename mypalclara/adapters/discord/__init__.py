"""Discord adapter package.

Provides the DiscordAdapter class that implements the PlatformAdapter interface
for Discord integration, and DiscordGatewayClient for connecting to the gateway.

Module structure:
- adapter.py: PlatformAdapter implementation
- gateway_client.py: Gateway connection and message handling
- message_builder.py: Message formatting and splitting
- attachment_handler.py: Image/file processing
- channel_modes.py: Channel mode management
- main.py: Standalone bot entry point
"""

from adapters.discord.adapter import DiscordAdapter
from adapters.discord.attachment_handler import (
    extract_attachments,
    is_image_file,
    is_text_file,
)
from adapters.discord.channel_modes import (
    ChannelModeManager,
    get_channel_mode,
    set_channel_mode,
)
from adapters.discord.gateway_client import DiscordGatewayClient
from adapters.discord.message_builder import (
    DISCORD_MSG_LIMIT,
    clean_content,
    format_response,
    split_message,
)

__all__ = [
    # Main classes
    "DiscordAdapter",
    "DiscordGatewayClient",
    "ChannelModeManager",
    # Message building
    "DISCORD_MSG_LIMIT",
    "clean_content",
    "format_response",
    "split_message",
    # Attachment handling
    "extract_attachments",
    "is_image_file",
    "is_text_file",
    # Channel modes
    "get_channel_mode",
    "set_channel_mode",
]
