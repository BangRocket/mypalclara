"""Teams gateway client for the Clara Gateway.

Extends the base GatewayClient to handle Teams-specific message
formatting and Adaptive Card rendering.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from botbuilder.core import TurnContext
from botbuilder.schema import Activity, ActivityTypes, Attachment

from adapters.base import GatewayClient
from adapters.teams.message_builder import AdaptiveCardBuilder
from config.logging import get_logger
from gateway.protocol import ChannelInfo, UserInfo

if TYPE_CHECKING:
    from adapters.teams.bot import TeamsBot

logger = get_logger("adapters.teams.gateway")

# Teams message limit (for plain text)
TEAMS_MSG_LIMIT = 28000  # Adaptive cards have higher limits


@dataclass
class PendingResponse:
    """Tracks an in-flight response for streaming."""

    request_id: str
    turn_context: TurnContext
    started_at: datetime = field(default_factory=datetime.now)
    accumulated_text: str = ""
    tool_count: int = 0
    last_update: datetime | None = None
    status_activity_id: str | None = None


class TeamsGatewayClient(GatewayClient):
    """Teams-specific gateway client.

    Handles Teams message formatting, Adaptive Cards, and streaming updates.
    """

    def __init__(
        self,
        gateway_url: str | None = None,
    ) -> None:
        """Initialize the Teams gateway client.

        Args:
            gateway_url: Optional gateway URL override
        """
        super().__init__(
            platform="teams",
            capabilities=["streaming", "cards", "attachments", "reactions"],
            gateway_url=gateway_url,
        )
        self.bot: TeamsBot | None = None
        self._pending: dict[str, PendingResponse] = {}
        self._update_cooldown = 1.0  # Seconds between updates (Teams is slower)
        self._card_builder = AdaptiveCardBuilder()

    async def send_teams_message(
        self,
        turn_context: TurnContext,
        tier_override: str | None = None,
    ) -> str | None:
        """Send a Teams message to the gateway for processing.

        Args:
            turn_context: Bot Framework turn context
            tier_override: Optional model tier override

        Returns:
            Request ID if sent, None if failed
        """
        try:
            activity = turn_context.activity

            # Build user info
            user = UserInfo(
                id=f"teams-{activity.from_property.id}",
                platform_id=activity.from_property.id,
                name=activity.from_property.name,
                display_name=activity.from_property.name,
            )

            # Build channel info
            conversation = activity.conversation
            is_group = conversation.is_group if hasattr(conversation, "is_group") else False

            channel = ChannelInfo(
                id=conversation.id,
                type="group" if is_group else "personal",
                name=conversation.name if hasattr(conversation, "name") else None,
                guild_id=activity.channel_id,
                guild_name=None,  # Teams doesn't have guild names in the same way
            )

            # Clean content (remove @mentions)
            content = self._clean_content(activity.text or "", activity)

            # Build reply chain from conversation reference
            reply_chain = await self._build_reply_chain(turn_context)

            # Send to gateway
            request_id = await self.send_message(
                user=user,
                channel=channel,
                content=content,
                tier_override=tier_override,
                reply_chain=reply_chain,
                metadata={
                    "platform": "teams",
                    "activity_id": activity.id,
                    "conversation_id": conversation.id,
                    "is_group": is_group,
                },
            )

            # Track pending response
            self._pending[request_id] = PendingResponse(
                request_id=request_id,
                turn_context=turn_context,
            )

            return request_id

        except Exception as e:
            logger.exception(f"Failed to send message to gateway: {e}")
            return None

    def _clean_content(self, content: str, activity: Activity) -> str:
        """Clean message content by removing bot mentions.

        Args:
            content: Raw message content
            activity: The activity containing mention data

        Returns:
            Cleaned content
        """
        # Remove mentions from Teams messages
        if activity.entities:
            for entity in activity.entities:
                if entity.type == "mention":
                    mentioned = entity.additional_properties.get("mentioned", {})
                    mention_text = entity.additional_properties.get("text", "")
                    if mention_text:
                        content = content.replace(mention_text, "").strip()

        return content.strip()

    async def _build_reply_chain(
        self,
        turn_context: TurnContext,
        max_messages: int = 5,
    ) -> list[dict[str, Any]]:
        """Build conversation history from Teams context.

        Note: Teams doesn't provide easy access to conversation history
        like Discord does. This is a placeholder for future enhancement.

        Args:
            turn_context: Bot Framework turn context
            max_messages: Maximum messages to include

        Returns:
            List of message dicts with role and content
        """
        # Teams doesn't expose conversation history easily
        # Would need to use Graph API for full history
        # For now, return empty chain
        return []

    async def on_response_start(self, message: Any) -> None:
        """Handle response start."""
        request_id = message.request_id
        pending = self._pending.get(request_id)
        if not pending:
            return

        # Send typing indicator
        try:
            await pending.turn_context.send_activity(Activity(type=ActivityTypes.typing))
        except Exception as e:
            logger.debug(f"Failed to send typing: {e}")

        logger.debug(f"Response started for {request_id}")

    async def on_response_chunk(self, message: Any) -> None:
        """Handle streaming response chunk."""
        request_id = message.request_id
        pending = self._pending.get(request_id)
        if not pending:
            return

        pending.accumulated_text = message.accumulated or (pending.accumulated_text + message.chunk)

        # Rate-limit updates (Teams is slower than Discord)
        now = datetime.now()
        if pending.last_update:
            elapsed = (now - pending.last_update).total_seconds()
            if elapsed < self._update_cooldown:
                return

        # Update or send status
        try:
            # For Teams, we typically wait for completion rather than
            # streaming updates, as editing messages is more expensive
            # Just update typing indicator
            await pending.turn_context.send_activity(Activity(type=ActivityTypes.typing))
            pending.last_update = now
        except Exception as e:
            logger.debug(f"Update error: {e}")

    async def on_response_end(self, message: Any) -> None:
        """Handle response completion."""
        request_id = message.request_id
        pending = self._pending.pop(request_id, None)
        if not pending:
            logger.debug(f"No pending request for response end {request_id}")
            return

        # Send final response
        try:
            full_text = message.full_text
            tool_count = message.tool_count

            # Build response activity
            if len(full_text) > TEAMS_MSG_LIMIT or tool_count > 0:
                # Use Adaptive Card for long responses or when tools were used
                card = self._card_builder.build_response_card(
                    text=full_text,
                    tool_count=tool_count,
                )
                activity = Activity(
                    type=ActivityTypes.message,
                    attachments=[
                        Attachment(
                            content_type="application/vnd.microsoft.card.adaptive",
                            content=card,
                        )
                    ],
                )
            else:
                # Plain text for simple responses
                activity = Activity(
                    type=ActivityTypes.message,
                    text=full_text,
                )

            await pending.turn_context.send_activity(activity)

            # Handle file attachments
            files_to_send = message.files
            if files_to_send:
                await self._send_files(pending.turn_context, files_to_send)

        except Exception as e:
            logger.exception(f"Failed to send final response: {e}")

        logger.info(f"Response {request_id} complete: " f"{len(message.full_text)} chars, {message.tool_count} tools")

    async def on_tool_start(self, message: Any) -> None:
        """Handle tool execution start."""
        request_id = message.request_id
        pending = self._pending.get(request_id)
        if not pending:
            return

        pending.tool_count = message.step

        # Send tool status card
        try:
            card = self._card_builder.build_tool_status_card(
                tool_name=message.tool_name,
                step=message.step,
                emoji=message.emoji,
            )
            activity = Activity(
                type=ActivityTypes.message,
                attachments=[
                    Attachment(
                        content_type="application/vnd.microsoft.card.adaptive",
                        content=card,
                    )
                ],
            )
            await pending.turn_context.send_activity(activity)
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
            try:
                error_card = self._card_builder.build_error_card(error_message=message.message[:200])
                activity = Activity(
                    type=ActivityTypes.message,
                    attachments=[
                        Attachment(
                            content_type="application/vnd.microsoft.card.adaptive",
                            content=error_card,
                        )
                    ],
                )
                await pending.turn_context.send_activity(activity)
            except Exception:
                pass

    async def on_cancelled(self, message: Any) -> None:
        """Handle request cancellation."""
        await super().on_cancelled(message)

        request_id = message.request_id
        pending = self._pending.pop(request_id, None)
        if pending:
            try:
                await pending.turn_context.send_activity(
                    Activity(
                        type=ActivityTypes.message,
                        text="Request cancelled.",
                    )
                )
            except Exception:
                pass

    async def _send_files(
        self,
        turn_context: TurnContext,
        file_paths: list[str],
    ) -> None:
        """Send files to Teams conversation.

        Note: Teams file handling is more complex than Discord.
        Files typically need to be uploaded to SharePoint/OneDrive first.
        This is a placeholder for full implementation.

        Args:
            turn_context: Bot Framework turn context
            file_paths: List of file paths to send
        """
        from pathlib import Path

        for path_str in file_paths:
            path = Path(path_str)
            if path.exists():
                # For now, just mention the file
                # Full implementation would upload to SharePoint
                await turn_context.send_activity(
                    Activity(
                        type=ActivityTypes.message,
                        text=f"File ready: {path.name}",
                    )
                )
                logger.info(f"File mentioned: {path.name}")
