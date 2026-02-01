"""Tests for the CognitionPipeline orchestrator."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clara_core.cognition import (
    CognitionEvent,
    CognitionPipeline,
    ContextBundle,
    EvaluationResult,
    EventMetadata,
    EventType,
    PipelineConfig,
    RateLimitConfig,
    RejectedEvent,
    ResponseCompleteEvent,
    TextChunkEvent,
    ToolCallEvent,
)
from clara_core.cognition.evaluator import EvaluatorConfig
from clara_core.cognition.reflect import ReflectorConfig


@pytest.fixture
def mock_memory_manager():
    """Create a mock MemoryManager."""
    mm = MagicMock()
    mm.get_or_create_session.return_value = MagicMock(
        id=1,
        project_id=None,
        session_summary=None,
    )
    mm.get_recent_messages.return_value = []
    mm.get_message_count.return_value = 0
    mm.fetch_mem0_context.return_value = ([], [], [])
    mm.fetch_emotional_context.return_value = []
    mm.build_prompt.return_value = [
        {"role": "system", "content": "You are Clara."},
        {"role": "user", "content": "Hello"},
    ]
    mm.add_to_mem0.return_value = None
    return mm


@pytest.fixture
def pipeline_config():
    """Create a pipeline config with disabled LLM evaluation."""
    return PipelineConfig(
        evaluator_config=EvaluatorConfig(use_llm_evaluation=False),
        reflector_config=ReflectorConfig(store_to_memory=False, track_patterns=False),
    )


@pytest.fixture
def pipeline(pipeline_config, mock_memory_manager):
    """Create a pipeline with mocked dependencies."""
    return CognitionPipeline(
        config=pipeline_config,
        memory_manager=mock_memory_manager,
    )


def make_message_event(content: str = "Hello", request_id: str = "test-req") -> CognitionEvent:
    """Create a MESSAGE event for testing."""
    return CognitionEvent(
        type=EventType.MESSAGE,
        payload={
            "content": content,
            "is_dm": True,  # DMs always trigger response
        },
        metadata=EventMetadata(
            request_id=request_id,
            user_id="user-123",
            channel_id="channel-456",
        ),
    )


def make_tool_result_event(
    result: str = "tool output",
    tool_name: str = "test_tool",
    request_id: str = "test-req",
) -> CognitionEvent:
    """Create a TOOL_RESULT event for testing."""
    return CognitionEvent(
        type=EventType.TOOL_RESULT,
        payload={
            "result": result,
            "tool_name": tool_name,
        },
        metadata=EventMetadata(
            request_id=request_id,
            user_id="user-123",
            channel_id="channel-456",
        ),
    )


class TestPipelineBasics:
    """Basic pipeline functionality tests."""

    @pytest.mark.asyncio
    async def test_process_message_yields_text_and_complete(self, pipeline):
        """Processing a message should yield text chunks and completion."""
        event = make_message_event("Hello Clara")

        # Mock the responder to return simple response
        async def mock_generate(*args, **kwargs):
            yield TextChunkEvent(text="Hello!", is_final=True, request_id="test-req")
            yield ResponseCompleteEvent(
                full_text="Hello!",
                tool_count=0,
                request_id="test-req",
            )

        with patch.object(pipeline.responder, "generate", mock_generate):
            events = []
            async for e in pipeline.process(event):
                events.append(e)

        # Should have text chunk and completion
        assert len(events) == 2
        assert isinstance(events[0], TextChunkEvent)
        assert events[0].text == "Hello!"
        assert isinstance(events[1], ResponseCompleteEvent)
        assert events[1].full_text == "Hello!"

    @pytest.mark.asyncio
    async def test_process_yields_tool_call_event(self, pipeline):
        """Tool calls should be yielded as ToolCallEvent (not executed)."""
        event = make_message_event("Run a command")
        tools = [{"name": "execute_command", "description": "Run a command"}]

        # Mock responder to return a tool call
        async def mock_generate(*args, **kwargs):
            yield ToolCallEvent(
                tool_name="execute_command",
                tool_args={"command": "ls"},
                call_id="call-1",
                request_id="test-req",
            )
            yield ResponseCompleteEvent(
                full_text="",
                tool_count=1,
                request_id="test-req",
            )

        with patch.object(pipeline.responder, "generate", mock_generate):
            events = []
            async for e in pipeline.process(event, tools=tools):
                events.append(e)

        # Should have tool call and completion
        assert len(events) == 2
        assert isinstance(events[0], ToolCallEvent)
        assert events[0].tool_name == "execute_command"
        assert events[0].tool_args == {"command": "ls"}
        assert isinstance(events[1], ResponseCompleteEvent)


class TestToolResultReentry:
    """Tests for tool result re-entry pattern."""

    @pytest.mark.asyncio
    async def test_tool_result_processed_normally(self, pipeline):
        """TOOL_RESULT events should be processed through the pipeline."""
        event = make_tool_result_event("command output", "execute_command")

        async def mock_generate(*args, **kwargs):
            yield TextChunkEvent(
                text="The command returned: command output",
                is_final=True,
                request_id="test-req",
            )
            yield ResponseCompleteEvent(
                full_text="The command returned: command output",
                tool_count=0,
                request_id="test-req",
            )

        with patch.object(pipeline.responder, "generate", mock_generate):
            events = []
            async for e in pipeline.process(event):
                events.append(e)

        assert len(events) == 2
        assert isinstance(events[0], TextChunkEvent)
        assert "command output" in events[0].text

    @pytest.mark.asyncio
    async def test_full_tool_call_continuation_flow(self, pipeline):
        """Test complete flow: message -> tool call -> tool result -> response."""
        tools = [{"name": "calculator", "description": "Do math"}]

        # Step 1: Initial message triggers tool call
        message_event = make_message_event("What is 2+2?")

        async def mock_generate_with_tool(*args, **kwargs):
            yield ToolCallEvent(
                tool_name="calculator",
                tool_args={"expression": "2+2"},
                call_id="call-1",
                request_id="test-req",
            )
            yield ResponseCompleteEvent(
                full_text="",
                tool_count=1,
                request_id="test-req",
            )

        with patch.object(pipeline.responder, "generate", mock_generate_with_tool):
            initial_events = []
            async for e in pipeline.process(message_event, tools=tools):
                initial_events.append(e)

        # Should get tool call
        assert isinstance(initial_events[0], ToolCallEvent)
        assert initial_events[0].tool_name == "calculator"

        # Step 2: Re-enter with tool result
        tool_result_event = make_tool_result_event("4", "calculator")

        async def mock_generate_final(*args, **kwargs):
            yield TextChunkEvent(
                text="The answer is 4.",
                is_final=True,
                request_id="test-req",
            )
            yield ResponseCompleteEvent(
                full_text="The answer is 4.",
                tool_count=0,
                request_id="test-req",
            )

        with patch.object(pipeline.responder, "generate", mock_generate_final):
            final_events = []
            async for e in pipeline.process(tool_result_event, tools=tools):
                final_events.append(e)

        assert isinstance(final_events[0], TextChunkEvent)
        assert "4" in final_events[0].text


class TestRateLimitRejection:
    """Tests for rate limit rejection at pipeline level."""

    @pytest.mark.asyncio
    async def test_rate_limit_rejects_excess_tool_results(self, mock_memory_manager):
        """Too many tool results should be rate-limited."""
        config = PipelineConfig(
            router_config=RateLimitConfig(
                max_tool_calls_per_request=2,
                max_tool_calls_per_minute=5,
            ),
            evaluator_config=EvaluatorConfig(use_llm_evaluation=False),
            reflector_config=ReflectorConfig(store_to_memory=False),
        )
        pipeline = CognitionPipeline(config=config, memory_manager=mock_memory_manager)

        async def mock_generate(*args, **kwargs):
            yield ResponseCompleteEvent(
                full_text="OK",
                tool_count=0,
                request_id="test-req",
            )

        request_id = "limited-request"

        with patch.object(pipeline.responder, "generate", mock_generate):
            # First 2 tool results should pass
            for i in range(2):
                event = make_tool_result_event(f"result-{i}", request_id=request_id)
                events = []
                async for e in pipeline.process(event):
                    events.append(e)
                assert not any(isinstance(e, RejectedEvent) for e in events), f"Call {i+1} should pass"

            # 3rd should be rejected
            event = make_tool_result_event("result-3", request_id=request_id)
            events = []
            async for e in pipeline.process(event):
                events.append(e)

            assert len(events) == 1
            assert isinstance(events[0], RejectedEvent)
            assert "limit" in events[0].reason.lower()
            assert events[0].rate_limit_info["type"] == "per_request"

    @pytest.mark.asyncio
    async def test_per_minute_rate_limit(self, mock_memory_manager):
        """Per-minute rate limit should reject across different requests."""
        config = PipelineConfig(
            router_config=RateLimitConfig(
                max_tool_calls_per_request=10,  # High per-request
                max_tool_calls_per_minute=3,  # Low per-minute
            ),
            evaluator_config=EvaluatorConfig(use_llm_evaluation=False),
            reflector_config=ReflectorConfig(store_to_memory=False),
        )
        pipeline = CognitionPipeline(config=config, memory_manager=mock_memory_manager)

        async def mock_generate(*args, **kwargs):
            yield ResponseCompleteEvent(
                full_text="OK",
                tool_count=0,
                request_id="test",
            )

        with patch.object(pipeline.responder, "generate", mock_generate):
            # Use different request IDs to avoid per-request limit
            for i in range(3):
                event = make_tool_result_event(f"result-{i}", request_id=f"req-{i}")
                events = []
                async for e in pipeline.process(event):
                    events.append(e)
                assert not any(isinstance(e, RejectedEvent) for e in events)

            # 4th should hit per-minute limit
            event = make_tool_result_event("result-4", request_id="req-4")
            events = []
            async for e in pipeline.process(event):
                events.append(e)

            assert len(events) == 1
            assert isinstance(events[0], RejectedEvent)
            assert events[0].rate_limit_info["type"] == "per_minute"


class TestReflectAsyncBehavior:
    """Tests for async reflection (fire-and-forget) behavior."""

    @pytest.mark.asyncio
    async def test_reflect_does_not_block_response(self, mock_memory_manager):
        """Reflection should not block the response stream."""
        config = PipelineConfig(
            evaluator_config=EvaluatorConfig(use_llm_evaluation=False),
            reflector_config=ReflectorConfig(
                store_to_memory=True,  # Enable memory storage
                track_patterns=True,
            ),
        )
        pipeline = CognitionPipeline(config=config, memory_manager=mock_memory_manager)

        # Track when memory storage is called
        storage_called = asyncio.Event()
        original_add = mock_memory_manager.add_to_mem0

        def slow_add_to_mem0(*args, **kwargs):
            # Simulate slow operation
            storage_called.set()
            original_add(*args, **kwargs)

        mock_memory_manager.add_to_mem0 = slow_add_to_mem0

        event = make_message_event("Hello")

        async def mock_generate(*args, **kwargs):
            yield TextChunkEvent(text="Hi!", is_final=True, request_id="test-req")
            yield ResponseCompleteEvent(
                full_text="Hi!",
                tool_count=0,
                request_id="test-req",
            )

        with patch.object(pipeline.responder, "generate", mock_generate):
            events = []
            async for e in pipeline.process(event):
                events.append(e)

        # Response should be complete immediately
        assert len(events) == 2
        assert isinstance(events[1], ResponseCompleteEvent)

        # Give the background task a moment to run
        await asyncio.sleep(0.1)

        # Verify reflection was scheduled (fire-and-forget)
        # Note: It may or may not have completed by now, but it was scheduled

    @pytest.mark.asyncio
    async def test_reflect_failure_does_not_affect_response(self, mock_memory_manager):
        """Reflection errors should not affect response delivery."""
        config = PipelineConfig(
            evaluator_config=EvaluatorConfig(use_llm_evaluation=False),
            reflector_config=ReflectorConfig(store_to_memory=True),
        )
        pipeline = CognitionPipeline(config=config, memory_manager=mock_memory_manager)

        # Make memory storage fail
        mock_memory_manager.add_to_mem0.side_effect = Exception("Memory storage failed")

        event = make_message_event("Hello")

        async def mock_generate(*args, **kwargs):
            yield TextChunkEvent(text="Hi!", is_final=True, request_id="test-req")
            yield ResponseCompleteEvent(
                full_text="Hi!",
                tool_count=0,
                request_id="test-req",
            )

        with patch.object(pipeline.responder, "generate", mock_generate):
            # Should not raise
            events = []
            async for e in pipeline.process(event):
                events.append(e)

        # Response should still be delivered
        assert len(events) == 2
        assert isinstance(events[1], ResponseCompleteEvent)


class TestPipelineUtilities:
    """Tests for pipeline utility methods."""

    @pytest.mark.asyncio
    async def test_reset_request_clears_rate_limit(self, mock_memory_manager):
        """reset_request should clear rate limit counters."""
        config = PipelineConfig(
            router_config=RateLimitConfig(max_tool_calls_per_request=1),
            evaluator_config=EvaluatorConfig(use_llm_evaluation=False),
            reflector_config=ReflectorConfig(store_to_memory=False),
        )
        pipeline = CognitionPipeline(config=config, memory_manager=mock_memory_manager)

        async def mock_generate(*args, **kwargs):
            yield ResponseCompleteEvent(full_text="OK", tool_count=0, request_id="test")

        with patch.object(pipeline.responder, "generate", mock_generate):
            # First call uses the limit
            event1 = make_tool_result_event("r1", request_id="req-1")
            events1 = []
            async for e in pipeline.process(event1):
                events1.append(e)

            # Second should be rejected
            event2 = make_tool_result_event("r2", request_id="req-1")
            events2 = []
            async for e in pipeline.process(event2):
                events2.append(e)
            assert isinstance(events2[0], RejectedEvent)

            # Reset the request
            pipeline.reset_request("req-1")

            # Now should work again
            event3 = make_tool_result_event("r3", request_id="req-1")
            events3 = []
            async for e in pipeline.process(event3):
                events3.append(e)
            assert isinstance(events3[0], ResponseCompleteEvent)

    def test_get_stats_returns_router_info(self, pipeline):
        """get_stats should include router statistics."""
        stats = pipeline.get_stats()

        assert "router" in stats
        assert "active_requests" in stats["router"]
        assert "tool_calls_in_window" in stats["router"]

    def test_reset_all_clears_state(self, pipeline):
        """reset_all should clear all pipeline state."""
        # Set some internal state
        pipeline._current_context = ContextBundle()
        pipeline._current_event = make_message_event()

        pipeline.reset_all()

        assert pipeline._current_context is None
        assert pipeline._current_event is None


class TestEvaluationRejection:
    """Tests for evaluation-based rejection."""

    @pytest.mark.asyncio
    async def test_evaluation_no_response_yields_rejected(self, mock_memory_manager):
        """When evaluation says no response needed, yield RejectedEvent."""
        config = PipelineConfig(
            evaluator_config=EvaluatorConfig(
                bot_user_ids={"bot-123"},  # Bot's own messages
                use_llm_evaluation=False,
            ),
            reflector_config=ReflectorConfig(store_to_memory=False),
        )
        pipeline = CognitionPipeline(config=config, memory_manager=mock_memory_manager)

        # Create event that looks like bot's own message
        event = CognitionEvent(
            type=EventType.MESSAGE,
            payload={"content": "Hello"},
            metadata=EventMetadata(
                request_id="test",
                user_id="bot-123",  # Bot's own user ID
                channel_id="channel",
            ),
        )

        events = []
        async for e in pipeline.process(event):
            events.append(e)

        assert len(events) == 1
        assert isinstance(events[0], RejectedEvent)
        assert "own message" in events[0].reason.lower()
