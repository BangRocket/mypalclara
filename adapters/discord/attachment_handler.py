"""Attachment handling for Discord.

Handles:
- Image processing and resizing for vision
- Text file extraction
- Generic file metadata
"""

from __future__ import annotations

import base64
import os
from typing import TYPE_CHECKING, Any

from config.logging import get_logger

if TYPE_CHECKING:
    import discord

logger = get_logger("adapters.discord.attachments")

# Image handling configuration
MAX_IMAGE_DIMENSION = int(os.getenv("DISCORD_MAX_IMAGE_DIMENSION", "1568"))
MAX_IMAGE_SIZE = int(os.getenv("DISCORD_MAX_IMAGE_SIZE", str(4 * 1024 * 1024)))  # 4MB
MAX_IMAGES_PER_REQUEST = int(os.getenv("DISCORD_MAX_IMAGES_PER_REQUEST", "1"))
MAX_TEXT_FILE_SIZE = int(os.getenv("DISCORD_MAX_TEXT_FILE_SIZE", str(100 * 1024)))  # 100KB

# Supported file extensions
IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp"})

TEXT_EXTENSIONS = frozenset(
    {
        ".txt",
        ".md",
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".json",
        ".yaml",
        ".yml",
        ".html",
        ".css",
        ".scss",
        ".xml",
        ".csv",
        ".log",
        ".sh",
        ".bash",
        ".zsh",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".java",
        ".go",
        ".rs",
        ".rb",
        ".php",
        ".sql",
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
        ".env",
        ".gitignore",
        ".dockerfile",
    }
)


def get_file_extension(filename: str) -> str:
    """Get the lowercase file extension from a filename.

    Args:
        filename: The filename to extract extension from

    Returns:
        The extension including the dot (e.g., ".py"), or empty string
    """
    if "." not in filename:
        return ""
    return "." + filename.lower().rsplit(".", 1)[-1]


def is_image_file(filename: str) -> bool:
    """Check if a filename indicates an image file.

    Args:
        filename: The filename to check

    Returns:
        True if the file appears to be an image
    """
    return get_file_extension(filename) in IMAGE_EXTENSIONS


def is_text_file(filename: str) -> bool:
    """Check if a filename indicates a text file.

    Args:
        filename: The filename to check

    Returns:
        True if the file appears to be a text file
    """
    return get_file_extension(filename) in TEXT_EXTENSIONS


async def extract_attachments(message: discord.Message) -> list[dict[str, Any]]:
    """Extract and process attachments from a Discord message.

    Handles:
    - Images: Resized for vision processing, base64 encoded
    - Text files: Content extracted directly
    - Other files: Metadata only

    Args:
        message: Discord message to extract from

    Returns:
        List of attachment dicts ready for gateway protocol
    """
    attachments = []

    for attachment in message.attachments:
        ext = get_file_extension(attachment.filename)

        try:
            if ext in IMAGE_EXTENSIONS:
                # Process image attachment
                img_att = await process_image_attachment(attachment)
                if img_att:
                    attachments.append(img_att)

            elif ext in TEXT_EXTENSIONS:
                # Process text file attachment
                txt_att = await process_text_attachment(attachment)
                if txt_att:
                    attachments.append(txt_att)

            else:
                # Generic file - metadata only
                attachments.append(
                    {
                        "type": "file",
                        "filename": attachment.filename,
                        "media_type": attachment.content_type,
                        "size": attachment.size,
                    }
                )

        except Exception as e:
            logger.warning(f"Failed to process attachment {attachment.filename}: {e}")

    return attachments


async def process_image_attachment(
    attachment: discord.Attachment,
    max_dimension: int = MAX_IMAGE_DIMENSION,
    max_size: int = MAX_IMAGE_SIZE,
) -> dict[str, Any] | None:
    """Process an image attachment for vision.

    Resizes large images and converts to base64.

    Args:
        attachment: Discord attachment object
        max_dimension: Maximum pixels on longest edge
        max_size: Maximum file size in bytes

    Returns:
        Attachment dict or None if processing fails
    """
    try:
        # Download image bytes
        image_bytes = await attachment.read()

        # Skip extremely large images
        if len(image_bytes) > max_size * 2:
            logger.warning(f"Image too large ({len(image_bytes)} bytes), skipping")
            return None

        # Resize for vision processing
        from clara_core.discord.utils import resize_image_for_vision

        resized_bytes, media_type = resize_image_for_vision(
            image_bytes,
            max_dimension=max_dimension,
        )

        # Check size after resize
        if len(resized_bytes) > max_size:
            logger.warning(f"Resized image still too large ({len(resized_bytes)} bytes)")
            return None

        # Convert to base64
        base64_data = base64.b64encode(resized_bytes).decode("utf-8")

        return {
            "type": "image",
            "filename": attachment.filename,
            "media_type": media_type,
            "base64_data": base64_data,
            "size": len(resized_bytes),
        }

    except Exception as e:
        logger.warning(f"Failed to process image {attachment.filename}: {e}")
        return None


async def process_text_attachment(
    attachment: discord.Attachment,
    max_size: int = MAX_TEXT_FILE_SIZE,
) -> dict[str, Any] | None:
    """Process a text file attachment.

    Args:
        attachment: Discord attachment object
        max_size: Maximum file size to process

    Returns:
        Attachment dict or None if processing fails
    """
    try:
        if attachment.size > max_size:
            logger.warning(f"Text file too large ({attachment.size} bytes), skipping")
            return None

        # Download and decode
        content_bytes = await attachment.read()
        content = content_bytes.decode("utf-8", errors="replace")

        return {
            "type": "text",
            "filename": attachment.filename,
            "media_type": attachment.content_type or "text/plain",
            "content": content,
            "size": len(content_bytes),
        }

    except Exception as e:
        logger.warning(f"Failed to process text file {attachment.filename}: {e}")
        return None
