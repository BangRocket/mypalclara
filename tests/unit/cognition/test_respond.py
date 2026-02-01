"""Tests for the cognition Responder module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clara_core.cognition.respond import (
    Responder,
    ResponderConfig,
    create_responder,
)
from clara_core.cognition.types import (
    ContextBundle,
    EvaluationResult,
    ResponseCompleteEvent,
    TextChunkEvent,
    ToolCallEvent,
)


def make_context(
    user_id: str = "user-123",
    messages: list | None = None,
) -> ContextBundle:
    """Helper to create a ContextBundle."""
    return ContextBundle(
        user_id=user_id,
        channel_id="channel-456",
        messages=messages or [
            {"role": "system", "content": "You are Clara..."},
            {"role": "user", "content": "Hello, what's 2+2?"},
        ],
        memories=["User likes math"],
    )


def make_evaluation(
    tier: str = "mid",
    complexity: str = "medium",
) -> EvaluationResult:
    """Helper to create an EvaluationResult."""
    return EvaluationResult(
        should_respond=True,
        complexity=complexity,
        suggested_tier=tier,
    )


@pytest.fixture
def mock_llm_text_only():
    """Mock LLM that returns text only (no tools)."""

    async def _llm(messages, tier):
        return "2+2 equals 4. That's basic arithmetic!"

    return _llm


@pytest.fixture
def mock_llm_with_tools():
    """Mock LLM that returns tool calls."""

    async def _llm(messages, tools, tier):
        return {
            "content": "",
            "tool_calls": [
                {
                    "id": "call-abc123",
                    "type": "function",
                    "function": {
                        "name": "execute_python",
                        "arguments": '{"code": "print(2+2)"}',
                    },
                },
            ],
        }

    return _llm


@pytest.fixture
def mock_llm_text_and_tools():
    """Mock LLM that returns both text and tool calls."""

    async def _llm(messages, tools, tier):
        return {
            "content": "Let me calculate that for you.",
            "tool_calls": [
                {
                    "id": "call-def456",
                    "type": "function",
                    "function": {
                        "name": "execute_python",
                        "arguments": '{"code": "result = 2 + 2\\nprint(result)"}',
                    },
                },
            ],
        }

    return _llm


class TestResponderBasic:
    """Basic tests for Responder initialization and configuration."""

    def test_default_config(self):
        """Responder should use default config if none provided."""
        responder = Responder()
        assert responder.config.default_tier == "mid"
        assert responder.config.use_streaming is True
        assert responder.config.include_tool_instruction is True

    def test_custom_config(self):
        """Responder should accept custom configuration."""
        config = ResponderConfig(
            default_tier="high",
            use_streaming=False,
        )
        responder = Responder(config=config)
        assert responder.config.default_tier == "high"
        assert responder.config.use_streaming is False

    def test_factory_function(self):
        """create_responder should create configured instance."""
        responder = create_responder(
            default_tier="low",
            use_streaming=False,
        )
        assert responder.config.default_tier == "low"
        assert responder.config.use_streaming is False


class TestGenerateTextOnly:
    """Tests for generating text-only responses."""

    @pytest.mark.asyncio
    async def test_yields_text_chunks(self, mock_llm_text_only):
        """generate should yield TextChunkEvent for text responses."""
        responder = Responder(llm_fn=mock_llm_text_only)
        context = make_context()

        events = []
        async for event in responder.generate(context, request_id="req-123"):
            events.append(event)

        # Should have at least one TextChunkEvent
        text_events = [e for e in events if isinstance(e, TextChunkEvent)]
        assert len(text_events) >= 1

        # Should end with ResponseCompleteEvent
        assert isinstance(events[-1], ResponseCompleteEvent)

    @pytest.mark.asyncio
    async def test_final_chunk_marked(self, mock_llm_text_only):
        """The last text chunk should have is_final=True."""
        responder = Responder(llm_fn=mock_llm_text_only)
        context = make_context()

        events = []
        async for event in responder.generate(context):
            events.append(event)

        # Find the last TextChunkEvent
        text_events = [e for e in events if isinstance(e, TextChunkEvent)]
        last_text = text_events[-1]
        assert last_text.is_final is True

    @pytest.mark.asyncio
    async def test_complete_event_has_full_text(self, mock_llm_text_only):
        """ResponseCompleteEvent should contain full text."""
        responder = Responder(llm_fn=mock_llm_text_only)
        context = make_context()

        events = []
        async for event in responder.generate(context):
            events.append(event)

        complete_event = events[-1]
        assert isinstance(complete_event, ResponseCompleteEvent)
        assert "2+2 equals 4" in complete_event.full_text
        assert complete_event.tool_count == 0


class TestGenerateWithTools:
    """Tests for generating responses with tool calls."""

    @pytest.mark.asyncio
    async def test_yields_tool_call_events(self, mock_llm_with_tools):
        """generate should yield ToolCallEvent for tool calls."""
        responder = Responder(llm_with_tools_fn=mock_llm_with_tools)
        context = make_context()
        tools = [{"type": "function", "function": {"name": "execute_python"}}]

        events = []
        async for event in responder.generate(context, tools=tools, request_id="req-456"):
            events.append(event)

        # Should have ToolCallEvent
        tool_events = [e for e in events if isinstance(e, ToolCallEvent)]
        assert len(tool_events) == 1

        # Verify tool call details
        tool_event = tool_events[0]
        assert tool_event.tool_name == "execute_python"
        assert "code" in tool_event.tool_args
        assert tool_event.call_id == "call-abc123"

    @pytest.mark.asyncio
    async def test_tool_calls_not_executed(self, mock_llm_with_tools):
        """Tool calls should NOT be executed by the Responder."""
        responder = Responder(llm_with_tools_fn=mock_llm_with_tools)
        context = make_context()
        tools = [{"type": "function", "function": {"name": "execute_python"}}]

        events = []
        async for event in responder.generate(context, tools=tools):
            events.append(event)

        # Verify tool call event is NOT marked as executed
        tool_events = [e for e in events if isinstance(e, ToolCallEvent)]
        assert len(tool_events) == 1
        assert tool_events[0].executed is False
        assert tool_events[0].result is None
        assert tool_events[0].error is None

    @pytest.mark.asyncio
    async def test_tool_count_in_complete_event(self, mock_llm_with_tools):
        """ResponseCompleteEvent should count tool calls."""
        responder = Responder(llm_with_tools_fn=mock_llm_with_tools)
        context = make_context()
        tools = [{"type": "function", "function": {"name": "execute_python"}}]

        events = []
        async for event in responder.generate(context, tools=tools):
            events.append(event)

        complete_event = events[-1]
        assert isinstance(complete_event, ResponseCompleteEvent)
        assert complete_event.tool_count == 1

    @pytest.mark.asyncio
    async def test_text_and_tools_combined(self, mock_llm_text_and_tools):
        """Responses with both text and tools should yield both event types."""
        responder = Responder(llm_with_tools_fn=mock_llm_text_and_tools)
        context = make_context()
        tools = [{"type": "function", "function": {"name": "execute_python"}}]

        events = []
        async for event in responder.generate(context, tools=tools):
            events.append(event)

        # Should have both types
        tool_events = [e for e in events if isinstance(e, ToolCallEvent)]
        text_events = [e for e in events if isinstance(e, TextChunkEvent)]

        assert len(tool_events) == 1
        assert len(text_events) >= 1  # At least one text chunk


class TestTierSelection:
    """Tests for model tier selection."""

    @pytest.mark.asyncio
    async def test_uses_evaluation_tier(self, mock_llm_text_only):
        """generate should use tier from EvaluationResult."""
        responder = Responder(llm_fn=mock_llm_text_only)
        context = make_context()
        evaluation = make_evaluation(tier="high")

        events = []
        async for event in responder.generate(context, evaluation=evaluation):
            events.append(event)

        complete_event = events[-1]
        assert complete_event.metadata["tier"] == "high"

    @pytest.mark.asyncio
    async def test_uses_default_tier_when_no_evaluation(self, mock_llm_text_only):
        """generate should use default tier when no evaluation provided."""
        config = ResponderConfig(default_tier="low")
        responder = Responder(config=config, llm_fn=mock_llm_text_only)
        context = make_context()

        events = []
        async for event in responder.generate(context):
            events.append(event)

        complete_event = events[-1]
        assert complete_event.metadata["tier"] == "low"


class TestToolArgumentParsing:
    """Tests for parsing tool call arguments."""

    @pytest.mark.asyncio
    async def test_parses_json_string_arguments(self):
        """Tool arguments as JSON strings should be parsed."""

        async def llm_with_string_args(messages, tools, tier):
            return {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-1",
                        "function": {
                            "name": "test_tool",
                            "arguments": '{"key": "value", "num": 42}',
                        },
                    },
                ],
            }

        responder = Responder(llm_with_tools_fn=llm_with_string_args)
        context = make_context()
        tools = [{"type": "function", "function": {"name": "test_tool"}}]

        events = []
        async for event in responder.generate(context, tools=tools):
            events.append(event)

        tool_events = [e for e in events if isinstance(e, ToolCallEvent)]
        assert tool_events[0].tool_args == {"key": "value", "num": 42}

    @pytest.mark.asyncio
    async def test_handles_invalid_json_arguments(self):
        """Invalid JSON arguments should result in empty dict."""

        async def llm_with_bad_args(messages, tools, tier):
            return {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-1",
                        "function": {
                            "name": "test_tool",
                            "arguments": "not valid json",
                        },
                    },
                ],
            }

        responder = Responder(llm_with_tools_fn=llm_with_bad_args)
        context = make_context()
        tools = [{"type": "function", "function": {"name": "test_tool"}}]

        events = []
        async for event in responder.generate(context, tools=tools):
            events.append(event)

        # Should still yield the event with empty args
        tool_events = [e for e in events if isinstance(e, ToolCallEvent)]
        assert len(tool_events) == 1
        assert tool_events[0].tool_args == {}


class TestToolInstruction:
    """Tests for tool instruction message."""

    def test_tool_instruction_content(self):
        """Tool instruction should include key guidelines."""
        responder = Responder()
        instruction = responder._build_tool_instruction()

        assert instruction["role"] == "system"
        assert "create_file_attachment" in instruction["content"]
        assert "execute_python" in instruction["content"]
        assert "github_" in instruction["content"]


class TestTextStreaming:
    """Tests for simulated text streaming."""

    @pytest.mark.asyncio
    async def test_streams_in_chunks(self, mock_llm_text_only):
        """Text should be streamed in chunks."""
        config = ResponderConfig(chunk_size=10)  # Small chunks
        responder = Responder(config=config, llm_fn=mock_llm_text_only)
        context = make_context()

        events = []
        async for event in responder.generate(context):
            events.append(event)

        text_events = [e for e in events if isinstance(e, TextChunkEvent)]

        # With chunk_size=10, should have multiple chunks
        assert len(text_events) > 1

    @pytest.mark.asyncio
    async def test_empty_response_no_chunks(self):
        """Empty responses should not yield any text chunks."""

        async def empty_llm(messages, tier):
            return ""

        responder = Responder(llm_fn=empty_llm)
        context = make_context()

        events = []
        async for event in responder.generate(context):
            events.append(event)

        text_events = [e for e in events if isinstance(e, TextChunkEvent)]
        assert len(text_events) == 0

        # Should still have complete event
        assert isinstance(events[-1], ResponseCompleteEvent)
        assert events[-1].full_text == ""


class TestRequestIdTracking:
    """Tests for request ID tracking in events."""

    @pytest.mark.asyncio
    async def test_request_id_in_text_events(self, mock_llm_text_only):
        """TextChunkEvents should include request_id."""
        responder = Responder(llm_fn=mock_llm_text_only)
        context = make_context()

        events = []
        async for event in responder.generate(context, request_id="req-xyz"):
            events.append(event)

        text_events = [e for e in events if isinstance(e, TextChunkEvent)]
        assert all(e.request_id == "req-xyz" for e in text_events)

    @pytest.mark.asyncio
    async def test_request_id_in_tool_events(self, mock_llm_with_tools):
        """ToolCallEvents should include request_id."""
        responder = Responder(llm_with_tools_fn=mock_llm_with_tools)
        context = make_context()
        tools = [{"type": "function", "function": {"name": "execute_python"}}]

        events = []
        async for event in responder.generate(context, tools=tools, request_id="req-abc"):
            events.append(event)

        tool_events = [e for e in events if isinstance(e, ToolCallEvent)]
        assert all(e.request_id == "req-abc" for e in tool_events)

    @pytest.mark.asyncio
    async def test_request_id_in_complete_event(self, mock_llm_text_only):
        """ResponseCompleteEvent should include request_id."""
        responder = Responder(llm_fn=mock_llm_text_only)
        context = make_context()

        events = []
        async for event in responder.generate(context, request_id="req-final"):
            events.append(event)

        complete_event = events[-1]
        assert complete_event.request_id == "req-final"
