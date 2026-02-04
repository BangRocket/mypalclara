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
            capabilities=["streaming", "attachments", "reactions"],
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
            chunks = split_message(full_text)

            # Send all chunks as replies
            for i, chunk in enumerate(chunks):
                if i == 0:
                    await pending.message.reply(chunk, mention_author=False)
                else:
                    await pending.message.channel.send(chunk)

            # Handle file attachments
            files_to_send = message.files
            if files_to_send:
                await self._send_files(pending.message.channel, files_to_send)

        except Exception as e:
            logger.exception(f"Failed to send final response: {e}")

        logger.info(f"Response {request_id} complete: {len(message.full_text)} chars, {message.tool_count} tools")

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
            if path.exists():
                files.append(discord.File(path))

        if files:
            try:
                await channel.send(files=files)
            except Exception as e:
                logger.warning(f"Failed to send files: {e}")
