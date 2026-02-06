"""WebChatAdapter — Gateway client for the web interface.

Extends GatewayClient to multiplex browser WebSocket connections
through a single gateway connection.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from adapters.base import GatewayClient
from mypalclara.gateway.protocol import ChannelInfo, UserInfo

logger = logging.getLogger("web.chat.adapter")


class WebChatAdapter(GatewayClient):
    """Gateway client for the web chat interface.

    A single instance connects to the gateway, then multiplexes
    browser WebSocket connections by request_id.
    """

    def __init__(self, gateway_url: str | None = None) -> None:
        super().__init__(
            platform="web",
            capabilities=["streaming", "tool_display"],
            gateway_url=gateway_url,
        )
        # Maps request_id -> asyncio.Queue for streaming events to browser
        self._request_queues: dict[str, asyncio.Queue] = {}
        self._background_task: asyncio.Task | None = None

    async def start_background(self) -> None:
        """Connect to gateway in the background."""
        if await self.connect():
            self._running = True
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            self._background_task = asyncio.create_task(self._receive_loop())
        else:
            raise RuntimeError("Failed to connect to gateway")

    async def stop(self) -> None:
        """Stop the adapter."""
        await self.disconnect()
        if self._background_task:
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass

    def register_request(self, request_id: str) -> asyncio.Queue:
        """Register a new browser request and return its event queue."""
        queue: asyncio.Queue = asyncio.Queue()
        self._request_queues[request_id] = queue
        return queue

    def unregister_request(self, request_id: str) -> None:
        """Remove a request's event queue."""
        self._request_queues.pop(request_id, None)

    async def send_chat_message(
        self,
        content: str,
        user_id: str,
        display_name: str,
        channel_id: str = "web-chat",
        tier_override: str | None = None,
    ) -> str:
        """Send a chat message to the gateway.

        Args:
            content: Message text.
            user_id: Prefixed user ID (e.g., web-<canonical_user_id>).
            display_name: User display name.
            channel_id: Channel identifier.
            tier_override: Optional model tier.

        Returns:
            The request_id for tracking the response stream.
        """
        user = UserInfo(
            id=user_id,
            platform_id=user_id,
            name=display_name,
            display_name=display_name,
        )
        channel = ChannelInfo(
            id=channel_id,
            type="dm",
            name="Web Chat",
        )
        return await self.send_message(
            user=user,
            channel=channel,
            content=content,
            tier_override=tier_override,
            metadata={"platform": "web"},
        )

    # ─── Gateway event handlers ─────────────────────────────────────────

    async def _dispatch(self, request_id: str, event: dict[str, Any]) -> None:
        """Send an event to the appropriate browser queue."""
        queue = self._request_queues.get(request_id)
        if queue:
            await queue.put(event)

    async def on_response_start(self, message: Any) -> None:
        await self._dispatch(
            message.request_id,
            {"type": "response_start", "model_tier": message.model_tier},
        )

    async def on_response_chunk(self, message: Any) -> None:
        await self._dispatch(
            message.request_id,
            {"type": "chunk", "text": message.chunk, "accumulated": message.accumulated},
        )

    async def on_response_end(self, message: Any) -> None:
        await self._dispatch(
            message.request_id,
            {"type": "response_end", "full_text": message.full_text, "tool_count": message.tool_count},
        )

    async def on_tool_start(self, message: Any) -> None:
        await self._dispatch(
            message.request_id,
            {
                "type": "tool_start",
                "tool_name": message.tool_name,
                "step": message.step,
                "description": message.description,
                "emoji": message.emoji,
            },
        )

    async def on_tool_result(self, message: Any) -> None:
        await self._dispatch(
            message.request_id,
            {
                "type": "tool_result",
                "tool_name": message.tool_name,
                "success": message.success,
                "output_preview": message.output_preview,
                "duration_ms": message.duration_ms,
            },
        )

    async def on_error(self, message: Any) -> None:
        request_id = getattr(message, "request_id", None)
        if request_id:
            await self._dispatch(
                request_id,
                {"type": "error", "code": message.code, "message": message.message},
            )

    async def on_cancelled(self, message: Any) -> None:
        await self._dispatch(
            message.request_id,
            {"type": "cancelled"},
        )


# Singleton instance
web_chat_adapter = WebChatAdapter()
