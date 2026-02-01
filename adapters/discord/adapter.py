"""Discord adapter for Clara.

Implements the Strangler Fig pattern: this adapter wraps the existing ClaraDiscordBot,
providing a PlatformAdapter interface while delegating to the proven existing code.
This allows gradual migration from Discord-specific code to platform-agnostic abstractions.

The adapter:
1. Converts Discord-native objects (Message, User, Channel) to platform-agnostic dataclasses
2. Provides the PlatformAdapter interface for the core to interact with
3. Delegates actual message handling to the existing bot implementation
4. Can optionally route through the gateway for cognition pipeline processing

Gateway Integration:
    When DISCORD_USE_GATEWAY=true, the adapter connects to the Clara gateway
    and routes messages through the cognition pipeline for processing.
    This provides rate-limited tool execution and unified message handling.

    Without gateway mode, messages are handled by the existing bot implementation
    with direct LLM calls and tool execution.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

from clara_core.platform import PlatformAdapter, PlatformContext, PlatformMessage

if TYPE_CHECKING:
    import discord

logger = logging.getLogger("discord.adapter")


class DiscordAdapter(PlatformAdapter):
    """Discord platform adapter implementing the Strangler Fig pattern.

    Wraps the existing ClaraDiscordBot to provide a PlatformAdapter interface
    while preserving all existing functionality. As more features are migrated
    to the platform-agnostic core, this adapter can be simplified.

    Gateway Integration:
        When DISCORD_USE_GATEWAY is set, messages can be routed through the
        Clara gateway for processing via the cognition pipeline. This provides:
        - Rate-limited tool execution (10 per-request, 20 per-minute)
        - Unified message processing across platforms
        - Centralized context and memory management

    Attributes:
        _bot: Reference to the ClaraDiscordBot instance
        _use_gateway: Whether to route through gateway
    """

    def __init__(self, bot: Any) -> None:
        """Initialize the Discord adapter.

        Args:
            bot: The ClaraDiscordBot instance to wrap
        """
        self._bot = bot
        self._use_gateway = os.getenv("DISCORD_USE_GATEWAY", "").lower() in (
            "true",
            "1",
            "yes",
        )
        if self._use_gateway:
            logger.info("DiscordAdapter: Gateway mode enabled")
        else:
            logger.debug("DiscordAdapter initialized (legacy mode)")

    @property
    def platform_name(self) -> str:
        """Return the platform identifier."""
        return "discord"

    @property
    def use_gateway(self) -> bool:
        """Whether gateway routing is enabled."""
        return self._use_gateway

    def message_to_platform(self, msg: discord.Message) -> PlatformMessage:
        """Convert a Discord Message to a PlatformMessage.

        Args:
            msg: Discord Message object

        Returns:
            PlatformMessage with converted data and Discord-specific metadata
        """
        is_dm = msg.guild is None

        return PlatformMessage(
            user_id=self.format_user_id(str(msg.author.id)),
            platform="discord",
            platform_user_id=str(msg.author.id),
            content=msg.content,
            channel_id=str(msg.channel.id),
            user_name=msg.author.name,
            user_display_name=msg.author.display_name,
            timestamp=msg.created_at,
            metadata={
                "is_dm": is_dm,
                "guild_id": str(msg.guild.id) if msg.guild else None,
                "guild_name": msg.guild.name if msg.guild else None,
                "message_id": str(msg.id),
                "_discord_message": msg,  # Preserve original for delegation
            },
        )

    def context_from_message(self, msg: discord.Message) -> PlatformContext:
        """Create a PlatformContext from a Discord Message.

        Args:
            msg: Discord Message object

        Returns:
            PlatformContext with Discord channel, user, and message references
        """
        return PlatformContext(
            platform="discord",
            channel=msg.channel,
            user=msg.author,
            message=msg,
            guild_id=str(msg.guild.id) if msg.guild else None,
            guild_name=msg.guild.name if msg.guild else None,
            channel_name=getattr(msg.channel, "name", "DM"),
        )

    def to_gateway_request(self, msg: discord.Message) -> dict[str, Any]:
        """Convert a Discord message to a gateway MessageRequest dict.

        This format matches the gateway protocol for routing messages
        through the cognition pipeline.

        Args:
            msg: Discord Message object

        Returns:
            Dict matching MessageRequest schema for gateway protocol
        """
        is_dm = msg.guild is None

        return {
            "type": "message",
            "id": f"discord-{msg.id}",
            "user": {
                "id": f"discord-{msg.author.id}",
                "platform_id": str(msg.author.id),
                "name": msg.author.name,
                "display_name": msg.author.display_name,
            },
            "channel": {
                "id": str(msg.channel.id),
                "type": "dm" if is_dm else "server",
                "name": getattr(msg.channel, "name", None),
                "guild_id": str(msg.guild.id) if msg.guild else None,
                "guild_name": msg.guild.name if msg.guild else None,
            },
            "content": msg.content,
            "attachments": [],  # TODO: Convert Discord attachments
            "reply_chain": [],  # TODO: Build reply chain from referenced messages
            "tier_override": None,  # TODO: Extract from message prefix
            "metadata": {
                "platform": "discord",
                "message_id": str(msg.id),
                "is_dm": is_dm,
            },
        }

    async def send_message(
        self,
        context: PlatformContext,
        content: str,
        files: list[Any] | None = None,
    ) -> Any:
        """Send a message through Discord.

        Args:
            context: The platform context containing the Discord channel
            content: The message content to send
            files: Optional list of discord.File objects to attach

        Returns:
            The sent discord.Message object
        """
        if context.channel is None:
            logger.error("Cannot send message: no channel in context")
            return None

        return await context.channel.send(content, files=files or [])

    async def send_typing_indicator(self, context: PlatformContext) -> None:
        """Show a typing indicator in the Discord channel.

        Args:
            context: The platform context containing the Discord channel
        """
        if context.channel is None:
            logger.warning("Cannot send typing indicator: no channel in context")
            return

        await context.channel.trigger_typing()

    async def handle_message(self, message: PlatformMessage) -> str | None:
        """Handle an incoming message by delegating to the bot.

        Implements the Strangler Fig pattern by extracting the original Discord
        message from metadata and delegating to the existing bot._handle_message.

        When DISCORD_USE_GATEWAY is enabled, this method should not be called
        directly - messages should be routed through the gateway client instead.

        Args:
            message: The platform message to handle

        Returns:
            None (response is sent directly via Discord by the bot)
        """
        if self._use_gateway:
            logger.warning(
                "handle_message called in gateway mode - "
                "messages should be routed through gateway client"
            )

        discord_msg = message.metadata.get("_discord_message")
        if discord_msg is None:
            logger.error("Cannot handle message: no _discord_message in metadata")
            return None

        is_dm = message.metadata.get("is_dm", False)

        # Delegate to existing bot implementation
        await self._bot._handle_message(discord_msg, is_dm=is_dm)
        return None
