"""Integration tests for Discord-Gateway message flow.

Tests the DiscordGatewayClient response handling, tier extraction,
and tool status display.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.discord.gateway_client import (
    DISCORD_MSG_LIMIT,
    DiscordGatewayClient,
    PendingResponse,
)
from gateway.protocol import ResponseChunk, ResponseEnd, ResponseStart, ToolStart


@dataclass
class MockDiscordMessage:
    """Mock Discord message for testing."""

    id: int = 123456789
    content: str = "Hello Clara"
    attachments: list = field(default_factory=list)

    @dataclass
    class MockAuthor:
        id: int = 987654321
        name: str = "TestUser"
        display_name: str = "Test User"
        bot: bool = False

    @dataclass
    class MockChannel:
        id: int = 111222333
        name: str = "test-channel"

        async def trigger_typing(self) -> None:
            pass

        async def send(self, content: str = None, **kwargs) -> "MockDiscordMessage":
            return MockDiscordMessage(content=content)

    @dataclass
    class MockGuild:
        id: int = 444555666
        name: str = "Test Guild"

    author: MockAuthor = field(default_factory=MockAuthor)
    channel: MockChannel = field(default_factory=MockChannel)
    guild: MockGuild | None = field(default_factory=MockGuild)
    reference: Any = None

    async def reply(self, content: str, **kwargs) -> "MockDiscordMessage":
        return MockDiscordMessage(content=content)

    async def add_reaction(self, emoji: str) -> None:
        pass


@dataclass
class MockBot:
    """Mock Discord bot for testing."""

    @dataclass
    class MockUser:
        id: int = 999888777

    user: MockUser = field(default_factory=MockUser)


class TestPendingResponse:
    """Tests for PendingResponse dataclass."""

    def test_has_response_id_field(self):
        """PendingResponse should have response_id field."""
        mock_msg = MockDiscordMessage()
        pending = PendingResponse(request_id="req-123", message=mock_msg)

        assert hasattr(pending, "response_id")
        assert pending.response_id is None  # Default is None

    def test_response_id_can_be_set(self):
        """response_id can be set after creation."""
        mock_msg = MockDiscordMessage()
        pending = PendingResponse(request_id="req-123", message=mock_msg)
        pending.response_id = "resp-456"

        assert pending.response_id == "resp-456"


class TestTierExtraction:
    """Tests for tier prefix extraction."""

    @pytest.fixture
    def client(self):
        """Create a gateway client for testing."""
        mock_bot = MockBot()
        return DiscordGatewayClient(bot=mock_bot, gateway_url="ws://test:1234")

    @pytest.mark.parametrize(
        "content,expected_content,expected_tier",
        [
            # High tier
            ("!high What is the meaning of life?", "What is the meaning of life?", "high"),
            ("!opus Explain quantum physics", "Explain quantum physics", "high"),
            # Mid tier
            ("!mid Tell me a joke", "Tell me a joke", "mid"),
            ("!sonnet Write a poem", "Write a poem", "mid"),
            # Low tier
            ("!low Hello", "Hello", "low"),
            ("!haiku Hi there", "Hi there", "low"),
            ("!fast Quick question", "Quick question", "low"),
            # No tier prefix
            ("Just a normal message", "Just a normal message", None),
            ("Hello Clara", "Hello Clara", None),
            # Case insensitive
            ("!HIGH test", "test", "high"),
            ("!High test", "test", "high"),
            ("!MID test", "test", "mid"),
            ("!LOW test", "test", "low"),
            # Edge cases
            ("!high", "", "high"),  # Just the prefix
            ("!high  extra spaces", "extra spaces", "high"),  # Extra spaces
            ("  !high test", "test", "high"),  # Leading whitespace is stripped first
            ("!highway is blocked", "!highway is blocked", None),  # Not a tier prefix (no space after !high)
        ],
    )
    def test_extract_tier_override(self, client, content, expected_content, expected_tier):
        """Test tier prefix extraction from content."""
        clean_content, tier = client._extract_tier_override(content)

        assert clean_content == expected_content
        assert tier == expected_tier


class TestResponseIdCorrelation:
    """Tests for response ID correlation between callbacks."""

    @pytest.fixture
    def client(self):
        """Create a gateway client for testing."""
        mock_bot = MockBot()
        client = DiscordGatewayClient(bot=mock_bot, gateway_url="ws://test:1234")
        return client

    def test_get_pending_by_response_id_not_found(self, client):
        """Returns None when response_id not found."""
        result = client._get_pending_by_response_id("nonexistent")
        assert result is None

    def test_get_pending_by_response_id_found(self, client):
        """Returns PendingResponse when response_id matches."""
        mock_msg = MockDiscordMessage()
        pending = PendingResponse(request_id="req-123", message=mock_msg)
        pending.response_id = "resp-456"
        client._pending["req-123"] = pending

        result = client._get_pending_by_response_id("resp-456")
        assert result is pending

    def test_get_pending_by_response_id_multiple_pending(self, client):
        """Finds correct pending among multiple."""
        mock_msg1 = MockDiscordMessage(id=1)
        mock_msg2 = MockDiscordMessage(id=2)
        mock_msg3 = MockDiscordMessage(id=3)

        pending1 = PendingResponse(request_id="req-1", message=mock_msg1)
        pending1.response_id = "resp-1"

        pending2 = PendingResponse(request_id="req-2", message=mock_msg2)
        pending2.response_id = "resp-2"

        pending3 = PendingResponse(request_id="req-3", message=mock_msg3)
        # pending3 has no response_id yet

        client._pending["req-1"] = pending1
        client._pending["req-2"] = pending2
        client._pending["req-3"] = pending3

        # Should find correct one
        assert client._get_pending_by_response_id("resp-2") is pending2
        assert client._get_pending_by_response_id("resp-1") is pending1
        assert client._get_pending_by_response_id("resp-3") is None


class TestResponseStart:
    """Tests for on_response_start callback."""

    @pytest.fixture
    def client(self):
        """Create a gateway client for testing."""
        mock_bot = MockBot()
        return DiscordGatewayClient(bot=mock_bot, gateway_url="ws://test:1234")

    @pytest.mark.asyncio
    async def test_stores_response_id(self, client):
        """on_response_start should store response_id in pending."""
        mock_msg = MockDiscordMessage()
        mock_msg.channel = MagicMock()
        mock_msg.channel.trigger_typing = AsyncMock()

        pending = PendingResponse(request_id="req-123", message=mock_msg)
        client._pending["req-123"] = pending

        # Simulate ResponseStart message
        response_start = MagicMock()
        response_start.request_id = "req-123"
        response_start.id = "resp-456"

        await client.on_response_start(response_start)

        assert pending.response_id == "resp-456"
        mock_msg.channel.trigger_typing.assert_called_once()

    @pytest.mark.asyncio
    async def test_ignores_unknown_request_id(self, client):
        """on_response_start should ignore unknown request IDs."""
        response_start = MagicMock()
        response_start.request_id = "unknown-req"
        response_start.id = "resp-456"

        # Should not raise
        await client.on_response_start(response_start)


class TestResponseChunk:
    """Tests for on_response_chunk callback."""

    @pytest.fixture
    def client(self):
        """Create a gateway client for testing."""
        mock_bot = MockBot()
        client = DiscordGatewayClient(bot=mock_bot, gateway_url="ws://test:1234")
        client._edit_cooldown = 0  # Disable cooldown for tests
        return client

    @pytest.mark.asyncio
    async def test_uses_response_id_lookup(self, client):
        """on_response_chunk should use response_id to find pending."""
        mock_msg = MockDiscordMessage()
        mock_msg.reply = AsyncMock(return_value=MockDiscordMessage())

        pending = PendingResponse(request_id="req-123", message=mock_msg)
        pending.response_id = "resp-456"
        client._pending["req-123"] = pending

        # Simulate ResponseChunk with response_id
        chunk = MagicMock()
        chunk.id = "resp-456"  # This is the response_id
        chunk.chunk = "Hello"
        chunk.accumulated = "Hello"

        await client.on_response_chunk(chunk)

        assert pending.accumulated_text == "Hello"

    @pytest.mark.asyncio
    async def test_ignores_unknown_response_id(self, client):
        """on_response_chunk should ignore unknown response IDs."""
        chunk = MagicMock()
        chunk.id = "unknown-resp"
        chunk.chunk = "Hello"
        chunk.accumulated = None

        # Should not raise
        await client.on_response_chunk(chunk)


class TestResponseEnd:
    """Tests for on_response_end callback."""

    @pytest.fixture
    def client(self):
        """Create a gateway client for testing."""
        mock_bot = MockBot()
        return DiscordGatewayClient(bot=mock_bot, gateway_url="ws://test:1234")

    @pytest.mark.asyncio
    async def test_uses_response_id_lookup(self, client):
        """on_response_end should use response_id to find pending."""
        mock_msg = MockDiscordMessage()
        mock_msg.reply = AsyncMock(return_value=MockDiscordMessage())
        mock_msg.channel = MagicMock()
        mock_msg.channel.send = AsyncMock(return_value=MockDiscordMessage())

        pending = PendingResponse(request_id="req-123", message=mock_msg)
        pending.response_id = "resp-456"
        client._pending["req-123"] = pending

        # Simulate ResponseEnd with response_id
        end = MagicMock()
        end.id = "resp-456"  # This is the response_id
        end.full_text = "Complete response"
        end.files = []
        end.tool_count = 0

        await client.on_response_end(end)

        # Pending should be removed
        assert "req-123" not in client._pending
        mock_msg.reply.assert_called_once()

    @pytest.mark.asyncio
    async def test_removes_pending_after_completion(self, client):
        """on_response_end should remove pending from tracking."""
        mock_msg = MockDiscordMessage()
        mock_msg.reply = AsyncMock(return_value=MockDiscordMessage())

        pending = PendingResponse(request_id="req-123", message=mock_msg)
        pending.response_id = "resp-456"
        client._pending["req-123"] = pending

        end = MagicMock()
        end.id = "resp-456"
        end.full_text = "Done"
        end.files = []
        end.tool_count = 0

        await client.on_response_end(end)

        assert len(client._pending) == 0


class TestToolStart:
    """Tests for on_tool_start callback."""

    @pytest.fixture
    def client(self):
        """Create a gateway client for testing."""
        mock_bot = MockBot()
        return DiscordGatewayClient(bot=mock_bot, gateway_url="ws://test:1234")

    @pytest.mark.asyncio
    async def test_uses_response_id_lookup(self, client):
        """on_tool_start should use response_id to find pending."""
        mock_msg = MockDiscordMessage()
        mock_msg.channel = MagicMock()
        mock_msg.channel.send = AsyncMock()

        pending = PendingResponse(request_id="req-123", message=mock_msg)
        pending.response_id = "resp-456"
        client._pending["req-123"] = pending

        # Simulate ToolStart with response_id
        tool_start = MagicMock()
        tool_start.id = "resp-456"  # This is the response_id
        tool_start.tool_name = "web_search"
        tool_start.step = 1
        tool_start.emoji = ""

        await client.on_tool_start(tool_start)

        assert pending.tool_count == 1
        mock_msg.channel.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_sends_status_message(self, client):
        """on_tool_start should send tool status to channel."""
        mock_msg = MockDiscordMessage()
        mock_msg.channel = MagicMock()
        mock_msg.channel.send = AsyncMock()

        pending = PendingResponse(request_id="req-123", message=mock_msg)
        pending.response_id = "resp-456"
        client._pending["req-123"] = pending

        tool_start = MagicMock()
        tool_start.id = "resp-456"
        tool_start.tool_name = "python_execute"
        tool_start.step = 2
        tool_start.emoji = ""

        await client.on_tool_start(tool_start)

        # Check the status message format
        call_args = mock_msg.channel.send.call_args
        assert "python_execute" in call_args.args[0]
        assert "step 2" in call_args.args[0]


class TestMessageSplitting:
    """Tests for message splitting for Discord limits."""

    @pytest.fixture
    def client(self):
        """Create a gateway client for testing."""
        mock_bot = MockBot()
        return DiscordGatewayClient(bot=mock_bot, gateway_url="ws://test:1234")

    def test_short_message_not_split(self, client):
        """Short messages should not be split."""
        text = "Hello, this is a short message."
        chunks = client._split_message(text)

        assert len(chunks) == 1
        assert chunks[0] == text

    def test_long_message_split(self, client):
        """Long messages should be split at line boundaries."""
        # Create a message longer than DISCORD_MSG_LIMIT
        lines = ["Line " + str(i) + "\n" for i in range(500)]
        text = "".join(lines)

        chunks = client._split_message(text)

        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= DISCORD_MSG_LIMIT

    def test_very_long_single_line_not_split(self, client):
        """Messages without line breaks cannot be split at line boundaries.

        Note: This documents current behavior. A very long single line will
        exceed Discord's limit because _split_message only splits on newlines.
        The _format_response method handles truncation separately.
        """
        text = "x" * 5000  # 5000 chars, over the limit, no line breaks
        chunks = client._split_message(text)

        # Current behavior: returns single chunk (not truncated)
        # because there are no line break opportunities
        assert len(chunks) == 1
        # Note: This chunk exceeds the limit - calling code should use
        # _format_response for truncation when needed


class TestFormatResponse:
    """Tests for response formatting."""

    @pytest.fixture
    def client(self):
        """Create a gateway client for testing."""
        mock_bot = MockBot()
        return DiscordGatewayClient(bot=mock_bot, gateway_url="ws://test:1234")

    def test_adds_typing_indicator_in_progress(self, client):
        """In-progress responses should have typing indicator."""
        text = "Hello"
        formatted = client._format_response(text, in_progress=True)

        # Typing indicator is the block character
        assert formatted.endswith("\u258c")  # Unicode LEFT HALF BLOCK

    def test_no_typing_indicator_when_complete(self, client):
        """Complete responses should not have typing indicator."""
        text = "Hello"
        formatted = client._format_response(text, in_progress=False)

        assert not formatted.endswith("\u258c")
        assert formatted == text

    def test_truncates_long_messages(self, client):
        """Long messages should be truncated."""
        text = "x" * 3000  # Over limit
        formatted = client._format_response(text, in_progress=False)

        assert len(formatted) <= DISCORD_MSG_LIMIT
        assert formatted.endswith("...")
