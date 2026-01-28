"""Integration tests for email-to-Discord alert flow.

Tests the complete email alert consumer flow:
1. EmailProvider emits MESSAGE_RECEIVED event
2. email_alert_consumer processes event
3. DiscordProvider sends notification to Discord DM channel

This validates the event wiring and channel object handling required
for email alerts to reach Discord users.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.events import Event, EventType, reset_event_emitter
from gateway.main import email_alert_consumer
from gateway.providers import get_provider_manager


@pytest.fixture(autouse=True)
def reset_emitter():
    """Reset event emitter before each test to ensure clean state."""
    reset_event_emitter()
    yield
    reset_event_emitter()


@pytest.fixture
def mock_discord_provider():
    """Create a mock Discord provider with bot and send_response."""
    provider = MagicMock()
    provider.running = True

    # Mock the bot and its methods
    bot = MagicMock()
    discord_user = MagicMock()
    dm_channel = AsyncMock()

    # Wire up the async chain
    bot.fetch_user = AsyncMock(return_value=discord_user)
    discord_user.create_dm = AsyncMock(return_value=dm_channel)
    provider.bot = bot

    # Mock send_response
    provider.send_response = AsyncMock()

    return provider


@pytest.fixture
def email_event():
    """Create a sample email MESSAGE_RECEIVED event."""
    return Event(
        type=EventType.MESSAGE_RECEIVED,
        platform="email",
        user_id="discord-123456789",
        data={
            "from": "recruiter@example.com",
            "subject": "Interview Invitation - Senior Engineer",
            "preview": "We'd like to invite you for an interview...",
        },
        timestamp=datetime.now(),
    )


class TestEmailAlertConsumer:
    """Test suite for email_alert_consumer function."""

    @pytest.mark.asyncio
    async def test_1_ignores_non_email_events(self):
        """Consumer should ignore events not from email platform."""
        event = Event(
            type=EventType.MESSAGE_RECEIVED,
            platform="discord",  # Wrong platform
            user_id="discord-123456789",
            data={"subject": "Test"},
        )

        # Should return early without error
        await email_alert_consumer(event)

    @pytest.mark.asyncio
    async def test_2_skips_when_discord_provider_missing(self, email_event):
        """Consumer should skip when Discord provider not registered."""
        # Ensure no Discord provider in manager
        manager = get_provider_manager()
        manager._providers.pop("discord", None)

        # Should log warning but not raise
        await email_alert_consumer(email_event)

    @pytest.mark.asyncio
    async def test_3_skips_when_discord_provider_not_running(
        self, email_event, mock_discord_provider
    ):
        """Consumer should skip when Discord provider not running."""
        mock_discord_provider.running = False

        manager = get_provider_manager()
        manager._providers["discord"] = mock_discord_provider

        await email_alert_consumer(email_event)

        # Should not call send_response
        mock_discord_provider.send_response.assert_not_called()

    @pytest.mark.asyncio
    async def test_4_skips_when_no_user_id(self, mock_discord_provider):
        """Consumer should skip when event has no user_id."""
        event = Event(
            type=EventType.MESSAGE_RECEIVED,
            platform="email",
            user_id=None,  # Missing user
            data={"subject": "Test"},
        )

        manager = get_provider_manager()
        manager._providers["discord"] = mock_discord_provider

        await email_alert_consumer(event)

        # Should not call send_response
        mock_discord_provider.send_response.assert_not_called()

    @pytest.mark.asyncio
    async def test_5_fetches_discord_user_and_creates_dm(
        self, email_event, mock_discord_provider
    ):
        """Consumer should fetch Discord user and create DM channel."""
        manager = get_provider_manager()
        manager._providers["discord"] = mock_discord_provider

        await email_alert_consumer(email_event)

        # Should fetch user with numeric Discord ID
        mock_discord_provider.bot.fetch_user.assert_awaited_once_with(123456789)

        # Should create DM channel
        discord_user = mock_discord_provider.bot.fetch_user.return_value
        discord_user.create_dm.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_6_sends_formatted_alert_via_discord(
        self, email_event, mock_discord_provider
    ):
        """Consumer should send formatted email alert to Discord."""
        manager = get_provider_manager()
        manager._providers["discord"] = mock_discord_provider

        await email_alert_consumer(email_event)

        # Verify send_response was called
        mock_discord_provider.send_response.assert_awaited_once()

        # Extract the arguments
        call_args = mock_discord_provider.send_response.call_args
        context = call_args[0][0]
        message = call_args[0][1]

        # Verify context has channel object
        assert "channel" in context
        assert context["user_id"] == "discord-123456789"
        assert context["is_alert"] is True

        # Verify message formatting
        assert "New Email Alert" in message
        assert "recruiter@example.com" in message
        assert "Interview Invitation" in message
        assert "We'd like to invite you" in message

    @pytest.mark.asyncio
    async def test_7_handles_bot_fetch_user_error(
        self, email_event, mock_discord_provider
    ):
        """Consumer should handle errors when fetching Discord user."""
        # Make fetch_user raise an error
        mock_discord_provider.bot.fetch_user.side_effect = Exception("User not found")

        manager = get_provider_manager()
        manager._providers["discord"] = mock_discord_provider

        # Should not raise, just log warning
        await email_alert_consumer(email_event)

        # Should not call send_response
        mock_discord_provider.send_response.assert_not_called()

    @pytest.mark.asyncio
    async def test_8_handles_send_response_error(
        self, email_event, mock_discord_provider
    ):
        """Consumer should handle errors when sending Discord message."""
        # Make send_response raise an error
        mock_discord_provider.send_response.side_effect = Exception("API error")

        manager = get_provider_manager()
        manager._providers["discord"] = mock_discord_provider

        # Should not raise, just log exception
        await email_alert_consumer(email_event)

        # Verify send_response was attempted
        mock_discord_provider.send_response.assert_awaited_once()


class TestEmailAlertConsumerDMChannelWiring:
    """Test suite focused on DM channel object wiring."""

    @pytest.mark.asyncio
    async def test_dm_channel_object_passed_to_send_response(
        self, email_event, mock_discord_provider
    ):
        """Verify actual Discord channel object is passed, not string ID."""
        manager = get_provider_manager()
        manager._providers["discord"] = mock_discord_provider

        await email_alert_consumer(email_event)

        # Get the DM channel that was created
        discord_user = mock_discord_provider.bot.fetch_user.return_value
        expected_dm_channel = discord_user.create_dm.return_value

        # Verify send_response received the actual channel object
        call_args = mock_discord_provider.send_response.call_args
        context = call_args[0][0]

        assert context["channel"] is expected_dm_channel
        assert not isinstance(context["channel"], str)

    @pytest.mark.asyncio
    async def test_user_id_prefix_stripped_correctly(
        self, mock_discord_provider
    ):
        """Verify discord- prefix is stripped when extracting user ID."""
        event = Event(
            type=EventType.MESSAGE_RECEIVED,
            platform="email",
            user_id="discord-987654321",  # Prefixed format
            data={"subject": "Test"},
        )

        manager = get_provider_manager()
        manager._providers["discord"] = mock_discord_provider

        await email_alert_consumer(event)

        # Should fetch with numeric ID only
        mock_discord_provider.bot.fetch_user.assert_awaited_once_with(987654321)

    @pytest.mark.asyncio
    async def test_handles_unprefixed_user_id(
        self, mock_discord_provider
    ):
        """Consumer should handle user_id without discord- prefix."""
        event = Event(
            type=EventType.MESSAGE_RECEIVED,
            platform="email",
            user_id="555555555",  # No prefix
            data={"subject": "Test"},
        )

        manager = get_provider_manager()
        manager._providers["discord"] = mock_discord_provider

        await email_alert_consumer(event)

        # Should use the ID as-is
        mock_discord_provider.bot.fetch_user.assert_awaited_once_with(555555555)

    @pytest.mark.asyncio
    async def test_preview_truncation(
        self, mock_discord_provider
    ):
        """Consumer should truncate long email previews."""
        event = Event(
            type=EventType.MESSAGE_RECEIVED,
            platform="email",
            user_id="discord-123456789",
            data={
                "from": "test@example.com",
                "subject": "Test",
                "preview": "A" * 500,  # Very long preview
            },
        )

        manager = get_provider_manager()
        manager._providers["discord"] = mock_discord_provider

        await email_alert_consumer(event)

        # Extract message content
        call_args = mock_discord_provider.send_response.call_args
        message = call_args[0][1]

        # Should be truncated to 200 chars max in preview
        assert len(message.split("Preview: ")[1].split("...")[0]) <= 200
