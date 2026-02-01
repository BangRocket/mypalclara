"""Integration tests for gateway + cognition pipeline.

Tests the full message flow:
1. MessageRequest through gateway processor
2. Conversion to CognitionEvent
3. Processing through cognition pipeline
4. Tool execution with rate limiting
5. Response streaming

These tests use mocks for external dependencies (LLM, memory, tools)
but test the real integration between gateway and pipeline.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clara_core.cognition import (
    CognitionEvent,
    CognitionPipeline,
    EventMetadata,
    EventType,
    PipelineConfig,
    RateLimitConfig,
    RejectedEvent,
    ResponseCompleteEvent,
    TextChunkEvent,
    ToolCallEvent,
)
from gateway.protocol import (
    ChannelInfo,
    MessageRequest,
    ResponseChunk,
    ResponseEnd,
    ResponseStart,
    ToolResult,
    ToolStart,
    UserInfo,
)


# ============================================================================
# Test Fixtures
# ============================================================================


@dataclass
class MockWebSocket:
    """Mock WebSocket for testing."""

    messages: list[str]

    def __init__(self):
        self.messages = []

    async def send(self, data: str) -> None:
        self.messages.append(data)


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket."""
    return MockWebSocket()


@pytest.fixture
def sample_request():
    """Create a sample MessageRequest."""
    return MessageRequest(
        id="test-123",
        user=UserInfo(
            id="discord-12345",
            platform_id="12345",
            name="testuser",
            display_name="Test User",
        ),
        channel=ChannelInfo(
            id="channel-456",
            type="server",
            name="general",
            guild_id="guild-789",
            guild_name="Test Server",
        ),
        content="Hello Clara, what is 2+2?",
        attachments=[],
        reply_chain=[],
        tier_override=None,
        metadata={"platform": "discord"},
    )


@pytest.fixture
def dm_request():
    """Create a sample DM MessageRequest."""
    return MessageRequest(
        id="test-dm-456",
        user=UserInfo(
            id="discord-12345",
            platform_id="12345",
            name="testuser",
            display_name="Test User",
        ),
        channel=ChannelInfo(
            id="dm-channel-123",
            type="dm",
            name=None,
            guild_id=None,
            guild_name=None,
        ),
        content="Run some Python code for me",
        attachments=[],
        reply_chain=[],
        tier_override="high",
        metadata={"platform": "discord"},
    )


@pytest.fixture
def mock_memory_manager():
    """Create a mock MemoryManager."""
    mm = MagicMock()
    mm.fetch_mem0_context = MagicMock(return_value=([], [], []))
    mm.build_prompt = MagicMock(
        return_value=[
            {"role": "system", "content": "You are Clara."},
            {"role": "user", "content": "Hello"},
        ]
    )
    mm.add_to_memory = MagicMock()
    return mm


@pytest.fixture
def mock_llm():
    """Create a mock LLM function."""

    def llm(messages):
        return "Hello! 2+2 equals 4."

    return llm


# ============================================================================
# Pipeline Integration Tests
# ============================================================================


