"""Message formatting and splitting for Discord.

Handles:
- Message splitting to fit Discord's 2000 character limit
- Response formatting with streaming indicators
- Content cleaning (bot mention removal)
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import discord

# Discord message limit
DISCORD_MSG_LIMIT = 2000


def clean_content(content: str, bot_user: discord.User | None) -> str:
    """Clean message content by removing bot mentions.

    Args:
        content: Raw message content
        bot_user: The bot's user object (to remove its mentions)

    Returns:
        Cleaned content with bot mentions removed
    """
    if bot_user:
        content = re.sub(rf"<@!?{bot_user.id}>", "", content)
    return content.strip()


def format_response(
    text: str,
    in_progress: bool = False,
    max_length: int = DISCORD_MSG_LIMIT,
) -> str:
    """Format response text for Discord.

    Args:
        text: Response text
        in_progress: Whether response is still streaming
        max_length: Maximum message length

    Returns:
        Formatted text
    """
    if in_progress:
        # Add typing indicator
        text = text + " \u258c"  # ▌

    # Truncate if too long
    if len(text) > max_length:
        text = text[: max_length - 4] + "..."

    return text


def split_message(text: str, max_length: int = DISCORD_MSG_LIMIT) -> list[str]:
    """Split a message into Discord-sized chunks.

    Attempts to split at line boundaries when possible to preserve
    formatting and readability.

    Args:
        text: The full text to split
        max_length: Maximum length per chunk

    Returns:
        List of chunks, each under max_length
    """
    if len(text) <= max_length:
        return [text]

    chunks = []
    current = ""

    for line in text.split("\n"):
        # Check if adding this line would exceed limit
        # Leave some margin for safety
        if len(current) + len(line) + 1 > max_length - 20:
            if current:
                chunks.append(current.strip())
            # Start new chunk with this line
            current = line + "\n"
        else:
            current += line + "\n"

    # Don't forget the last chunk
    if current.strip():
        chunks.append(current.strip())

    # Safety: if somehow we got no chunks, just truncate
    return chunks if chunks else [text[:max_length]]


def split_message_preserve_code(text: str, max_length: int = DISCORD_MSG_LIMIT) -> list[str]:
    """Split a message while preserving code blocks.

    More sophisticated splitting that keeps code blocks intact
    when possible.

    Args:
        text: The full text to split
        max_length: Maximum length per chunk

    Returns:
        List of chunks, each under max_length
    """
    if len(text) <= max_length:
        return [text]

    # Check if there are code blocks
    code_block_pattern = r"```[\s\S]*?```"
    code_blocks = list(re.finditer(code_block_pattern, text))

    if not code_blocks:
        # No code blocks, use simple splitting
        return split_message(text, max_length)

    chunks = []
    current = ""
    last_end = 0

    for match in code_blocks:
        # Add text before this code block
        before_block = text[last_end : match.start()]
        code_block = match.group()

        # Can we fit the text before + code block?
        if len(current) + len(before_block) + len(code_block) <= max_length - 20:
            current += before_block + code_block
        else:
            # Need to split
            if current:
                chunks.append(current.strip())
            current = ""

            # Does the code block itself fit?
            if len(code_block) <= max_length - 20:
                # Add text before if it fits
                if len(before_block) <= max_length - len(code_block) - 20:
                    current = before_block + code_block
                else:
                    # Split the before text, then add code block
                    for chunk in split_message(before_block, max_length):
                        chunks.append(chunk)
                    current = code_block
            else:
                # Code block too big, have to split it
                if before_block.strip():
                    chunks.extend(split_message(before_block, max_length))
                chunks.extend(split_message(code_block, max_length))

        last_end = match.end()

    # Add remaining text
    remaining = text[last_end:]
    if remaining.strip():
        if len(current) + len(remaining) <= max_length:
            current += remaining
        else:
            if current:
                chunks.append(current.strip())
            chunks.extend(split_message(remaining, max_length))
            current = ""

    if current.strip():
        chunks.append(current.strip())

    return chunks if chunks else [text[:max_length]]
