"""Standalone Discord adapter for the Clara Gateway.

This runs the Discord bot as a thin client that connects to the gateway
for all message processing.

Usage:
    poetry run python -m adapters.discord

Environment variables:
    DISCORD_BOT_TOKEN - Discord bot token (required)
    CLARA_GATEWAY_URL - Gateway WebSocket URL (default: ws://127.0.0.1:18789)
    USE_GATEWAY - Must be "true" to use gateway mode
"""

from __future__ import annotations

import asyncio
import os
import re
import signal
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import discord
from discord.ext import commands as discord_commands

from adapters.discord.channel_modes import get_channel_mode
from adapters.discord.gateway_client import DiscordGatewayClient
from adapters.discord.voice import VoiceManager
from clara_core.config import get_settings
from clara_core.discord import setup as setup_slash_commands
from config.logging import get_logger, init_logging

init_logging()
logger = get_logger("adapters.discord")

# Configuration
_settings = get_settings()
BOT_TOKEN = _settings.discord.bot_token
GATEWAY_URL = _settings.gateway.url
STOP_PHRASES = [p.strip().lower() for p in _settings.discord.stop_phrases.split(",")]

# Intents for Discord
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.voice_states = True


class GatewayDiscordBot(discord_commands.Bot):
    """Discord bot that uses the gateway for processing."""

    def __init__(self) -> None:
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
        )
        self.gateway_client: DiscordGatewayClient | None = None
        self.voice_manager: VoiceManager | None = None
        self._gateway_task: asyncio.Task | None = None
        self._commands_synced: bool = False

    async def setup_hook(self) -> None:
        """Called when the bot is ready to start.

        Note: Pycord does not call this method automatically like discord.py does.
        Gateway initialization is done in on_ready() instead for compatibility.
        """
        pass

    async def _run_gateway(self) -> None:
        """Run the gateway client."""
        try:
            await self.gateway_client.start()
        except Exception as e:
            logger.exception(f"Gateway client error: {e}")

    async def on_ready(self) -> None:
        """Called when Discord connection is established."""
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Gateway: {GATEWAY_URL}")
        logger.info(f"Guilds: {len(self.guilds)}")

        # Register and sync slash commands (only once)
        # See: https://github.com/BangRocket/mypalclara/issues/136
        if not self._commands_synced:
            try:
                setup_slash_commands(self)
                logger.info("Slash commands cog registered")

                # Use guild-specific sync for instant visibility
                guild_ids = [guild.id for guild in self.guilds]
                await self.sync_commands(guild_ids=guild_ids)
                cmd_count = len(self.pending_application_commands or [])
                logger.info(f"Synced {cmd_count} slash commands to {len(guild_ids)} guilds")
                self._commands_synced = True
            except Exception as e:
                logger.warning(f"Failed to sync slash commands: {e}")

        # Initialize gateway client if not already done
        # Note: This is done here instead of setup_hook() because Pycord
        # does not call setup_hook() automatically like discord.py does.
        # See: https://github.com/BangRocket/mypalclara/issues/132
        if self.gateway_client is None:
            self.gateway_client = DiscordGatewayClient(
                bot=self,
                gateway_url=GATEWAY_URL,
            )
            self._gateway_task = asyncio.create_task(self._run_gateway())
            logger.info("Gateway client initialized")

            # Initialize voice manager
            self.voice_manager = VoiceManager(self, self.gateway_client)
            self.gateway_client.voice_manager = self.voice_manager
            logger.info("Voice manager initialized")

    async def on_message(self, message: discord.Message) -> None:
        """Handle incoming Discord messages."""
        # Ignore own messages
        if message.author == self.user:
            return

        # Ignore bots
        if message.author.bot:
            return

        # Check if mentioned or in DM
        is_dm = message.guild is None
        is_mention = self.user in message.mentions if self.user else False

        # Get channel mode
        channel_id = str(message.channel.id)
        channel_mode = get_channel_mode(channel_id)

        # Check for stop phrase
        content_lower = message.content.lower().strip()
        if is_mention and any(phrase in content_lower for phrase in STOP_PHRASES):
            await self._handle_stop(message)
            return

        # Determine if we should respond based on channel mode
        should_respond = False
        if is_dm:
            should_respond = True
        elif is_mention:
            should_respond = channel_mode != "off"
        elif channel_mode == "active":
            should_respond = True

        if not should_respond:
            return

        # Check if gateway is connected
        if not self.gateway_client or not self.gateway_client.is_connected:
            logger.warning("Gateway not connected, skipping message")
            return

        # Detect tier override from message
        tier_override = self._detect_tier(message.content)

        # Send to gateway
        try:
            await self.gateway_client.send_discord_message(
                message=message,
                tier_override=tier_override,
            )
        except Exception as e:
            logger.exception(f"Failed to send to gateway: {e}")
            await message.reply(
                "Sorry, I'm having trouble connecting right now.",
                mention_author=False,
            )

    async def _handle_stop(self, message: discord.Message) -> None:
        """Handle a stop phrase to cancel current processing.

        Args:
            message: The message containing the stop phrase
        """
        logger.info(f"Stop phrase detected from {message.author.id}")

        # Cancel any pending requests for this channel
        if self.gateway_client:
            channel_id = str(message.channel.id)
            cancelled = self.gateway_client.cancel_pending_for_channel(channel_id)
            if cancelled:
                await message.add_reaction("🛑")
                logger.info(f"Cancelled {len(cancelled)} pending requests")
            else:
                await message.add_reaction("👌")  # Nothing to cancel

    def _detect_tier(self, content: str) -> str | None:
        """Detect tier override from message prefix."""
        content_lower = content.lower().strip()

        tier_prefixes = {
            "!high": "high",
            "!opus": "high",
            "!mid": "mid",
            "!sonnet": "mid",
            "!low": "low",
            "!haiku": "low",
            "!fast": "low",
        }

        for prefix, tier in tier_prefixes.items():
            if content_lower.startswith(prefix):
                return tier

        return None

    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        """Handle voice state changes for voice session management."""
        if self.voice_manager:
            await self.voice_manager.handle_voice_state_update(member, before, after)

    async def close(self) -> None:
        """Clean shutdown."""
        # Leave all voice sessions
        if self.voice_manager:
            for guild_id in list(self.voice_manager.sessions):
                await self.voice_manager.leave(guild_id)
        if self.gateway_client:
            await self.gateway_client.disconnect()
        if self._gateway_task:
            self._gateway_task.cancel()
        await super().close()


async def main() -> None:
    """Run the gateway-connected Discord bot."""
    if not BOT_TOKEN:
        logger.error("DISCORD_BOT_TOKEN not set")
        sys.exit(1)

    bot = GatewayDiscordBot()

    # Set up signal handlers
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def signal_handler():
        logger.info("Received shutdown signal")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    # Start bot
    try:
        async with bot:
            await asyncio.gather(
                bot.start(BOT_TOKEN),
                stop_event.wait(),
            )
    except Exception as e:
        logger.exception(f"Bot error: {e}")
    finally:
        if not bot.is_closed():
            await bot.close()

    logger.info("Bot stopped")

    # Use os._exit() to skip Python's async generator finalization phase
    # which causes noisy errors from MCP stdio_client cleanup
    os._exit(0)


def run() -> None:
    """Sync entry point for poetry scripts."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
