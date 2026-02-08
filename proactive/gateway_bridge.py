"""Bridge between ORS engine and the gateway protocol.

Provides two things:
1. A duck-typed client replacement for Discord's Client — ORS calls
   client.send_proactive_message() which routes through the gateway.
2. A context enricher function that feeds Rook memories, emotional
   context, and recurring topics into ORS's gather_full_context().
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from config.logging import get_logger
from mypalclara.gateway.protocol import ChannelInfo, ProactiveMessage, UserInfo

if TYPE_CHECKING:
    from collections.abc import Callable

    from mypalclara.gateway.processor import MessageProcessor
    from mypalclara.gateway.server import GatewayServer

logger = get_logger("proactive.bridge")

# Module-level reference set when GatewayORSBridge is instantiated.
# Used by the scheduler tool to send scheduled messages without needing
# the server object directly.
_bridge: "GatewayORSBridge | None" = None


class GatewayORSBridge:
    """Bridges ORS engine to gateway protocol.

    Duck-types the ``client`` parameter that ORS passes around.
    The engine calls ``client.send_proactive_message(...)`` — this class
    routes it through the gateway's ``broadcast_to_platform()`` so the
    appropriate adapter receives a ``ProactiveMessage``.
    """

    def __init__(self, server: GatewayServer, processor: MessageProcessor) -> None:
        global _bridge
        self._server = server
        self._processor = processor
        _bridge = self

    async def send_proactive_message(
        self,
        user_id: str,
        channel_id: str,
        message: str,
        purpose: str,
    ) -> bool:
        """Send a proactive message via the gateway protocol.

        Args:
            user_id: Prefixed user ID (e.g. "discord-123")
            channel_id: Channel ID where the last interaction happened
            message: The message content
            purpose: Why ORS is reaching out

        Returns:
            True if at least one adapter received the message
        """
        # Determine platform from user_id prefix (e.g. "discord-123" -> "discord")
        platform = user_id.split("-")[0] if "-" in user_id else "unknown"

        # Extract the platform user ID (everything after the first dash)
        platform_user_id = user_id.split("-", 1)[1] if "-" in user_id else user_id

        proto_msg = ProactiveMessage(
            user=UserInfo(
                id=user_id,
                platform_id=platform_user_id,
            ),
            channel=ChannelInfo(
                id=channel_id,
                type="dm",  # ORS proactive messages are typically DMs
            ),
            content=message,
            priority="normal",
        )

        count = await self._server.broadcast_to_platform(platform, proto_msg)
        if count > 0:
            logger.info(f"Proactive message sent via gateway to {platform} ({count} node(s))")
            return True

        logger.warning(f"No connected {platform} adapters to receive proactive message")
        return False

    def get_context_enricher(self) -> Callable[[str], dict[str, Any]]:
        """Return an enricher function for ``gather_full_context()``.

        The enricher pulls data from the same sources the gateway
        processor already queries (Rook memories, emotional context,
        recurring topics) so ORS assessments benefit from richer context.
        """

        def enrich(user_id: str) -> dict[str, Any]:
            result: dict[str, Any] = {}
            mm = self._processor._memory_manager
            if not mm:
                return result

            try:
                mems, _, _ = mm.fetch_mem0_context(user_id, None, "")
                if mems:
                    result["user_memories"] = [m if isinstance(m, str) else str(m) for m in mems[:10]]
            except Exception as e:
                logger.debug(f"Enrichment: mem0 fetch failed: {e}")

            try:
                emo = mm.fetch_emotional_context(user_id, limit=3)
                if emo:
                    result["emotional_context"] = emo
            except Exception as e:
                logger.debug(f"Enrichment: emotional context failed: {e}")

            try:
                topics = mm.fetch_recurring_topics(user_id, min_mentions=2, lookback_days=14)
                if topics:
                    result["recurring_topics"] = topics[:10]
            except Exception as e:
                logger.debug(f"Enrichment: recurring topics failed: {e}")

            return result

        return enrich
