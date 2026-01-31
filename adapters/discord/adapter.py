"""Discord adapter for Clara.

Implements the Strangler Fig pattern: this adapter wraps the existing ClaraDiscordBot,
providing a PlatformAdapter interface while delegating to the proven existing code.
This allows gradual migration from Discord-specific code to platform-agnostic abstractions.

The adapter:
1. Converts Discord-native objects (Message, User, Channel) to platform-agnostic dataclasses
2. Provides the PlatformAdapter interface for the core to interact with
3. Delegates actual message handling to the existing bot implementation
"""

from __future__ import annotations

import logging
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

    Attributes:
        _bot: Reference to the ClaraDiscordBot instance
    """

    def __init__(self, bot: Any) -> None:
        """Initialize the Discord adapter.

        Args:
            bot: The ClaraDiscordBot instance to wrap
        """
        self._bot = bot
        logger.debug("DiscordAdapter initialized")

    @property
    def platform_name(self) -> str:
        """Return the platform identifier."""
        return "discord"

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

        Args:
            message: The platform message to handle

        Returns:
            None (response is sent directly via Discord by the bot)
        """
        discord_msg = message.metadata.get("_discord_message")
        if discord_msg is None:
            logger.error("Cannot handle message: no _discord_message in metadata")
            return None

        is_dm = message.metadata.get("is_dm", False)

        # Delegate to existing bot implementation
        await self._bot._handle_message(discord_msg, is_dm=is_dm)
        return None
