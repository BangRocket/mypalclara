"""
Discord Adapter - Routes Discord events to Clara's graph.

Converts Discord messages to normalized Event model and
sends responses back to Discord.
"""

import logging

import discord
from discord.ext import commands

from mypalclara.config.settings import settings
from mypalclara.graph import process_event
from mypalclara.models.events import Attachment, ChannelMode, Event, EventType, HistoricalMessage

logger = logging.getLogger(__name__)

# How many messages to fetch for context
HISTORY_LIMIT = 20


class ClaraBot(commands.Bot):
    """Discord bot that routes events to Clara's graph."""

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        super().__init__(
            command_prefix="!",  # Not really used
            intents=intents,
        )

        self.clara_user_id = None  # Set on ready

    async def on_ready(self):
        logger.info(f"[discord] Logged in as {self.user}")
        self.clara_user_id = self.user.id

    async def on_message(self, message: discord.Message):
        """Convert Discord message to Event and process."""

        # Ignore own messages
        if message.author.id == self.clara_user_id:
            return

        # Ignore bots
        if message.author.bot:
            return

        # Fetch conversation history
        history = await self._fetch_history(message.channel, before=message)

        # Build event with history
        event = self._message_to_event(message, history)

        content_preview = event.content[:50] if event.content else "(no content)"
        logger.info(f"[discord] Event from {event.user_name}: {content_preview}...")

        # Track status message for editing
        status_message = None
        last_status = None

        async def on_status(node_name: str, state: dict):
            """Handle status updates from the graph."""
            nonlocal status_message, last_status

            # Show tool use status when entering command node
            if node_name == "command":
                rumination = state.get("rumination")
                if rumination and rumination.faculty:
                    faculty = rumination.faculty
                    intent = rumination.intent or ""
                    intent_preview = intent[:100] + "..." if len(intent) > 100 else intent

                    status_text = f"*Using {faculty}:* {intent_preview}"

                    # Avoid duplicate messages
                    if status_text != last_status:
                        last_status = status_text
                        if status_message:
                            # Edit existing status message
                            try:
                                await status_message.edit(content=status_text)
                            except discord.errors.NotFound:
                                status_message = await message.channel.send(status_text)
                        else:
                            status_message = await message.channel.send(status_text)

        # Process through Clara's graph with typing indicator
        try:
            async with message.channel.typing():
                result = await process_event(event, on_status=on_status)

            # Delete status message if we're about to send response
            if status_message and result.get("response"):
                try:
                    await status_message.delete()
                except discord.errors.NotFound:
                    pass

            # Send response if we have one
            if result.get("response"):
                response_text = result["response"]

                # Discord has 2000 char limit
                if len(response_text) > 2000:
                    # Split into chunks
                    chunks = [response_text[i : i + 2000] for i in range(0, len(response_text), 2000)]
                    for chunk in chunks:
                        await message.channel.send(chunk)
                else:
                    await message.channel.send(response_text)

                logger.info(f"[discord] Response sent ({len(response_text)} chars)")

        except Exception as e:
            logger.exception(f"[discord] Error processing event: {e}")

    async def _fetch_history(
        self, channel: discord.TextChannel, before: discord.Message
    ) -> list[HistoricalMessage]:
        """Fetch recent conversation history from the channel."""
        history = []

        try:
            async for msg in channel.history(limit=HISTORY_LIMIT, before=before):
                # Skip system messages
                if msg.type != discord.MessageType.default:
                    continue

                is_clara = msg.author.id == self.clara_user_id
                history.append(
                    HistoricalMessage(
                        author="Clara" if is_clara else msg.author.display_name,
                        content=msg.content or "(attachment)",
                        is_clara=is_clara,
                        timestamp=msg.created_at,
                    )
                )

            # Reverse to get chronological order (oldest first)
            history.reverse()
            logger.debug(f"[discord] Fetched {len(history)} messages of history")

        except discord.errors.Forbidden:
            logger.warning("[discord] No permission to fetch message history")
        except Exception as e:
            logger.error(f"[discord] Error fetching history: {e}")

        return history

    def _message_to_event(
        self, message: discord.Message, history: list[HistoricalMessage] | None = None
    ) -> Event:
        """Convert Discord message to normalized Event."""

        # Check if Clara was mentioned
        mentioned = self.user in message.mentions if self.user else False

        # Check if this is a reply to Clara
        reply_to_clara = False
        if message.reference and message.reference.resolved:
            if hasattr(message.reference.resolved, "author"):
                reply_to_clara = message.reference.resolved.author.id == self.clara_user_id

        # Determine channel mode (could be stored in DB per channel)
        channel_mode = self._get_channel_mode(message.channel)

        # Build attachments
        attachments = [
            Attachment(
                id=str(a.id),
                filename=a.filename,
                url=a.url,
                content_type=a.content_type,
                size=a.size,
            )
            for a in message.attachments
        ]

        return Event(
            id=str(message.id),
            type=EventType.MESSAGE,
            user_id=f"discord-{message.author.id}",  # Prefix to match stored format
            user_name=message.author.display_name,
            channel_id=str(message.channel.id),
            guild_id=str(message.guild.id) if message.guild else None,
            content=message.content,
            attachments=attachments,
            is_dm=isinstance(message.channel, discord.DMChannel),
            mentioned=mentioned,
            reply_to_clara=reply_to_clara,
            channel_mode=channel_mode,
            conversation_history=history or [],
            metadata={
                "message_type": str(message.type),
                "jump_url": message.jump_url,
            },
        )

    def _get_channel_mode(self, channel) -> ChannelMode:
        """Get channel mode. Could be DB-driven in the future."""
        # Default: conversational in DMs, assistant in servers
        if isinstance(channel, discord.DMChannel):
            return ChannelMode.CONVERSATIONAL
        return ChannelMode.ASSISTANT


async def run_bot():
    """Run the Discord bot."""
    if not settings.discord_bot_token:
        raise RuntimeError("DISCORD_BOT_TOKEN is not set")

    bot = ClaraBot()
    await bot.start(settings.discord_bot_token)