class TestPipelineIntegration:
    """Tests for cognition pipeline message processing."""

    @pytest.mark.asyncio
    async def test_simple_message_through_pipeline(
        self, mock_memory_manager, mock_llm
    ):
        """Test a simple message flows through the pipeline."""
        pipeline = CognitionPipeline(
            memory_manager=mock_memory_manager,
            llm_fn=mock_llm,
        )

        event = CognitionEvent(
            type=EventType.MESSAGE,
            payload={
                "content": "Hello Clara!",
                "is_dm": True,
                "has_mention": True,
            },
            metadata=EventMetadata(
                request_id="test-123",
                user_id="user-1",
                channel_id="channel-1",
                source="discord",
            ),
        )

        # Mock the responder's generate method to yield simple response
        with patch.object(
            pipeline.responder,
            "generate",
            return_value=self._async_gen(
                [
                    TextChunkEvent(text="Hello! ", request_id="test-123"),
                    TextChunkEvent(text="How can I help?", request_id="test-123"),
                    ResponseCompleteEvent(
                        full_text="Hello! How can I help?",
                        tool_count=0,
                        request_id="test-123",
                    ),
                ]
            ),
        ):
            events = []
            async for e in pipeline.process(event, tools=[]):
                events.append(e)

        # Should have text chunks and completion
        assert len(events) == 3
        assert isinstance(events[0], TextChunkEvent)
        assert isinstance(events[1], TextChunkEvent)
        assert isinstance(events[2], ResponseCompleteEvent)
        assert events[2].full_text == "Hello! How can I help?"

    @pytest.mark.asyncio
    async def test_tool_call_event_yielded(self, mock_memory_manager, mock_llm):
        """Test that tool calls are yielded as events."""
        pipeline = CognitionPipeline(
            memory_manager=mock_memory_manager,
            llm_fn=mock_llm,
        )

        event = CognitionEvent(
            type=EventType.MESSAGE,
            payload={
                "content": "Calculate 10 * 5",
                "is_dm": True,
                "has_mention": True,
            },
            metadata=EventMetadata(
                request_id="test-456",
                user_id="user-1",
                channel_id="channel-1",
            ),
        )

        # Mock responder to yield a tool call
        with patch.object(
            pipeline.responder,
            "generate",
            return_value=self._async_gen(
                [
                    ToolCallEvent(
                        tool_name="execute_python",
                        tool_args={"code": "print(10 * 5)"},
                        call_id="call-1",
                        request_id="test-456",
                    ),
                ]
            ),
        ):
            events = []
            async for e in pipeline.process(event, tools=[]):
                events.append(e)

        # Should yield the tool call (not execute it)
        assert len(events) == 1
        assert isinstance(events[0], ToolCallEvent)
        assert events[0].tool_name == "execute_python"
        assert events[0].tool_args == {"code": "print(10 * 5)"}

    @pytest.mark.asyncio
    async def test_tool_result_reentry(self, mock_memory_manager, mock_llm):
        """Test that tool results can re-enter the pipeline."""
        config = PipelineConfig(
            router_config=RateLimitConfig(
                max_tool_calls_per_request=10,
                max_tool_calls_per_minute=20,
            ),
        )
        pipeline = CognitionPipeline(
            config=config,
            memory_manager=mock_memory_manager,
            llm_fn=mock_llm,
        )

        # First, send a TOOL_RESULT event
        tool_result_event = CognitionEvent(
            type=EventType.TOOL_RESULT,
            payload={
                "result": "50",
                "tool_name": "execute_python",
                "call_id": "call-1",
                "success": True,
            },
            metadata=EventMetadata(
                request_id="test-789",
                user_id="user-1",
                channel_id="channel-1",
            ),
        )

        # Mock responder to yield completion after tool result
        with patch.object(
            pipeline.responder,
            "generate",
            return_value=self._async_gen(
                [
                    TextChunkEvent(
                        text="The result is 50.",
                        request_id="test-789",
                    ),
                    ResponseCompleteEvent(
                        full_text="The result is 50.",
                        tool_count=1,
                        request_id="test-789",
                    ),
                ]
            ),
        ):
            events = []
            async for e in pipeline.process(tool_result_event, tools=[]):
                events.append(e)

        # Should continue processing after tool result
        assert len(events) == 2
        assert isinstance(events[0], TextChunkEvent)
        assert isinstance(events[1], ResponseCompleteEvent)

    @pytest.mark.asyncio
    async def test_rate_limit_enforcement(self, mock_memory_manager, mock_llm):
        """Test that rate limits are enforced on tool calls."""
        config = PipelineConfig(
            router_config=RateLimitConfig(
                max_tool_calls_per_request=2,  # Low limit for testing
                max_tool_calls_per_minute=10,
            ),
        )
        pipeline = CognitionPipeline(
            config=config,
            memory_manager=mock_memory_manager,
            llm_fn=mock_llm,
        )

        request_id = "rate-limit-test"

        # Send multiple tool results to trigger rate limit
        for i in range(3):
            tool_result = CognitionEvent(
                type=EventType.TOOL_RESULT,
                payload={
                    "result": f"Result {i}",
                    "tool_name": "execute_python",
                    "call_id": f"call-{i}",
                },
                metadata=EventMetadata(
                    request_id=request_id,  # Same request_id
                    user_id="user-1",
                    channel_id="channel-1",
                ),
            )

            # Mock responder - only first 2 should pass
            with patch.object(
                pipeline.responder,
                "generate",
                return_value=self._async_gen(
                    [
                        ResponseCompleteEvent(
                            full_text=f"Done {i}",
                            tool_count=i + 1,
                            request_id=request_id,
                        ),
                    ]
                ),
            ):
                events = []
                async for e in pipeline.process(tool_result, tools=[]):
                    events.append(e)

                if i < 2:
                    # First two should succeed
                    assert len(events) == 1
                    assert isinstance(events[0], ResponseCompleteEvent)
                else:
                    # Third should be rate limited
                    assert len(events) == 1
                    assert isinstance(events[0], RejectedEvent)
                    # Check for rate limit keywords in reason
                    reason_lower = events[0].reason.lower()
                    assert "limit" in reason_lower or "per-request" in reason_lower

    async def _async_gen(self, items):
        """Helper to create async generator from list."""
        for item in items:
            yield item


