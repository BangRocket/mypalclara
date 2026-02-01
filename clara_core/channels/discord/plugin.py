"""Discord channel plugin implementation.

Implements ChannelPlugin with Discord-specific adapters.
Uses discord.py library for Discord API interaction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from clara_core.channels.adapters import (
    ChannelGatewayAdapter,
    ChannelMessagingAdapter,
    ChannelOutboundAdapter,
    ChannelStatus,
    ChannelStatusAdapter,
    ChannelStreamingAdapter,
    ChannelThreadingAdapter,
    OutboundMessage,
)
from clara_core.channels.types import (
    ChannelCapabilities,
    ChannelId,
    ChannelMeta,
    ChannelPluginImpl,
    MsgContext,
)
from config.logging import get_logger

if TYPE_CHECKING:
    import discord

    from adapters.base import GatewayClient

logger = get_logger("channels.discord")


# =============================================================================
# Discord-specific Adapters
# =============================================================================


@dataclass
class DiscordAccount:
    """Resolved Discord bot account."""

    bot_id: str
    bot_name: str
    guilds: list[str]


class DiscordGatewayAdapter:
    """Gateway adapter for Discord.

    Handles connection to the Clara gateway for message processing.
    """

    def __init__(self) -> None:
        self._client: "GatewayClient | None" = None
        self._connected = False

    async def connect(self, gateway_url: str) -> bool:
        """Connect to the Clara gateway."""
        from adapters.discord.gateway_client import DiscordGatewayClient

        try:
            self._client = DiscordGatewayClient()
            self._client.gateway_url = gateway_url
            await self._client.connect()
            self._connected = True
            logger.info("Discord connected to gateway")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to gateway: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from the gateway."""
        if self._client:
            await self._client.disconnect()
            self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if connected to gateway."""
        return self._connected

    async def send_to_gateway(self, context: MsgContext) -> str:
        """Send a message to the gateway."""
        if not self._client:
            raise RuntimeError("Not connected to gateway")

        from gateway.protocol import ChannelInfo, UserInfo

        user = UserInfo(
            id=context.user_id,
            name=context.user_name or context.user_id,
            display_name=context.user_display_name,
        )
        channel = ChannelInfo(
            id=context.channel_id or "unknown",
            name=context.metadata.get("channel_name", ""),
            type="dm" if context.is_dm else "guild",
        )

        return await self._client.send_message(
            user=user,
            channel=channel,
            content=context.content,
            attachments=[],  # TODO: Convert attachments
            metadata=context.metadata,
        )


class DiscordMessagingAdapter:
    """Messaging adapter for Discord.

    Handles incoming message normalization and processing.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Any]] = {}

    def normalize_message(self, raw_message: "discord.Message") -> MsgContext:
        """Normalize a Discord message to MsgContext."""
        is_dm = raw_message.guild is None

        return MsgContext(
            message_id=str(raw_message.id),
            channel_type=ChannelId.DISCORD,
            channel_id=str(raw_message.channel.id),
            user_id=str(raw_message.author.id),
            user_name=raw_message.author.name,
            user_display_name=raw_message.author.display_name,
            content=raw_message.content,
            timestamp=raw_message.created_at,
            is_dm=is_dm,
            is_mention=bool(raw_message.mentions),  # Simplified
            guild_id=str(raw_message.guild.id) if raw_message.guild else None,
            guild_name=raw_message.guild.name if raw_message.guild else None,
            metadata={
                "channel_name": getattr(raw_message.channel, "name", "DM"),
                "attachments": [
                    {"url": a.url, "filename": a.filename, "content_type": a.content_type}
                    for a in raw_message.attachments
                ],
            },
            _original=raw_message,
        )

    async def process_message(self, context: MsgContext) -> None:
        """Process an incoming message."""
        handlers = self._handlers.get("message", [])
        for handler in handlers:
            await handler(context)

    def register_handler(self, event_type: str, handler: Any) -> None:
        """Register a message event handler."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)


class DiscordOutboundAdapter:
    """Outbound adapter for Discord.

    Handles sending messages, editing, deleting, and reactions.
    """

    def __init__(self, bot: "discord.Client | None" = None) -> None:
        self._bot = bot

    def set_bot(self, bot: "discord.Client") -> None:
        """Set the Discord bot client."""
        self._bot = bot

    async def send_message(self, message: OutboundMessage) -> Any:
        """Send a message to Discord."""
        if not self._bot:
            raise RuntimeError("Discord bot not initialized")

        channel = self._bot.get_channel(int(message.channel_id))
        if not channel:
            logger.error(f"Channel not found: {message.channel_id}")
            return None

        # Build kwargs
        kwargs: dict[str, Any] = {"content": message.content}

        if message.reply_to:
            # TODO: Fetch message reference
            pass

        if message.embeds:
            import discord
            kwargs["embeds"] = [
                discord.Embed.from_dict(e) for e in message.embeds
            ]

        return await channel.send(**kwargs)

    async def edit_message(
        self, message_id: str, channel_id: str, new_content: str
    ) -> bool:
        """Edit an existing message."""
        if not self._bot:
            return False

        try:
            channel = self._bot.get_channel(int(channel_id))
            if not channel:
                return False
            message = await channel.fetch_message(int(message_id))
            await message.edit(content=new_content)
            return True
        except Exception as e:
            logger.error(f"Failed to edit message: {e}")
            return False

    async def delete_message(self, message_id: str, channel_id: str) -> bool:
        """Delete a message."""
        if not self._bot:
            return False

        try:
            channel = self._bot.get_channel(int(channel_id))
            if not channel:
                return False
            message = await channel.fetch_message(int(message_id))
            await message.delete()
            return True
        except Exception as e:
            logger.error(f"Failed to delete message: {e}")
            return False

    async def add_reaction(
        self, message_id: str, channel_id: str, emoji: str
    ) -> bool:
        """Add a reaction to a message."""
        if not self._bot:
            return False

        try:
            channel = self._bot.get_channel(int(channel_id))
            if not channel:
                return False
            message = await channel.fetch_message(int(message_id))
            await message.add_reaction(emoji)
            return True
        except Exception as e:
            logger.error(f"Failed to add reaction: {e}")
            return False


class DiscordStreamingAdapter:
    """Streaming adapter for Discord.

    Handles typing indicators and streaming message updates.
    """

    def __init__(self, bot: "discord.Client | None" = None) -> None:
        self._bot = bot
        self._typing_channels: set[str] = set()

    def set_bot(self, bot: "discord.Client") -> None:
        """Set the Discord bot client."""
        self._bot = bot

    async def start_typing(self, channel_id: str) -> None:
        """Start typing indicator."""
        if not self._bot:
            return

        try:
            channel = self._bot.get_channel(int(channel_id))
            if channel:
                await channel.trigger_typing()
                self._typing_channels.add(channel_id)
        except Exception as e:
            logger.debug(f"Failed to start typing: {e}")

    async def stop_typing(self, channel_id: str) -> None:
        """Stop typing indicator."""
        self._typing_channels.discard(channel_id)

    async def stream_response(
        self, channel_id: str, chunks: Any
    ) -> str:
        """Stream response chunks by editing a message."""
        if not self._bot:
            raise RuntimeError("Discord bot not initialized")

        channel = self._bot.get_channel(int(channel_id))
        if not channel:
            raise RuntimeError(f"Channel not found: {channel_id}")

        # Send initial message
        message = await channel.send("...")
        content = ""

        async for chunk in chunks:
            content += chunk
            # Update message every few chunks to avoid rate limiting
            if len(content) % 100 < len(chunk):
                await message.edit(content=content[:2000])

        # Final update
        await message.edit(content=content[:2000])
        return str(message.id)

    async def update_message(
        self, message_id: str, channel_id: str, content: str
    ) -> None:
        """Update a streaming message."""
        if not self._bot:
            return

        try:
            channel = self._bot.get_channel(int(channel_id))
            if channel:
                message = await channel.fetch_message(int(message_id))
                await message.edit(content=content[:2000])
        except Exception as e:
            logger.debug(f"Failed to update message: {e}")


class DiscordThreadingAdapter:
    """Threading adapter for Discord.

    Handles thread creation and replies.
    """

    def __init__(self, bot: "discord.Client | None" = None) -> None:
        self._bot = bot

    def set_bot(self, bot: "discord.Client") -> None:
        """Set the Discord bot client."""
        self._bot = bot

    async def create_thread(
        self, channel_id: str, message_id: str, name: str | None = None
    ) -> str:
        """Create a thread from a message."""
        if not self._bot:
            raise RuntimeError("Discord bot not initialized")

        channel = self._bot.get_channel(int(channel_id))
        if not channel:
            raise RuntimeError(f"Channel not found: {channel_id}")

        message = await channel.fetch_message(int(message_id))
        thread = await message.create_thread(name=name or "Thread")
        return str(thread.id)

    async def get_thread_messages(
        self, thread_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Get messages in a thread."""
        if not self._bot:
            return []

        thread = self._bot.get_channel(int(thread_id))
        if not thread:
            return []

        messages = []
        async for msg in thread.history(limit=limit):
            messages.append({
                "id": str(msg.id),
                "content": msg.content,
                "author_id": str(msg.author.id),
                "author_name": msg.author.name,
                "timestamp": msg.created_at.isoformat(),
            })
        return messages

    async def reply_in_thread(self, thread_id: str, content: str) -> Any:
        """Send a reply in a thread."""
        if not self._bot:
            raise RuntimeError("Discord bot not initialized")

        thread = self._bot.get_channel(int(thread_id))
        if not thread:
            raise RuntimeError(f"Thread not found: {thread_id}")

        return await thread.send(content)


