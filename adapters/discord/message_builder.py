"""Message formatting and splitting for Discord.

Handles:
- Message splitting to fit Discord's 2000 character limit
- Response formatting with streaming indicators
- Content cleaning (bot mention removal)
- Special marker parsing for reactions, embeds, threads, buttons
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import discord

logger = logging.getLogger(__name__)

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


def parse_markers(text: str) -> dict[str, Any]:
    """Parse special markers from response text.

    Markers are special lines that trigger platform features:
    - __REACTION__:emoji - Add reaction to original message
    - __EMBED__:{json} - Create an embed message
    - __THREAD__:name:archive_minutes - Create a thread
    - __EDIT__:message_id - Edit a previous message
    - __BUTTONS__:[{json}] - Add interactive buttons

    Args:
        text: Full response text

    Returns:
        Dict with parsed data and cleaned text:
        - text: Cleaned text with markers removed
        - reaction: Emoji to react with (optional)
        - embed: Embed data dict (optional)
        - thread: Thread config dict (optional)
        - edit_target: Message ID to edit (optional)
        - buttons: Button configs list (optional)
    """
    result: dict[str, Any] = {"text": text}
    lines_to_remove = []

    for line in text.split("\n"):
        line_stripped = line.strip()

        # Reaction marker
        if line_stripped.startswith("__REACTION__:"):
            result["reaction"] = line_stripped.replace("__REACTION__:", "").strip()
            lines_to_remove.append(line)

        # Embed marker
        elif line_stripped.startswith("__EMBED__:"):
            try:
                json_str = line_stripped.replace("__EMBED__:", "").strip()
                result["embed"] = json.loads(json_str)
                lines_to_remove.append(line)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse embed JSON: {e}")

        # Thread marker
        elif line_stripped.startswith("__THREAD__:"):
            parts = line_stripped.replace("__THREAD__:", "").strip().split(":")
            result["thread"] = {
                "name": parts[0] if parts else "Discussion",
                "auto_archive": int(parts[1]) if len(parts) > 1 else 1440,
            }
            lines_to_remove.append(line)

        # Edit marker
        elif line_stripped.startswith("__EDIT__:"):
            result["edit_target"] = line_stripped.replace("__EDIT__:", "").strip()
            lines_to_remove.append(line)

        # Buttons marker
        elif line_stripped.startswith("__BUTTONS__:"):
            try:
                json_str = line_stripped.replace("__BUTTONS__:", "").strip()
                result["buttons"] = json.loads(json_str)
                lines_to_remove.append(line)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse buttons JSON: {e}")

    # Remove marker lines from text
    for line in lines_to_remove:
        text = text.replace(line, "")

    result["text"] = text.strip()
    return result
