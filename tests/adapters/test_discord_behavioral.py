"""Behavioral tests for Discord gateway client parity.

These tests validate that DiscordGatewayClient maintains behavioral parity
with the original discord_bot.py implementation. Each test documents a
specific behavior that must be preserved during migration.

Test Categories:
- Message Deduplication (tests 1-3)
- Queue Management (tests 4-7)
- Tier Selection (tests 8-11)
- Response Streaming (tests 12-15)
- Tool Status Display (tests 16-18)
- Error Handling (tests 19-21)
- Image/Vision Support (tests 22-24)
"""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass, field

import pytest

from adapters.discord.gateway_client import DiscordGatewayClient, PendingResponse
from gateway.protocol import (
    ResponseStart,
    ResponseChunk,
    ResponseEnd,
    ToolStart,
    ToolResult,
    ErrorMessage,
    CancelledMessage,
    AttachmentInfo,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_discord_bot():
    """Create mock Discord bot with user info."""
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.id = 123456789
    bot.user.name = "Clara"
    return bot


@pytest.fixture
def mock_channel():
    """Create mock Discord channel."""
    channel = AsyncMock()
    channel.id = 111111111
    channel.name = "test-channel"
    channel.trigger_typing = AsyncMock()
    channel.send = AsyncMock()

    # Create mock message for send return value
    sent_msg = AsyncMock()
    sent_msg.edit = AsyncMock()
    sent_msg.add_reaction = AsyncMock()
    sent_msg.delete = AsyncMock()
    channel.send.return_value = sent_msg

    return channel


@pytest.fixture
def mock_discord_message(mock_channel, mock_discord_bot):
    """Create mock Discord message with all required attributes."""
    msg = MagicMock()
    msg.id = 333333333
    msg.author = MagicMock()
    msg.author.id = 987654321
    msg.author.name = "TestUser"
    msg.author.display_name = "Test User"
    msg.author.bot = False
    msg.channel = mock_channel
    msg.guild = MagicMock()
    msg.guild.id = 222222222
    msg.guild.name = "Test Server"
    msg.content = "Hello Clara"
    msg.attachments = []
    msg.reference = None
    msg.created_at = datetime.now()
    msg.reply = AsyncMock()
    msg.add_reaction = AsyncMock()

    # Reply returns a message
    reply_msg = AsyncMock()
    reply_msg.edit = AsyncMock()
    msg.reply.return_value = reply_msg

    return msg


@pytest.fixture
def gateway_client(mock_discord_bot):
    """Create gateway client with mocked WebSocket."""
    client = DiscordGatewayClient(mock_discord_bot, gateway_url="ws://test:18789")
    client._connected = True
    client._ws = AsyncMock()
    return client


def create_pending(
    request_id: str,
    message: MagicMock,
    response_id: str | None = None,
) -> PendingResponse:
    """Helper to create PendingResponse with defaults."""
    pending = PendingResponse(
        request_id=request_id,
        message=message,
    )
    if response_id:
        pending.response_id = response_id
    return pending