# ============================================================================
# Request Conversion Tests
# ============================================================================


class TestRequestConversion:
    """Tests for MessageRequest to CognitionEvent conversion."""

    def test_server_message_conversion(self, sample_request):
        """Test conversion of server message to CognitionEvent."""
        from gateway.processor import MessageProcessor

        processor = MessageProcessor()
        event = processor._request_to_event(sample_request)

        assert event.type == EventType.MESSAGE
        assert "Hello Clara" in event.content
        assert "[Test User]:" in event.content  # Display name prefix for server
        assert event.metadata.request_id == "test-123"
        assert event.metadata.user_id == "discord-12345"
        assert event.metadata.channel_id == "channel-456"
        assert event.payload["is_dm"] is False
        assert event.payload["has_mention"] is True

    def test_dm_message_conversion(self, dm_request):
        """Test conversion of DM to CognitionEvent."""
        from gateway.processor import MessageProcessor

        processor = MessageProcessor()
        event = processor._request_to_event(dm_request)

        assert event.type == EventType.MESSAGE
        # DMs should NOT have display name prefix
        assert "[Test User]:" not in event.content
        assert event.content == "Run some Python code for me"
        assert event.payload["is_dm"] is True
        assert event.payload["tier_override"] == "high"


# ============================================================================
# Discord Adapter Integration Tests
# ============================================================================


