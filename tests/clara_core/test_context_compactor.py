"""Tests for progressive context compaction."""

from unittest.mock import AsyncMock, patch

import pytest

from mypalclara.core.context_compactor import ContextCompactor
from mypalclara.core.llm.messages import AssistantMessage, SystemMessage, UserMessage


def _make_messages(count: int, chars_each: int = 500) -> list:
    msgs = [SystemMessage(content="You are Clara.")]
    for i in range(count):
        if i % 2 == 0:
            msgs.append(UserMessage(content=f"User message {i}: " + "x" * chars_each))
        else:
            msgs.append(AssistantMessage(content=f"Assistant message {i}: " + "y" * chars_each))
    msgs.append(UserMessage(content="Current message"))
    return msgs


class TestCompactionDecision:
    @pytest.mark.asyncio
    async def test_no_compaction_under_budget(self):
        compactor = ContextCompactor(budget_ratio=0.6)
        messages = _make_messages(5, chars_each=100)
        result = await compactor.compact_if_needed(messages, budget_tokens=100_000)
        assert not result.was_compacted
        assert result.messages == messages

    @pytest.mark.asyncio
    async def test_compaction_over_budget(self):
        compactor = ContextCompactor(budget_ratio=0.6)
        messages = _make_messages(50, chars_each=2000)
        with patch.object(compactor, "_summarize_chunk", new_callable=AsyncMock) as mock_sum:
            mock_sum.return_value = "Summary of conversation chunk."
            result = await compactor.compact_if_needed(messages, budget_tokens=5_000)
        assert result.was_compacted
        assert len(result.messages) < len(messages)
        assert result.tokens_saved > 0


class TestCompactionPreservation:
    @pytest.mark.asyncio
    async def test_system_message_preserved(self):
        compactor = ContextCompactor(budget_ratio=0.6)
        messages = _make_messages(50, chars_each=2000)
        with patch.object(compactor, "_summarize_chunk", new_callable=AsyncMock) as mock_sum:
            mock_sum.return_value = "Summary."
            result = await compactor.compact_if_needed(messages, budget_tokens=5_000)
        assert isinstance(result.messages[0], SystemMessage)
        assert "Clara" in result.messages[0].content

    @pytest.mark.asyncio
    async def test_current_message_preserved(self):
        compactor = ContextCompactor(budget_ratio=0.6)
        messages = _make_messages(50, chars_each=2000)
        with patch.object(compactor, "_summarize_chunk", new_callable=AsyncMock) as mock_sum:
            mock_sum.return_value = "Summary."
            result = await compactor.compact_if_needed(messages, budget_tokens=5_000)
        assert "Current message" in result.messages[-1].content

    @pytest.mark.asyncio
    async def test_summary_message_present(self):
        compactor = ContextCompactor(budget_ratio=0.6)
        messages = _make_messages(50, chars_each=2000)
        with patch.object(compactor, "_summarize_chunk", new_callable=AsyncMock) as mock_sum:
            mock_sum.return_value = "Important summary."
            result = await compactor.compact_if_needed(messages, budget_tokens=5_000)
        summaries = [m for m in result.messages if isinstance(m, SystemMessage) and "Conversation Summary" in m.content]
        assert len(summaries) == 1


class TestFallback:
    @pytest.mark.asyncio
    async def test_fallback_on_summarization_error(self):
        compactor = ContextCompactor(budget_ratio=0.6)
        messages = _make_messages(50, chars_each=2000)
        with patch.object(compactor, "_summarize_chunk", new_callable=AsyncMock) as mock_sum:
            mock_sum.side_effect = Exception("LLM error")
            result = await compactor.compact_if_needed(messages, budget_tokens=5_000)
        assert result.was_compacted
        assert len(result.messages) < len(messages)


class TestSecurity:
    @pytest.mark.asyncio
    async def test_untrusted_content_stripped(self):
        compactor = ContextCompactor(budget_ratio=0.6)
        messages = [
            SystemMessage(content="You are Clara."),
            UserMessage(content="Do something"),
            AssistantMessage(content="<untrusted_tool_result>sensitive data</untrusted_tool_result>"),
        ] + [UserMessage(content="x" * 2000) for _ in range(20)]
        messages.append(UserMessage(content="Current"))

        summaries_seen = []

        async def capture_summarize(chunk):
            text = " ".join(getattr(m, "content", "") for m in chunk)
            summaries_seen.append(text)
            return "Summary."

        with patch.object(compactor, "_summarize_chunk", side_effect=capture_summarize):
            await compactor.compact_if_needed(messages, budget_tokens=5_000)

        # The sensitive data should NOT appear in what was passed to summarize
        all_text = " ".join(summaries_seen)
        assert "sensitive data" not in all_text
