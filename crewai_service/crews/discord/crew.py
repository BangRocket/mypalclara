"""Discord Crew - translates between Discord and Flow contract.

This Crew handles all Discord-specific logic:
- Receiving Discord messages and converting to InboundMessage
- Delivering OutboundMessage as Discord replies (with chunking)
- Building conversation history from Discord reply chains
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from crewai_service.crews.base import BaseCrew
from crewai_service.contracts.messages import InboundMessage, OutboundMessage
from crewai_service.discord.helpers import (
    build_participants_list,
    chunk_response,
    clean_message_content,
    get_or_create_thread_id,
)

if TYPE_CHECKING:
    import discord


# Max messages to fetch for reply chain
MAX_REPLY_CHAIN = 10


class DiscordCrew(BaseCrew):
    """Translates between Discord and Flow contract.

    Responsibilities:
    - Transform Discord messages into InboundMessage for the Flow
    - Transform OutboundMessage from the Flow into Discord sends
    - Handle message chunking for Discord's 2000 char limit
    - Build conversation history from Discord reply chains
    """

    def __init__(self, bot_user: "discord.User"):
        """Initialize the Discord Crew.

        Args:
            bot_user: The bot's Discord user (for mention cleanup)
        """
        self.bot_user = bot_user

    async def receive(self, message: "discord.Message") -> InboundMessage:
        """Transform Discord message into Flow contract.

        Args:
            message: Discord message object

        Returns:
            Normalized InboundMessage for the Flow
        """
        # Clean message content (remove bot mentions)
        content = clean_message_content(message.content, self.bot_user.id)

        # Build metadata
        metadata = {
            "channel_id": str(message.channel.id),
            "message_id": str(message.id),
            "guild_id": str(message.guild.id) if message.guild else None,
            "guild_name": message.guild.name if message.guild else None,
            "channel_name": getattr(message.channel, "name", "DM"),
            "is_dm": message.guild is None,
            "thread_id": get_or_create_thread_id(message),
            "participants": build_participants_list(message),
        }

        # Get attachment URLs
        attachments = [a.url for a in message.attachments]

        # Build conversation history from reply chain
        recent_messages = await self._build_reply_chain(message)

        return InboundMessage(
            source="discord",
            user_id=f"discord-{message.author.id}",
            user_name=message.author.display_name,
            content=content,
            attachments=attachments,
            metadata=metadata,
            recent_messages=recent_messages,
            timestamp=datetime.now(timezone.utc),
        )

    async def deliver(
        self,
        response: OutboundMessage,
        message: "discord.Message",
    ) -> None:
        """Send Flow response back to Discord.

        Handles chunking for long responses.

        Args:
            response: Normalized OutboundMessage from the Flow
            message: Original Discord message to reply to
        """
        chunks = chunk_response(response.content)

        for i, chunk in enumerate(chunks):
            if i == 0:
                # First chunk - reply to original message
                await message.reply(chunk, mention_author=False)
            else:
                # Subsequent chunks - just send to channel
                await message.channel.send(chunk)

    async def _build_reply_chain(
        self,
        message: "discord.Message",
    ) -> list[dict[str, str]]:
        """Build conversation chain by following Discord replies.

        Args:
            message: The message with a reply reference

        Returns:
            List of messages in chronological order
        """
        chain = []

        # Only follow if there's a reply reference
        if not message.reference or not message.reference.resolved:
            return chain

        current = message.reference.resolved
        seen_ids = set()

        while current and len(chain) < MAX_REPLY_CHAIN:
            if current.id in seen_ids:
                break
            seen_ids.add(current.id)

            # Determine role
            if current.author == self.bot_user:
                role = "assistant"
            else:
                role = "user"

            # Clean content
            content = clean_message_content(current.content, self.bot_user.id)
            if content:
                # Add author prefix for non-bot messages in group chats
                if role == "user" and current.guild:
                    content = f"[{current.author.display_name}]: {content}"

                chain.append({"role": role, "content": content})

            # Follow the chain
            if current.reference and current.reference.resolved:
                current = current.reference.resolved
            else:
                break

        # Reverse to get chronological order
        chain.reverse()
        return chain