class TestDiscordAdapterIntegration:
    """Tests for Discord adapter gateway integration."""

    def test_to_gateway_request_format(self):
        """Test Discord message to gateway request conversion."""
        from adapters.discord.adapter import DiscordAdapter

        # Create mock Discord message
        mock_author = MagicMock()
        mock_author.id = 12345
        mock_author.name = "testuser"
        mock_author.display_name = "Test User"

        mock_channel = MagicMock()
        mock_channel.id = 456
        mock_channel.name = "general"

        mock_guild = MagicMock()
        mock_guild.id = 789
        mock_guild.name = "Test Server"

        mock_msg = MagicMock()
        mock_msg.id = 999
        mock_msg.author = mock_author
        mock_msg.channel = mock_channel
        mock_msg.guild = mock_guild
        mock_msg.content = "Hello Clara!"

        # Create adapter with mock bot
        adapter = DiscordAdapter(bot=MagicMock())

        # Convert to gateway request
        request = adapter.to_gateway_request(mock_msg)

        assert request["type"] == "message"
        assert request["id"] == "discord-999"
        assert request["user"]["id"] == "discord-12345"
        assert request["user"]["name"] == "testuser"
        assert request["channel"]["id"] == "456"
        assert request["channel"]["type"] == "server"
        assert request["channel"]["guild_name"] == "Test Server"
        assert request["content"] == "Hello Clara!"
        assert request["metadata"]["platform"] == "discord"

    def test_dm_to_gateway_request_format(self):
        """Test Discord DM to gateway request conversion."""
        from adapters.discord.adapter import DiscordAdapter

        # Create mock Discord DM
        mock_author = MagicMock()
        mock_author.id = 12345
        mock_author.name = "testuser"
        mock_author.display_name = "Test User"

        mock_channel = MagicMock()
        mock_channel.id = 456
        mock_channel.name = None  # DMs don't have names

        mock_msg = MagicMock()
        mock_msg.id = 999
        mock_msg.author = mock_author
        mock_msg.channel = mock_channel
        mock_msg.guild = None  # DMs have no guild
        mock_msg.content = "Private message"

        adapter = DiscordAdapter(bot=MagicMock())
        request = adapter.to_gateway_request(mock_msg)

        assert request["channel"]["type"] == "dm"
        assert request["channel"]["guild_id"] is None
        assert request["metadata"]["is_dm"] is True


# ============================================================================
# End-to-End Flow Tests
# ============================================================================


