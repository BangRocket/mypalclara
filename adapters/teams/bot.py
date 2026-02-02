"""Microsoft Teams Bot implementation using Bot Framework SDK.

This module handles Teams-specific activity processing and routes
messages to the gateway for AI processing.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from botbuilder.core import ActivityHandler, TurnContext
from botbuilder.schema import Activity, ActivityTypes, ChannelAccount

from config.logging import get_logger

if TYPE_CHECKING:
    from adapters.teams.gateway_client import TeamsGatewayClient

logger = get_logger("adapters.teams.bot")


class TeamsBot(ActivityHandler):
    """Bot Framework activity handler for Teams.

    Processes incoming activities (messages, reactions, etc.) and routes
    them to the Clara Gateway for AI-powered responses.
    """

    def __init__(self, gateway_client: "TeamsGatewayClient") -> None:
        """Initialize the Teams bot.

        Args:
            gateway_client: Gateway client for message processing
        """
        super().__init__()
        self.gateway_client = gateway_client
        self._pending_contexts: dict[str, TurnContext] = {}

    async def on_message_activity(self, turn_context: TurnContext) -> None:
        """Handle incoming message activity.

        Args:
            turn_context: Bot Framework turn context
        """
        activity = turn_context.activity

        # Log message receipt
        logger.info(
            f"Message from {activity.from_property.name} "
            f"({activity.from_property.id}): {activity.text[:50] if activity.text else '[no text]'}..."
        )

        # Check if gateway is connected
        if not self.gateway_client or not self.gateway_client.is_connected:
            logger.warning("Gateway not connected, skipping message")
            await turn_context.send_activity("I'm having trouble connecting right now. Please try again.")
            return

        # Send typing indicator
        await turn_context.send_activity(Activity(type=ActivityTypes.typing))

        # Detect tier override from message
        tier_override = self._detect_tier(activity.text or "")

        # Send to gateway
        try:
            request_id = await self.gateway_client.send_teams_message(
                turn_context=turn_context,
                tier_override=tier_override,
            )

            if request_id:
                # Store context for response handling
                self._pending_contexts[request_id] = turn_context
                logger.debug(f"Message sent to gateway: {request_id}")
        except Exception as e:
            logger.exception(f"Failed to send to gateway: {e}")
            await turn_context.send_activity("Sorry, I encountered an error processing your message.")

    async def on_members_added_activity(
        self,
        members_added: list[ChannelAccount],
        turn_context: TurnContext,
    ) -> None:
        """Handle new members added to conversation.

        Args:
            members_added: List of new members
            turn_context: Bot Framework turn context
        """
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                # Welcome new user
                await turn_context.send_activity("Hello! I'm Clara, your AI assistant. " "How can I help you today?")

    async def on_conversation_update_activity(self, turn_context: TurnContext) -> None:
        """Handle conversation update activities.

        Args:
            turn_context: Bot Framework turn context
        """
        await super().on_conversation_update_activity(turn_context)

    async def on_reactions_added(
        self,
        message_reactions: list[Any],
        turn_context: TurnContext,
    ) -> None:
        """Handle reaction added to message.

        Args:
            message_reactions: List of reactions added
            turn_context: Bot Framework turn context
        """
        for reaction in message_reactions:
            logger.debug(f"Reaction added: {reaction.type}")

    async def on_reactions_removed(
        self,
        message_reactions: list[Any],
        turn_context: TurnContext,
    ) -> None:
        """Handle reaction removed from message.

        Args:
            message_reactions: List of reactions removed
            turn_context: Bot Framework turn context
        """
        for reaction in message_reactions:
            logger.debug(f"Reaction removed: {reaction.type}")

    def _detect_tier(self, content: str) -> str | None:
        """Detect tier override from message prefix.

        Args:
            content: Message content

        Returns:
            Tier name or None
        """
        content_lower = content.lower().strip()

        tier_prefixes = {
            "!high": "high",
            "!opus": "high",
            "!mid": "mid",
            "!sonnet": "mid",
            "!low": "low",
            "!haiku": "low",
            "!fast": "low",
        }

        for prefix, tier in tier_prefixes.items():
            if content_lower.startswith(prefix):
                return tier

        return None

    def get_context(self, request_id: str) -> TurnContext | None:
        """Get stored turn context for a request.

        Args:
            request_id: The request ID

        Returns:
            TurnContext if found
        """
        return self._pending_contexts.get(request_id)

    def remove_context(self, request_id: str) -> TurnContext | None:
        """Remove and return stored turn context.

        Args:
            request_id: The request ID

        Returns:
            TurnContext if found
        """
        return self._pending_contexts.pop(request_id, None)
