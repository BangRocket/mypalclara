"""Discord helper functions."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import discord


def clean_message_content(content: str, bot_id: int) -> str:
    """Remove bot mentions from message content.

    Args:
        content: Raw message content
        bot_id: The bot's user ID

    Returns:
        Cleaned message content
    """
    # Remove bot mentions like <@123456789> or <@!123456789>
    patterns = [
        rf"<@!?{bot_id}>",  # Direct mention
        r"<@!?\d+>",  # Any user mention at start (likely the bot)
    ]

    cleaned = content
    for pattern in patterns:
        cleaned = re.sub(pattern, "", cleaned, count=1)

    return cleaned.strip()


def chunk_response(content: str, max_length: int = 2000) -> list[str]:
    """Split a response into Discord-safe chunks.

    Tries to split on sentence boundaries when possible.

    Args:
        content: The response content
        max_length: Maximum chunk length (Discord limit is 2000)

    Returns:
        List of content chunks
    """
    if len(content) <= max_length:
        return [content]

    chunks = []
    remaining = content

    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break

        # Find a good split point
        split_at = max_length

        # Try to split at sentence boundary
        for sep in [". ", ".\n", "! ", "!\n", "? ", "?\n", "\n\n", "\n"]:
            last_sep = remaining[:max_length].rfind(sep)
            if last_sep > max_length // 2:  # Only use if reasonably far in
                split_at = last_sep + len(sep)
                break
        else:
            # Fall back to word boundary
            last_space = remaining[:max_length].rfind(" ")
            if last_space > max_length // 2:
                split_at = last_space + 1

        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()

    return chunks


def build_participants_list(message: "discord.Message") -> list[dict]:
    """Build participants list from message context.

    Args:
        message: Discord message

    Returns:
        List of participant dicts with id and name
    """
    participants = []

    # Add mentioned users
    for user in message.mentions:
        participants.append({
            "id": f"discord-{user.id}",
            "name": user.display_name,
        })

    # Add message author if not already included
    author_id = f"discord-{message.author.id}"
    if not any(p["id"] == author_id for p in participants):
        participants.append({
            "id": author_id,
            "name": message.author.display_name,
        })

    return participants


def get_or_create_thread_id(message: "discord.Message") -> str:
    """Get or create a thread ID for the message context.

    Uses channel ID as the thread ID for now (simplified).

    Args:
        message: Discord message

    Returns:
        Thread ID string
    """
    # For threads, use the thread ID
    if hasattr(message.channel, "parent_id") and message.channel.parent_id:
        return f"discord-thread-{message.channel.id}"

    # For DMs, use the channel ID (which is unique per DM)
    if message.guild is None:
        return f"discord-dm-{message.channel.id}"

    # For regular channels, use channel ID
    return f"discord-channel-{message.channel.id}"
