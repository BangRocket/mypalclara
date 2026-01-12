"""
Discord Faculty - Discord messaging capabilities.

Provides tools for sending messages to Discord channels,
including cross-channel posting and rich embeds.
"""

import logging
from typing import Any, Optional

from mypalclara.faculties.base import Faculty
from mypalclara.models.state import FacultyResult

logger = logging.getLogger(__name__)


class DiscordFaculty(Faculty):
    """Discord messaging faculty."""

    name = "discord"
    description = "Send messages to Discord channels, including cross-channel posting and embeds"

    available_actions = [
        "send_message",
        "send_embed",
        "send_file",
        "get_channel_info",
        "list_channels",
    ]

    def __init__(self):
        self._bot = None  # Set by adapter when executing

    def set_bot(self, bot):
        """Set the Discord bot instance."""
        self._bot = bot

    async def execute(
        self,
        intent: str,
        constraints: Optional[list[str]] = None,
        user_id: Optional[str] = None,
        channel_id: Optional[str] = None,
    ) -> FacultyResult:
        """Execute Discord-related intent."""
        logger.info(f"[discord] Intent: {intent}")

        if self._bot is None:
            return FacultyResult(
                success=False,
                summary="Discord bot not available in this context",
                error="No bot instance",
            )

        try:
            action, params = self._parse_intent(intent)
            logger.info(f"[discord] Action: {action}")

            if action == "send_message":
                result = await self._send_message(params)
            elif action == "send_embed":
                result = await self._send_embed(params)
            elif action == "send_file":
                result = await self._send_file(params)
            elif action == "get_channel_info":
                result = await self._get_channel_info(params)
            elif action == "list_channels":
                result = await self._list_channels(params)
            else:
                return FacultyResult(
                    success=False,
                    summary=f"Unknown Discord action: {action}",
                    error=f"Action '{action}' not recognized",
                )

            return result

        except Exception as e:
            logger.exception(f"[discord] Error: {e}")
            return FacultyResult(
                success=False,
                summary=f"Discord error: {str(e)}",
                error=str(e),
            )

    def _parse_intent(self, intent: str) -> tuple[str, dict]:
        """Parse natural language intent into action and parameters."""
        intent_lower = intent.lower()

        # Send message
        if any(phrase in intent_lower for phrase in ["send message", "post to", "send to channel"]):
            channel_id = self._extract_channel_id(intent)
            content = self._extract_content(intent)
            return "send_message", {"channel_id": channel_id, "content": content}

        # Send embed
        if any(phrase in intent_lower for phrase in ["send embed", "post embed", "rich message"]):
            channel_id = self._extract_channel_id(intent)
            return "send_embed", {"channel_id": channel_id, **self._parse_embed_params(intent)}

        # Send file
        if any(phrase in intent_lower for phrase in ["send file", "share file", "upload file"]):
            channel_id = self._extract_channel_id(intent)
            filename = self._extract_filename(intent)
            return "send_file", {"channel_id": channel_id, "filename": filename}

        # Channel info
        if any(phrase in intent_lower for phrase in ["channel info", "about channel"]):
            channel_id = self._extract_channel_id(intent)
            return "get_channel_info", {"channel_id": channel_id}

        # List channels
        if any(phrase in intent_lower for phrase in ["list channels", "show channels", "available channels"]):
            guild_id = self._extract_guild_id(intent)
            return "list_channels", {"guild_id": guild_id}

        # Default to send message
        channel_id = self._extract_channel_id(intent)
        content = self._extract_content(intent)
        return "send_message", {"channel_id": channel_id, "content": content}

    def _extract_channel_id(self, text: str) -> str:
        """Extract Discord channel ID from text."""
        import re
        # Look for <#123456789> format
        match = re.search(r'<#(\d+)>', text)
        if match:
            return match.group(1)

        # Look for raw ID
        match = re.search(r'channel[:\s]+(\d{17,19})', text, re.IGNORECASE)
        if match:
            return match.group(1)

        # Look for any long number that could be a channel ID
        match = re.search(r'\b(\d{17,19})\b', text)
        return match.group(1) if match else ""

    def _extract_guild_id(self, text: str) -> str:
        """Extract Discord guild/server ID from text."""
        import re
        match = re.search(r'(?:guild|server)[:\s]+(\d{17,19})', text, re.IGNORECASE)
        return match.group(1) if match else ""

    def _extract_content(self, text: str) -> str:
        """Extract message content from text."""
        import re
        # Look for content in quotes
        match = re.search(r'["\']([^"\']+)["\']', text)
        if match:
            return match.group(1)

        # Look for content after "message:" or "content:"
        match = re.search(r'(?:message|content)[:\s]+(.+)$', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

        return ""

    def _extract_filename(self, text: str) -> str:
        """Extract filename from text."""
        import re
        match = re.search(r'["\']([^"\']+\.[a-zA-Z0-9]+)["\']', text)
        if match:
            return match.group(1)

        match = re.search(r'\b([\w\-]+\.[\w]+)\b', text)
        return match.group(1) if match else ""

    def _parse_embed_params(self, text: str) -> dict:
        """Parse embed parameters from text."""
        import re
        params: dict[str, Any] = {}

        match = re.search(r'title[:\s]+["\']([^"\']+)["\']', text, re.IGNORECASE)
        if match:
            params["title"] = match.group(1)

        match = re.search(r'description[:\s]+["\']([^"\']+)["\']', text, re.IGNORECASE)
        if match:
            params["description"] = match.group(1)

        match = re.search(r'color[:\s]+(\w+)', text, re.IGNORECASE)
        if match:
            color_str = match.group(1)
            # Convert color names to hex
            colors = {
                "red": 0xFF0000,
                "green": 0x00FF00,
                "blue": 0x0000FF,
                "yellow": 0xFFFF00,
                "orange": 0xFFA500,
                "purple": 0x800080,
            }
            params["color"] = colors.get(color_str.lower())

        return params

    async def _send_message(self, params: dict) -> FacultyResult:
        """Send a message to a specific Discord channel."""
        channel_id = params.get("channel_id")
        content = params.get("content", "")

        if not channel_id:
            return FacultyResult(success=False, summary="No channel ID provided", error="Missing channel_id")

        if not content:
            return FacultyResult(success=False, summary="No message content provided", error="Missing content")

        try:
            channel_id_int = int(channel_id)
        except (ValueError, TypeError):
            return FacultyResult(
                success=False,
                summary=f"Invalid channel_id '{channel_id}' - must be a valid Discord channel ID",
                error="Invalid channel_id",
            )

        # Get the channel
        channel = self._bot.get_channel(channel_id_int)
        if not channel:
            try:
                channel = await self._bot.fetch_channel(channel_id_int)
            except Exception:
                return FacultyResult(
                    success=False,
                    summary=f"Channel {channel_id} not found. Make sure Clara is in the server.",
                    error="Channel not found",
                )

        if not hasattr(channel, "send"):
            return FacultyResult(
                success=False,
                summary=f"Channel {channel_id} is not a text channel",
                error="Not a text channel",
            )

        # Check permissions
        if hasattr(channel, "guild") and channel.guild:
            me = channel.guild.me
            if me:
                permissions = channel.permissions_for(me)
                if not permissions.send_messages:
                    return FacultyResult(
                        success=False,
                        summary=f"Clara doesn't have permission to send messages in #{channel.name}",
                        error="No send permission",
                    )

        # Send the message
        await channel.send(content=content)

        channel_name = getattr(channel, "name", str(channel_id))
        guild_name = getattr(channel, "guild", None)
        guild_str = f" in {guild_name.name}" if guild_name else ""

        return FacultyResult(
            success=True,
            summary=f"Message sent to #{channel_name}{guild_str}",
            data={"channel_id": channel_id, "channel_name": channel_name},
        )

    async def _send_embed(self, params: dict) -> FacultyResult:
        """Send an embed to a Discord channel."""
        channel_id = params.get("channel_id")
        title = params.get("title", "")
        description = params.get("description", "")
        color = params.get("color")

        if not channel_id:
            return FacultyResult(success=False, summary="No channel ID provided", error="Missing channel_id")

        if not title and not description:
            return FacultyResult(success=False, summary="Embed needs title or description", error="Empty embed")

        try:
            import discord

            channel_id_int = int(channel_id)
            channel = self._bot.get_channel(channel_id_int)
            if not channel:
                channel = await self._bot.fetch_channel(channel_id_int)

            embed = discord.Embed()
            if title:
                embed.title = title
            if description:
                embed.description = description
            if color:
                embed.color = discord.Color(color)

            # Add fields if provided
            for field in params.get("fields", []):
                embed.add_field(
                    name=field.get("name", ""),
                    value=field.get("value", ""),
                    inline=field.get("inline", False),
                )

            await channel.send(embed=embed)

            channel_name = getattr(channel, "name", str(channel_id))

            return FacultyResult(
                success=True,
                summary=f"Embed sent to #{channel_name}",
                data={"channel_id": channel_id},
            )

        except Exception as e:
            return FacultyResult(
                success=False,
                summary=f"Failed to send embed: {str(e)}",
                error=str(e),
            )

    async def _send_file(self, params: dict) -> FacultyResult:
        """Send a file to a Discord channel."""
        channel_id = params.get("channel_id")
        filename = params.get("filename", "")
        content = params.get("content", "")  # Optional message with file

        if not channel_id:
            return FacultyResult(success=False, summary="No channel ID provided", error="Missing channel_id")

        if not filename:
            return FacultyResult(success=False, summary="No filename provided", error="Missing filename")

        return FacultyResult(
            success=False,
            summary="File sending requires local file path - use the files faculty to manage files",
            error="Use files faculty",
        )

    async def _get_channel_info(self, params: dict) -> FacultyResult:
        """Get information about a Discord channel."""
        channel_id = params.get("channel_id")

        if not channel_id:
            return FacultyResult(success=False, summary="No channel ID provided", error="Missing channel_id")

        try:
            channel_id_int = int(channel_id)
            channel = self._bot.get_channel(channel_id_int)
            if not channel:
                channel = await self._bot.fetch_channel(channel_id_int)

            info = {
                "id": str(channel.id),
                "name": getattr(channel, "name", "DM"),
                "type": str(channel.type),
            }

            if hasattr(channel, "guild") and channel.guild:
                info["guild"] = channel.guild.name
                info["guild_id"] = str(channel.guild.id)

            if hasattr(channel, "topic") and channel.topic:
                info["topic"] = channel.topic

            summary = f"**#{info['name']}**\n"
            if "guild" in info:
                summary += f"Server: {info['guild']}\n"
            if "topic" in info:
                summary += f"Topic: {info['topic']}\n"
            summary += f"Type: {info['type']}"

            return FacultyResult(
                success=True,
                summary=summary,
                data=info,
            )

        except Exception as e:
            return FacultyResult(
                success=False,
                summary=f"Failed to get channel info: {str(e)}",
                error=str(e),
            )

    async def _list_channels(self, params: dict) -> FacultyResult:
        """List channels in a server."""
        guild_id = params.get("guild_id")

        if not guild_id:
            # List channels from all guilds the bot is in
            channels = []
            for guild in self._bot.guilds:
                for channel in guild.text_channels[:5]:  # Limit per guild
                    channels.append({
                        "id": str(channel.id),
                        "name": channel.name,
                        "guild": guild.name,
                    })
        else:
            try:
                guild_id_int = int(guild_id)
                guild = self._bot.get_guild(guild_id_int)
                if not guild:
                    return FacultyResult(
                        success=False,
                        summary=f"Server {guild_id} not found",
                        error="Guild not found",
                    )

                channels = [
                    {"id": str(c.id), "name": c.name, "guild": guild.name}
                    for c in guild.text_channels[:20]
                ]
            except Exception as e:
                return FacultyResult(success=False, summary=f"Error: {str(e)}", error=str(e))

        if not channels:
            return FacultyResult(
                success=True,
                summary="No text channels found",
                data={"channels": []},
            )

        formatted = "\n".join([f"- **#{c['name']}** ({c['id']}) in {c['guild']}" for c in channels[:20]])

        return FacultyResult(
            success=True,
            summary=f"**Text Channels:**\n{formatted}",
            data={"channels": channels},
        )
