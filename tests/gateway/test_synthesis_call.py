"""Tests for synthesis call fallback when tools run but content is empty."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mypalclara.core.llm.messages import SystemMessage, UserMessage
from mypalclara.core.tool_guard import LoopAction
from mypalclara.gateway.llm_orchestrator import LLMOrchestrator


def _make_tool_response(*, has_tool_calls: bool, content: str | None = None, tool_calls=None):
    """Create a mock ToolResponse."""
    resp = MagicMock()
    resp.has_tool_calls = has_tool_calls
    resp.content = content
    resp.tool_calls = tool_calls or []
    resp.to_assistant_message.return_value = MagicMock()
    return resp


def _allow_check():
    """Return a loop-guard check result that allows the tool call."""
    result = MagicMock()
    result.action = LoopAction.ALLOW
    result.reason = None
    return result


async def _collect_events(gen) -> list[dict]:
    """Collect all events from an async generator."""
    events = []
    async for event in gen:
        events.append(event)
    return events


def _no_compaction_result(messages):
    """Return a CompactionResult that indicates no compaction was needed."""
    result = MagicMock()
    result.was_compacted = False
    result.messages = messages
    result.tokens_saved = 0
    return result


@pytest.fixture
def orchestrator():
    """Create an initialized LLMOrchestrator with mocked tool executor."""
    orch = LLMOrchestrator()
    orch._tool_executor = MagicMock()
    orch._initialized = True
    # Mock context compactor to avoid tiktoken issues with mock messages
    orch._context_compactor.compact_if_needed = AsyncMock(side_effect=lambda msgs, budget: _no_compaction_result(msgs))
    return orch


class TestSynthesisCall:
    """Tests for synthesis call when tools ran but final content is empty."""

    @pytest.mark.asyncio
    async def test_empty_content_after_tools_triggers_synthesis(self, orchestrator):
        """When tools ran (total_tools_run > 0) and content is empty, a synthesis
        call should be made to produce a text response."""
        # First call: LLM returns tool calls
        tool_call = MagicMock()
        tool_call.name = "search"
        tool_call.arguments = {"query": "test"}
        tool_call.id = "tc_1"
        tool_call.to_result_message.return_value = MagicMock()

        tool_response_with_calls = _make_tool_response(has_tool_calls=True, content=None, tool_calls=[tool_call])

        # Second call: LLM returns empty content (no tool calls)
        tool_response_empty = _make_tool_response(has_tool_calls=False, content="")

        orchestrator._call_llm = AsyncMock(side_effect=[tool_response_with_calls, tool_response_empty])
        orchestrator._tool_executor.execute = AsyncMock(return_value="search result")
        orchestrator._loop_guard.check = MagicMock(return_value=_allow_check())
        orchestrator._loop_guard.record_result = MagicMock()

        # Mock _call_main_llm to return synthesis text
        orchestrator._call_main_llm = AsyncMock(return_value="I searched and found the result.")

        messages = [
            SystemMessage(content="You are Clara."),
            UserMessage(content="Search for something"),
        ]

        events = await _collect_events(
            orchestrator.generate_with_tools(
                messages=messages,
                tools=[{"name": "search"}],
                user_id="test-user",
                request_id="req-1",
                tier=None,
            )
        )

        # Verify synthesis call was made
        orchestrator._call_main_llm.assert_called_once()

        # Verify we got a complete event with the synthesis text
        complete_events = [e for e in events if e["type"] == "complete"]
        assert len(complete_events) == 1
        assert complete_events[0]["text"] == "I searched and found the result."
        assert complete_events[0]["tool_count"] == 1

    @pytest.mark.asyncio
    async def test_nonempty_content_after_tools_skips_synthesis(self, orchestrator):
        """When tools ran but the LLM returned non-empty content, no synthesis
        call should be made."""
        # First call: LLM returns tool calls
        tool_call = MagicMock()
        tool_call.name = "search"
        tool_call.arguments = {"query": "test"}
        tool_call.id = "tc_1"
        tool_call.to_result_message.return_value = MagicMock()

        tool_response_with_calls = _make_tool_response(has_tool_calls=True, content=None, tool_calls=[tool_call])

        # Second call: LLM returns content (no tool calls)
        tool_response_with_content = _make_tool_response(
            has_tool_calls=False, content="Here is what I found from the search."
        )

        orchestrator._call_llm = AsyncMock(side_effect=[tool_response_with_calls, tool_response_with_content])
        orchestrator._tool_executor.execute = AsyncMock(return_value="search result")
        orchestrator._loop_guard.check = MagicMock(return_value=_allow_check())
        orchestrator._loop_guard.record_result = MagicMock()

        # _call_main_llm should NOT be called
        orchestrator._call_main_llm = AsyncMock(return_value="should not appear")

        messages = [
            SystemMessage(content="You are Clara."),
            UserMessage(content="Search for something"),
        ]

        events = await _collect_events(
            orchestrator.generate_with_tools(
                messages=messages,
                tools=[{"name": "search"}],
                user_id="test-user",
                request_id="req-1",
                tier=None,
            )
        )

        # Verify synthesis call was NOT made
        orchestrator._call_main_llm.assert_not_called()

        # Verify we got a complete event with the original content
        complete_events = [e for e in events if e["type"] == "complete"]
        assert len(complete_events) == 1
        assert complete_events[0]["text"] == "Here is what I found from the search."

    @pytest.mark.asyncio
    @patch("mypalclara.gateway.llm_orchestrator.AUTO_CONTINUE_ENABLED", False)
    async def test_empty_content_no_tools_run_skips_synthesis(self, orchestrator):
        """When no tools ran (total_tools_run == 0) and content is empty,
        no synthesis call should be made (nothing to synthesize).
        With auto-continue disabled, iteration 0 uses streaming path."""
        # LLM returns empty content, no tool calls on first iteration
        tool_response_empty = _make_tool_response(has_tool_calls=False, content="")

        orchestrator._call_llm = AsyncMock(return_value=tool_response_empty)

        # Mock streaming path (iteration 0 without auto-continue uses streaming)
        async def empty_stream():
            yield ""

        orchestrator._call_main_llm_streaming = MagicMock(return_value=empty_stream())

        # _call_main_llm should NOT be called for synthesis
        orchestrator._call_main_llm = AsyncMock(return_value="should not appear")

        messages = [
            SystemMessage(content="You are Clara."),
            UserMessage(content="Hello"),
        ]

        events = await _collect_events(
            orchestrator.generate_with_tools(
                messages=messages,
                tools=[{"name": "search"}],
                user_id="test-user",
                request_id="req-1",
                tier=None,
            )
        )

        # No synthesis call since no tools ran
        orchestrator._call_main_llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_none_content_after_tools_triggers_synthesis(self, orchestrator):
        """When content is None (not just empty string) after tools ran,
        synthesis should still trigger."""
        tool_call = MagicMock()
        tool_call.name = "fetch"
        tool_call.arguments = {"url": "http://example.com"}
        tool_call.id = "tc_1"
        tool_call.to_result_message.return_value = MagicMock()

        tool_response_with_calls = _make_tool_response(has_tool_calls=True, content=None, tool_calls=[tool_call])
        # content=None => `content = tool_response.content or ""` => ""
        tool_response_none = _make_tool_response(has_tool_calls=False, content=None)

        orchestrator._call_llm = AsyncMock(side_effect=[tool_response_with_calls, tool_response_none])
        orchestrator._tool_executor.execute = AsyncMock(return_value="page content")
        orchestrator._loop_guard.check = MagicMock(return_value=_allow_check())
        orchestrator._loop_guard.record_result = MagicMock()

        orchestrator._call_main_llm = AsyncMock(return_value="I fetched the page for you.")

        messages = [UserMessage(content="Fetch example.com")]

        events = await _collect_events(
            orchestrator.generate_with_tools(
                messages=messages,
                tools=[{"name": "fetch"}],
                user_id="test-user",
                request_id="req-1",
                tier=None,
            )
        )

        orchestrator._call_main_llm.assert_called_once()
        complete_events = [e for e in events if e["type"] == "complete"]
        assert complete_events[0]["text"] == "I fetched the page for you."
