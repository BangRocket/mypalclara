"""Discord provider for Clara Gateway.

Implements the Strangler Fig pattern: wraps the existing ClaraDiscordBot
without rewriting its core logic. This allows gradual migration while
preserving all proven Discord bot functionality.

The provider:
1. Manages the Discord bot lifecycle (start/stop)
2. Normalizes Discord messages to PlatformMessage format
3. Provides send_response() for sending replies back through Discord
"""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, Any

from config.logging import get_logger
from gateway.providers.base import PlatformMessage, Provider

if TYPE_CHECKING:
    from discord import File as DiscordFile
    from discord import Message as DiscordMessage

    from discord_bot import ClaraDiscordBot

logger = get_logger("gateway.providers.discord")

# Timeout for waiting for bot to become ready
BOT_READY_TIMEOUT = 30.0  # seconds
BOT_READY_POLL_INTERVAL = 0.1  # seconds


class DiscordProvider(Provider):
    """Discord platform provider wrapping ClaraDiscordBot.

    Uses the Strangler Fig pattern to wrap the existing 4000+ line Discord bot
    without rewriting its core logic. This enables gradual migration to the
    gateway architecture while preserving all proven functionality.

    Lifecycle:
        1. Gateway calls start() - creates bot and starts in background
        2. Provider normalizes incoming Discord messages to PlatformMessage
        3. Gateway processes and calls send_response() with results
        4. Gateway calls stop() - gracefully shuts down bot

    Attributes:
        _bot: The wrapped ClaraDiscordBot instance (None until started)
        _bot_task: Background task running the bot's event loop
        _running: Whether the provider is currently running
    """

    def __init__(self) -> None:
        """Initialize the Discord provider.

        Does not start the bot - call start() to begin operation.
        """
        super().__init__()
        self._bot: ClaraDiscordBot | None = None
        self._bot_task: asyncio.Task[None] | None = None

    @property
    def name(self) -> str:
        """Return the provider identifier."""
        return "discord"

    @property
    def bot(self) -> ClaraDiscordBot | None:
        """Get the wrapped ClaraDiscordBot instance.

        Returns:
            The bot instance, or None if not started
        """
        return self._bot

    async def start(self) -> None:
        """Start the Discord bot in provider mode.

        Creates a ClaraDiscordBot instance and starts it in a background task.
        Waits for the bot to become ready before returning.

        Raises:
            RuntimeError: If DISCORD_BOT_TOKEN is not set
            TimeoutError: If bot doesn't become ready within timeout
        """
        if self._running:
            logger.debug("DiscordProvider already running")
            return

        # Get token from environment
        token = os.getenv("DISCORD_BOT_TOKEN")
        if not token:
            raise RuntimeError(
                "DISCORD_BOT_TOKEN environment variable is required for Discord provider"
            )

        # Import here to avoid circular imports and allow the module
        # to be imported even when discord.py is not installed
        from discord_bot import ClaraDiscordBot

        logger.info("Starting Discord provider...")

        # Create bot instance
        self._bot = ClaraDiscordBot()
        self._bot._provider_mode = True

        # Start bot in background task
        self._bot_task = asyncio.create_task(
            self._bot.start_for_provider(token),
            name="discord-bot-provider",
        )

        # Wait for bot to become ready with timeout
        elapsed = 0.0
        while elapsed < BOT_READY_TIMEOUT:
            if self._bot.is_ready_for_provider():
                self._running = True
                logger.info(
                    f"Discord provider started successfully "
                    f"(ready in {elapsed:.1f}s)"
                )
                return
            await asyncio.sleep(BOT_READY_POLL_INTERVAL)
            elapsed += BOT_READY_POLL_INTERVAL

            # Check if bot task failed
            if self._bot_task.done():
                exc = self._bot_task.exception()
                if exc:
                    raise RuntimeError(f"Discord bot failed to start: {exc}") from exc

        # Timeout reached
        await self._cleanup()
        raise TimeoutError(
            f"Discord bot did not become ready within {BOT_READY_TIMEOUT}s"
        )

    async def stop(self) -> None:
        """Stop the Discord bot gracefully.

        Calls the bot's stop_for_provider() method and cleans up resources.
        Safe to call multiple times.
        """
        if not self._running and self._bot is None:
            logger.debug("DiscordProvider not running, nothing to stop")
            return

        logger.info("Stopping Discord provider...")
        self._running = False

        await self._cleanup()
        logger.info("Discord provider stopped")

    async def _cleanup(self) -> None:
        """Clean up bot resources."""
        # Stop the bot if it exists
        if self._bot is not None:
            try:
                await self._bot.stop_for_provider()
            except Exception as e:
                logger.warning(f"Error during bot shutdown: {e}")

        # Cancel the background task if running
        if self._bot_task is not None and not self._bot_task.done():
            self._bot_task.cancel()
            try:
                await self._bot_task
            except asyncio.CancelledError:
                pass

        self._bot = None
        self._bot_task = None

    def normalize_message(self, discord_msg: DiscordMessage) -> PlatformMessage:
        """Convert a Discord Message to normalized PlatformMessage format.

        Follows the pattern from adapters/discord/adapter.py for consistency.

        Args:
            discord_msg: The Discord Message object to normalize

        Returns:
            PlatformMessage with all fields populated from the Discord message
        """
        is_dm = discord_msg.guild is None

        # Build attachments list
        attachments = []
        for attachment in discord_msg.attachments:
            attachments.append(
                {
                    "filename": attachment.filename,
                    "url": attachment.url,
                    "size": attachment.size,
                    "content_type": attachment.content_type,
                }
            )

        return PlatformMessage(
            user_id=self.format_user_id(str(discord_msg.author.id)),
            platform="discord",
            platform_user_id=str(discord_msg.author.id),
            content=discord_msg.content,
            channel_id=str(discord_msg.channel.id),
            thread_id=str(discord_msg.channel.id),  # Use channel as thread for now
            user_name=discord_msg.author.name,
            user_display_name=discord_msg.author.display_name,
            attachments=attachments,
            timestamp=discord_msg.created_at,
            metadata={
                "is_dm": is_dm,
                "guild_id": str(discord_msg.guild.id) if discord_msg.guild else None,
                "guild_name": discord_msg.guild.name if discord_msg.guild else None,
                "message_id": str(discord_msg.id),
                "channel_name": getattr(discord_msg.channel, "name", "DM"),
                "_discord_message": discord_msg,  # Preserve original for delegation
            },
        )

    async def send_response(
        self,
        context: dict[str, Any],
        content: str,
        files: list[str] | None = None,
    ) -> None:
        """Send a response back through Discord.

        Args:
            context: Dict containing at minimum a "channel" key with the
                Discord channel to send to. May also contain "message_id"
                for threading.
            content: The text content to send
            files: Optional list of file paths to attach

        Raises:
            ValueError: If context doesn't contain required "channel" key
            Exception: If Discord API call fails
        """
        channel = context.get("channel")
        if channel is None:
            raise ValueError("context must contain 'channel' key with Discord channel")

        # Convert file paths to Discord File objects if needed
        discord_files: list[DiscordFile] | None = None
        if files:
            import discord

            discord_files = []
            for file_path in files:
                try:
                    discord_files.append(discord.File(file_path))
                except Exception as e:
                    logger.warning(f"Failed to attach file {file_path}: {e}")

        # Send the message
        await channel.send(content, files=discord_files or [])

    def __repr__(self) -> str:
        """Return string representation of the provider."""
        bot_status = "connected" if self._bot and self._bot.is_ready() else "disconnected"
        return (
            f"<DiscordProvider(running={self._running}, "
            f"bot_status={bot_status})>"
        )
