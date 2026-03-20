"""Loopback adapter for internal message dispatch.

Routes internal messages (scheduler tasks, subagent outputs, system events)
through the same gateway message pipeline as external platform messages,
ensuring all safety layers apply uniformly.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Callable

from mypalclara.gateway.protocol import ChannelInfo, MessageRequest, UserInfo

logger = logging.getLogger(__name__)


class LoopbackAdapter:
    """Internal adapter for dispatching messages through the gateway pipeline."""

    def __init__(self) -> None:
        self._processor: Callable[..., Any] | None = None

    def set_processor(self, processor: Callable[..., Any]) -> None:
        """Set the message processor callback.

        Args:
            processor: An async callable that accepts a MessageRequest
                       and returns a response string.
        """
        self._processor = processor

    async def send(
        self,
        content: str,
        user_id: str = "system",
        channel_id: str = "internal",
        source: str = "loopback",
        tier: str | None = None,
    ) -> None:
        """Send a message through the pipeline (fire-and-forget).

        Args:
            content: Message text content.
            user_id: User ID for the request.
            channel_id: Channel ID for the request.
            source: Source identifier (e.g. "scheduler", "subagent").
            tier: Optional model tier override ("high", "mid", "low").
        """
        if self._processor is None:
            logger.warning("LoopbackAdapter.send() called with no processor set; dropping message")
            return

        request = self._build_request(content, user_id, channel_id, source, tier)
        try:
            await self._processor(request)
        except Exception:
            logger.exception("LoopbackAdapter.send() processor raised an exception")

    async def send_and_wait(
        self,
        content: str,
        user_id: str = "system",
        channel_id: str = "internal",
        source: str = "loopback",
        tier: str | None = None,
        timeout: float = 300.0,
    ) -> str:
        """Send a message and wait for the response.

        Args:
            content: Message text content.
            user_id: User ID for the request.
            channel_id: Channel ID for the request.
            source: Source identifier.
            tier: Optional model tier override.
            timeout: Maximum seconds to wait for a response.

        Returns:
            The processor's response string.

        Raises:
            TimeoutError: If the processor does not respond within timeout.
        """
        if self._processor is None:
            logger.warning("LoopbackAdapter.send_and_wait() called with no processor set; returning empty")
            return ""

        request = self._build_request(content, user_id, channel_id, source, tier)
        try:
            result = await asyncio.wait_for(self._processor(request), timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"LoopbackAdapter.send_and_wait() timed out after {timeout}s " f"for request {request.id}"
            )
        return result if isinstance(result, str) else str(result)

    def _build_request(
        self,
        content: str,
        user_id: str,
        channel_id: str,
        source: str,
        tier: str | None,
    ) -> MessageRequest:
        """Build a MessageRequest from parameters.

        Args:
            content: Message text content.
            user_id: User ID for the request.
            channel_id: Channel ID for the request.
            source: Source identifier.
            tier: Optional model tier override.

        Returns:
            A fully constructed MessageRequest.
        """
        return MessageRequest(
            id=f"loopback-{uuid.uuid4().hex[:8]}",
            content=content,
            user=UserInfo(
                id=user_id,
                platform_id=user_id,
                name=source,
                display_name=source,
            ),
            channel=ChannelInfo(
                id=channel_id,
                type="dm",
                name="internal",
            ),
            tier_override=tier,
            metadata={"source": source, "loopback": True},
        )