class TestEndToEndFlow:
    """End-to-end tests for gateway -> pipeline -> response."""

    @pytest.mark.asyncio
    async def test_full_message_flow(self, sample_request, mock_websocket):
        """Test complete message flow through gateway processor."""
        from gateway.processor import MessageProcessor

        processor = MessageProcessor()

        # Mock dependencies
        mock_mm = MagicMock()
        mock_mm.fetch_mem0_context = MagicMock(return_value=([], [], []))
        mock_mm.build_prompt = MagicMock(
            return_value=[
                {"role": "system", "content": "You are Clara."},
                {"role": "user", "content": "Hello"},
            ]
        )
        mock_mm.add_to_memory = MagicMock()

        mock_te = MagicMock()
        mock_te.get_all_tools = MagicMock(return_value=[])

        # Create mock pipeline that yields simple response
        mock_pipeline = MagicMock()

        async def mock_process(event, tools):
            yield TextChunkEvent(text="Hello! ", request_id=event.request_id)
            yield TextChunkEvent(text="I can help.", request_id=event.request_id)
            yield ResponseCompleteEvent(
                full_text="Hello! I can help.",
                tool_count=0,
                request_id=event.request_id,
            )

        mock_pipeline.process = mock_process
        mock_pipeline.reset_request = MagicMock()

        # Set up processor
        processor._initialized = True
        processor._memory_manager = mock_mm
        processor._tool_executor = mock_te
        processor._pipeline = mock_pipeline

        # Process request
        mock_server = MagicMock()
        await processor.process(sample_request, mock_websocket, mock_server)

        # Verify messages sent to websocket
        import json

        messages = [json.loads(m) for m in mock_websocket.messages]

        # Should have: response_start, 2 chunks, response_end
        assert len(messages) == 4

        assert messages[0]["type"] == "response_start"
        assert messages[1]["type"] == "response_chunk"
        assert messages[1]["chunk"] == "Hello! "
        assert messages[2]["type"] == "response_chunk"
        assert messages[2]["chunk"] == "I can help."
        assert messages[3]["type"] == "response_end"
        assert messages[3]["full_text"] == "Hello! I can help."

    @pytest.mark.asyncio
    async def test_tool_execution_flow(self, dm_request, mock_websocket):
        """Test message flow with tool execution."""
        from gateway.processor import MessageProcessor

        processor = MessageProcessor()

        # Mock dependencies
        mock_mm = MagicMock()
        mock_mm.fetch_mem0_context = MagicMock(return_value=([], [], []))
        mock_mm.build_prompt = MagicMock(return_value=[])
        mock_mm.add_to_memory = MagicMock()

        mock_te = MagicMock()
        mock_te.get_all_tools = MagicMock(return_value=[])
        mock_te.execute = AsyncMock(return_value="50\n")

        # Track pipeline calls
        call_count = 0

        async def mock_process(event, tools):
            nonlocal call_count
            call_count += 1

            if event.type == EventType.MESSAGE:
                # First call yields tool
                yield ToolCallEvent(
                    tool_name="execute_python",
                    tool_args={"code": "print(10 * 5)"},
                    call_id="call-1",
                    request_id=event.request_id,
                )
            else:
                # Second call (after tool result) yields response
                yield TextChunkEvent(text="The result is 50.", request_id=event.request_id)
                yield ResponseCompleteEvent(
                    full_text="The result is 50.",
                    tool_count=1,
                    request_id=event.request_id,
                )

        mock_pipeline = MagicMock()
        mock_pipeline.process = mock_process
        mock_pipeline.reset_request = MagicMock()

        # Set up processor
        processor._initialized = True
        processor._memory_manager = mock_mm
        processor._tool_executor = mock_te
        processor._pipeline = mock_pipeline

        # Process request
        mock_server = MagicMock()
        await processor.process(dm_request, mock_websocket, mock_server)

        # Verify tool was executed
        mock_te.execute.assert_called_once()
        call_args = mock_te.execute.call_args
        assert call_args.kwargs["tool_name"] == "execute_python"
        assert call_args.kwargs["arguments"] == {"code": "print(10 * 5)"}

        # Verify messages include tool notifications
        import json

        messages = [json.loads(m) for m in mock_websocket.messages]

        # Find tool messages
        tool_start = next((m for m in messages if m["type"] == "tool_start"), None)
        tool_result = next((m for m in messages if m["type"] == "tool_result"), None)

        assert tool_start is not None
        assert tool_start["tool_name"] == "execute_python"

        assert tool_result is not None
        assert tool_result["tool_name"] == "execute_python"
        assert tool_result["success"] is True

    @pytest.mark.asyncio
    async def test_rate_limit_in_gateway_flow(self, dm_request, mock_websocket):
        """Test rate limiting works in gateway flow."""
        from gateway.processor import MessageProcessor

        processor = MessageProcessor()

        # Mock dependencies
        mock_mm = MagicMock()
        mock_mm.fetch_mem0_context = MagicMock(return_value=([], [], []))
        mock_mm.build_prompt = MagicMock(return_value=[])

        mock_te = MagicMock()
        mock_te.get_all_tools = MagicMock(return_value=[])
        mock_te.execute = AsyncMock(return_value="result")

        # Create pipeline with low rate limit
        from clara_core.cognition import PipelineConfig, RateLimitConfig

        real_pipeline = CognitionPipeline(
            config=PipelineConfig(
                router_config=RateLimitConfig(
                    max_tool_calls_per_request=1,  # Only allow 1 tool call
                    max_tool_calls_per_minute=10,
                ),
            ),
            memory_manager=mock_mm,
        )

        # Mock responder to keep yielding tool calls
        tool_call_count = 0

        async def mock_generate(context, tools, evaluation, request_id):
            nonlocal tool_call_count
            tool_call_count += 1
            yield ToolCallEvent(
                tool_name="execute_python",
                tool_args={"code": f"step {tool_call_count}"},
                call_id=f"call-{tool_call_count}",
                request_id=request_id,
            )

        with patch.object(real_pipeline.responder, "generate", mock_generate):
            processor._initialized = True
            processor._memory_manager = mock_mm
            processor._tool_executor = mock_te
            processor._pipeline = real_pipeline

            # Process request - should hit rate limit after 1 tool
            mock_server = MagicMock()
            await processor.process(dm_request, mock_websocket, mock_server)

        # Verify rate limit error was sent
        import json

        messages = [json.loads(m) for m in mock_websocket.messages]
        error_msg = next((m for m in messages if m["type"] == "error"), None)

        assert error_msg is not None
        assert error_msg["code"] == "rate_limited"
