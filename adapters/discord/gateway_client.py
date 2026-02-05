"""Discord gateway client for the Clara Gateway.

Connects Discord to the gateway for centralized processing.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from adapters.base import GatewayClient
from adapters.discord.attachment_handler import extract_attachments
from adapters.discord.message_builder import (
    DISCORD_MSG_LIMIT,
    clean_content,
    format_response,
    split_message,
)
from config.logging import get_logger
from gateway.protocol import ChannelInfo, UserInfo

if TYPE_CHECKING:
    import discord

logger = get_logger("adapters.discord.gateway")


@dataclass
class PendingResponse:
    """Tracks an in-flight response for streaming."""

    request_id: str
    message: discord.Message
    started_at: datetime = field(default_factory=datetime.now)
    accumulated_text: str = ""
    tool_count: int = 0
    last_edit: datetime | None = None
    status_message: discord.Message | None = None
    typing_task: asyncio.Task[None] | None = None
    sent_messages: list[discord.Message] = field(default_factory=list)
    thread: discord.Thread | None = None


class DiscordGatewayClient(GatewayClient):
    """Discord-specific gateway client.

    Handles Discord message formatting, chunking, and streaming display.
    """

    def __init__(
        self,
        bot: Any,
        gateway_url: str | None = None,
    ) -> None:
        """Initialize the Discord gateway client.

        Args:
            bot: The Discord bot instance
            gateway_url: Optional gateway URL override
        """
        super().__init__(
            platform="discord",
            capabilities=["streaming", "attachments", "reactions", "embeds", "threads", "editing", "buttons"],
            gateway_url=gateway_url,
        )
        self.bot = bot
        self._pending: dict[str, PendingResponse] = {}
        self._edit_cooldown = 0.5  # Seconds between edits
        self._typing_interval = 8.0  # Discord typing lasts ~10 seconds

    async def send_discord_message(
        self,
        message: discord.Message,
        tier_override: str | None = None,
    ) -> str | None:
        """Send a Discord message to the gateway for processing.

        Args:
            message: The Discord message to process
            tier_override: Optional model tier override

        Returns:
            Request ID if sent, None if failed
        """
        try:
            # Build user info
            user = UserInfo(
                id=f"discord-{message.author.id}",
                platform_id=str(message.author.id),
                name=message.author.name,
                display_name=message.author.display_name,
            )

            # Build channel info
            is_dm = message.guild is None
            channel = ChannelInfo(
                id=str(message.channel.id),
                type="dm" if is_dm else "server",
                name=getattr(message.channel, "name", None),
                guild_id=str(message.guild.id) if message.guild else None,
                guild_name=message.guild.name if message.guild else None,
            )

            # Clean content
            content = clean_content(message.content, self.bot.user)

            # Build reply chain if present
            reply_chain = await self._build_reply_chain(message)

            # Extract attachments (images and text files)
            attachments = await extract_attachments(message)

            # Send to gateway
            request_id = await self.send_message(
                user=user,
                channel=channel,
                content=content,
                attachments=attachments,
                tier_override=tier_override,
                reply_chain=reply_chain,
                metadata={
                    "platform": "discord",
                    "message_id": str(message.id),
                    "is_dm": is_dm,
                },
            )

            # Track pending response
            self._pending[request_id] = PendingResponse(
                request_id=request_id,
                message=message,
            )

            return request_id

        except Exception as e:
            logger.exception(f"Failed to send message to gateway: {e}")
            return None

    async def _build_reply_chain(
        self,
        message: discord.Message,
        max_messages: int = 10,
    ) -> list[dict[str, Any]]:
        """Build conversation history from reply chain.

        Args:
            message: The starting message
            max_messages: Maximum messages to include

        Returns:
            List of message dicts with role and content
        """
        chain = []
        current = message
        seen_ids: set[int] = set()

        while current and len(chain) < max_messages:
            if current.id in seen_ids:
                break
            seen_ids.add(current.id)

            # Add to chain
            role = "assistant" if current.author.bot else "user"
            chain.insert(0, {"role": role, "content": current.content})

            # Follow reply
            if current.reference and current.reference.message_id:
                try:
                    current = await message.channel.fetch_message(current.reference.message_id)
                except Exception:
                    break
            else:
                break

        return chain[:-1]  # Exclude the current message

    async def on_response_start(self, message: Any) -> None:
        """Handle response start."""
        request_id = message.request_id
        pending = self._pending.get(request_id)
        if not pending:
            return

        # Show typing indicator immediately and keep it alive until completion
        await pending.message.channel.trigger_typing()
        self._start_typing_loop(pending)
        logger.debug(f"Response started for {request_id}")

    async def on_response_chunk(self, message: Any) -> None:
        """Handle streaming response chunk - just maintain typing indicator."""
        request_id = message.request_id
        pending = self._pending.get(request_id)
        if not pending:
            logger.debug(f"No pending request for chunk {request_id}")
            return

        # Accumulate text for final response
        pending.accumulated_text = message.accumulated or (pending.accumulated_text + message.chunk)

    async def on_response_end(self, message: Any) -> None:
        """Handle response completion - send the full message."""
        request_id = message.request_id
        pending = self._pending.pop(request_id, None)
        if not pending:
            logger.debug(f"No pending request for response end {request_id}")
            return
        self._stop_typing_loop(pending)

        # Send final response
        try:
            full_text = message.full_text

            # Parse markers from text
            parsed = self._parse_markers(full_text)
            full_text = parsed["text"]

            # Determine target channel (may be thread)
            target_channel = pending.thread or pending.message.channel

            # Handle thread creation marker
            if parsed.get("thread"):
                thread_info = parsed["thread"]
                try:
                    pending.thread = await pending.message.create_thread(
                        name=thread_info["name"],
                        auto_archive_duration=thread_info.get("auto_archive", 1440),
                    )
                    target_channel = pending.thread
                    logger.debug(f"Created thread: {pending.thread.name}")
                except Exception as e:
                    logger.warning(f"Failed to create thread: {e}")

            # Handle edit_target from protocol
            edit_target = getattr(message, "edit_target", None) or parsed.get("edit_target")

            # Get button components
            components = getattr(message, "components", []) or []
            if parsed.get("buttons"):
                components = parsed["buttons"]

            # Build view with buttons if any
            view = None
            if components:
                view = await self._create_button_view(components)

            # Handle embeds
            embeds = []
            if parsed.get("embed"):
                embed = self._create_embed_from_data(parsed["embed"])
                if embed:
                    embeds.append(embed)

            # Determine if we should edit or send new
            if edit_target == "last" and pending.sent_messages:
                # Edit the last sent message
                last_msg = pending.sent_messages[-1]
                try:
                    await last_msg.edit(
                        content=full_text if full_text else None,
                        embeds=embeds if embeds else None,
                        view=view,
                    )
                    logger.debug(f"Edited last message {last_msg.id}")
                except Exception as e:
                    logger.warning(f"Failed to edit message: {e}")
            elif edit_target == "status" and pending.status_message:
                # Edit the status message
                try:
                    await pending.status_message.edit(
                        content=full_text if full_text else None,
                        embeds=embeds if embeds else None,
                        view=view,
                    )
                    logger.debug(f"Edited status message {pending.status_message.id}")
                except Exception as e:
                    logger.warning(f"Failed to edit status: {e}")
            else:
                # Send new message(s)
                chunks = split_message(full_text) if full_text else [""]

                sent_message = None
                for i, chunk in enumerate(chunks):
                    # First chunk gets embeds and view
                    kwargs: dict[str, Any] = {"mention_author": False}
                    if i == 0:
                        if embeds:
                            kwargs["embeds"] = embeds
                        if view:
                            kwargs["view"] = view

                    if i == 0 and target_channel == pending.message.channel:
                        sent_message = await pending.message.reply(chunk or None, **kwargs)
                    else:
                        sent_message = await target_channel.send(chunk or None, **kwargs)

                    if sent_message:
                        pending.sent_messages.append(sent_message)

                # Add reaction if requested
                if parsed.get("reaction") and sent_message:
                    await self._send_reaction(sent_message, parsed["reaction"])

            # Handle file attachments (prefer file_data over files)
            file_data = getattr(message, "file_data", []) or []
            if file_data:
                logger.info(f"[response_end] Sending {len(file_data)} files from file_data")
                await self._send_files_from_data(target_channel, file_data)
            elif message.files:
                # Fallback to file paths (deprecated)
                logger.info(f"[response_end] Sending {len(message.files)} files from paths")
                await self._send_files(target_channel, message.files)

        except Exception as e:
            logger.exception(f"Failed to send final response: {e}")

        logger.info(f"Response {request_id} complete: {len(message.full_text)} chars, {message.tool_count} tools")

    def _parse_markers(self, text: str) -> dict[str, Any]:
        """Parse special markers from response text.

        Args:
            text: Full response text

        Returns:
            Dict with parsed data and cleaned text
        """
        import json

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

    def _create_embed_from_data(self, data: dict[str, Any]) -> discord.Embed | None:
        """Create a Discord embed from parsed data.

        Args:
            data: Embed data dict with type, title, description, etc.

        Returns:
            Discord Embed or None
        """
        import discord

        from clara_core.discord.embeds import (
            EMBED_COLOR_ERROR,
            EMBED_COLOR_INFO,
            EMBED_COLOR_PRIMARY,
            EMBED_COLOR_SUCCESS,
            EMBED_COLOR_WARNING,
        )

        embed_type = data.get("type", "info")
        title = data.get("title", "")
        description = data.get("description")

        # Determine color based on type
        color_map = {
            "success": EMBED_COLOR_SUCCESS,
            "error": EMBED_COLOR_ERROR,
            "warning": EMBED_COLOR_WARNING,
            "info": EMBED_COLOR_INFO,
            "status": EMBED_COLOR_PRIMARY,
            "custom": data.get("color", EMBED_COLOR_PRIMARY),
        }
        color = color_map.get(embed_type, EMBED_COLOR_INFO)

        # Add emoji prefix for success/error/warning
        emoji_map = {"success": "✅ ", "error": "❌ ", "warning": "⚠️ "}
        if embed_type in emoji_map:
            title = emoji_map[embed_type] + title

        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
        )

        # Add fields
        fields = data.get("fields", [])
        for field_data in fields:
            embed.add_field(
                name=field_data.get("name", ""),
                value=field_data.get("value", ""),
                inline=field_data.get("inline", False),
            )

        # Add footer
        footer = data.get("footer")
        if footer:
            embed.set_footer(text=footer)

        return embed

    async def _create_button_view(self, buttons: list[dict[str, Any]]) -> discord.ui.View:
        """Create a Discord View with buttons.

        Args:
            buttons: List of button configurations

        Returns:
            Discord View with buttons
        """
        from clara_core.discord.views import GatewayButtonView

        return GatewayButtonView(buttons)

    async def on_tool_start(self, message: Any) -> None:
        """Handle tool execution start."""
        request_id = message.request_id
        pending = self._pending.get(request_id)
        if not pending:
            logger.debug(f"No pending request for tool start {request_id}")
            return

        pending.tool_count = message.step

        # Send status message
        try:
            status = f"-# {message.emoji} {message.tool_name}... (step {message.step})"
            await pending.message.channel.send(status, silent=True)
        except Exception as e:
            logger.debug(f"Failed to send tool status: {e}")

    async def on_tool_result(self, message: Any) -> None:
        """Handle tool execution result."""
        # Tool results are already logged
        pass

    async def on_error(self, message: Any) -> None:
        """Handle gateway error."""
        await super().on_error(message)

        request_id = message.request_id
        pending = self._pending.pop(request_id, None)
        if pending:
            self._stop_typing_loop(pending)
            try:
                error_msg = f"Sorry, I encountered an error: {message.message[:100]}"
                await pending.message.reply(error_msg, mention_author=False)
            except Exception:
                pass

    async def on_cancelled(self, message: Any) -> None:
        """Handle request cancellation."""
        await super().on_cancelled(message)

        request_id = message.request_id
        pending = self._pending.pop(request_id, None)
        if pending:
            self._stop_typing_loop(pending)
            try:
                await pending.message.add_reaction("🛑")
            except Exception:
                pass

    def cancel_pending_for_channel(self, channel_id: str) -> list[str]:
        """Cancel all pending requests for a channel.

        Args:
            channel_id: Discord channel ID

        Returns:
            List of cancelled request IDs
        """
        cancelled = []
        to_remove = []

        for request_id, pending in self._pending.items():
            if str(pending.message.channel.id) == channel_id:
                to_remove.append(request_id)
                cancelled.append(request_id)

        for request_id in to_remove:
            pending = self._pending.get(request_id)
            if pending:
                self._stop_typing_loop(pending)
            del self._pending[request_id]

        return cancelled

    def _start_typing_loop(self, pending: PendingResponse) -> None:
        if pending.typing_task and not pending.typing_task.done():
            return

        async def _loop() -> None:
            try:
                while True:
                    await asyncio.sleep(self._typing_interval)
                    await pending.message.channel.trigger_typing()
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.debug(f"Typing indicator error: {e}")

        pending.typing_task = asyncio.create_task(_loop())

    def _stop_typing_loop(self, pending: PendingResponse) -> None:
        task = pending.typing_task
        if task and not task.done():
            task.cancel()
        pending.typing_task = None

    async def _send_files(
        self,
        channel: Any,
        file_paths: list[str],
    ) -> None:
        """Send files to a Discord channel.

        Args:
            channel: Discord channel
            file_paths: List of file paths to send
        """
        from pathlib import Path

        import discord

        files = []
        for path_str in file_paths:
            path = Path(path_str)
            logger.info(f"[_send_files] Checking path: {path} (exists: {path.exists()})")
            if path.exists():
                files.append(discord.File(path))
            else:
                logger.warning(f"[_send_files] File not found: {path}")

        logger.info(f"[_send_files] Prepared {len(files)} Discord files to send")
        if files:
            try:
                await channel.send(files=files)
            except Exception as e:
                logger.warning(f"Failed to send files: {e}")

    async def _send_files_from_data(
        self,
        channel: Any,
        file_data: list[dict[str, str]],
    ) -> None:
        """Send files to Discord from base64-encoded data.

        Args:
            channel: Discord channel
            file_data: List of FileData dicts with filename, content_base64, media_type
        """
        import base64
        from io import BytesIO

        import discord

        files = []
        for fd in file_data:
            try:
                # FileData is a Pydantic model, access attributes directly
                filename = fd.filename or "file"
                content_b64 = fd.content_base64 or ""
                content = base64.b64decode(content_b64)

                # Create Discord file from bytes
                file_obj = discord.File(BytesIO(content), filename=filename)
                files.append(file_obj)
                logger.info(f"[_send_files_from_data] Prepared file: {filename} ({len(content)} bytes)")
            except Exception as e:
                logger.error(f"[_send_files_from_data] Failed to prepare {getattr(fd, 'filename', 'unknown')}: {e}")

        if files:
            try:
                await channel.send(files=files)
                logger.info(f"[_send_files_from_data] Sent {len(files)} files to Discord")
            except Exception as e:
                logger.error(f"[_send_files_from_data] Failed to send files: {e}")

    async def _send_reaction(
        self,
        message: discord.Message,
        emoji: str,
    ) -> None:
        """Add a reaction to a Discord message.

        Args:
            message: Discord message to react to
            emoji: Emoji string to react with
        """
        try:
            await message.add_reaction(emoji)
            logger.debug(f"Added reaction {emoji} to message {message.id}")
        except Exception as e:
            logger.warning(f"Failed to add reaction: {e}")