class DiscordStatusAdapter:
    """Status adapter for Discord.

    Provides health checks and status reporting.
    """

    def __init__(self, bot: "discord.Client | None" = None) -> None:
        self._bot = bot
        self._last_message_at: str | None = None

    def set_bot(self, bot: "discord.Client") -> None:
        """Set the Discord bot client."""
        self._bot = bot

    def update_last_message(self) -> None:
        """Update last message timestamp."""
        from datetime import datetime
        self._last_message_at = datetime.now().isoformat()

    async def get_status(self) -> ChannelStatus:
        """Get current channel status."""
        if not self._bot:
            return ChannelStatus(
                is_connected=False,
                is_healthy=False,
                error="Bot not initialized",
            )

        is_connected = not self._bot.is_closed()
        latency_ms = int(self._bot.latency * 1000) if is_connected else None

        return ChannelStatus(
            is_connected=is_connected,
            is_healthy=is_connected and (latency_ms or 0) < 5000,
            latency_ms=latency_ms,
            last_message_at=self._last_message_at,
            metadata={
                "guilds": len(self._bot.guilds) if is_connected else 0,
                "user": str(self._bot.user) if self._bot.user else None,
            },
        )

    async def run_health_check(self) -> tuple[bool, str]:
        """Run a health check."""
        status = await self.get_status()
        if not status.is_connected:
            return False, "Bot is not connected to Discord"
        if not status.is_healthy:
            return False, f"High latency: {status.latency_ms}ms"
        return True, f"Healthy, latency: {status.latency_ms}ms"


# =============================================================================
# Discord Plugin
# =============================================================================


class DiscordPlugin(ChannelPluginImpl[DiscordAccount]):
    """Discord channel plugin.

    Provides full Discord integration including:
    - Streaming responses with typing indicators
    - Thread/reply support
    - Rich embeds
    - Slash commands
    - File attachments
    - Reactions
    """

    def __init__(self, bot: "discord.Client | None" = None) -> None:
        """Initialize the Discord plugin.

        Args:
            bot: Optional Discord client. If not provided, adapters that
                 need it won't work until set_bot() is called.
        """
        super().__init__(
            id=ChannelId.DISCORD,
            meta=ChannelMeta(
                name="Discord",
                description="Discord chat platform integration",
                icon="discord",
                category="messaging",
                is_core=True,
                version="1.0.0",
            ),
            capabilities=ChannelCapabilities(
                can_receive=True,
                can_send=True,
                streaming=True,
                threading=True,
                reactions=True,
                attachments=True,
                images=True,
                embeds=True,
                components=True,
                slash_commands=True,
                presence=True,
                typing_indicator=True,
                edit=True,
                delete=True,
                max_message_length=2000,
            ),
        )

        # Initialize adapters
        self.gateway = DiscordGatewayAdapter()
        self.messaging = DiscordMessagingAdapter()
        self.outbound = DiscordOutboundAdapter(bot)
        self.streaming = DiscordStreamingAdapter(bot)
        self.threading = DiscordThreadingAdapter(bot)
        self.status = DiscordStatusAdapter(bot)

        self._bot = bot

    def set_bot(self, bot: "discord.Client") -> None:
        """Set the Discord bot client for all adapters.

        Args:
            bot: The Discord client instance
        """
        self._bot = bot
        self.outbound.set_bot(bot)
        self.streaming.set_bot(bot)
        self.threading.set_bot(bot)
        self.status.set_bot(bot)


def create_discord_plugin(bot: "discord.Client | None" = None) -> DiscordPlugin:
    """Create a Discord plugin instance.

    Args:
        bot: Optional Discord client

    Returns:
        Configured Discord plugin
    """
    return DiscordPlugin(bot)
