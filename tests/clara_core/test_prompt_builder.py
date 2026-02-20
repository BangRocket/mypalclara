"""Tests for PromptBuilder: thread summary exclusion, channel context, token trimming."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from mypalclara.core.llm.messages import AssistantMessage, SystemMessage, UserMessage


def _make_prompt_builder():
    """Create a PromptBuilder with mocked persona."""
    from mypalclara.core.prompt_builder import PromptBuilder

    return PromptBuilder(agent_id="test-agent")


def _make_db_message(role: str, content: str, user_id: str = "user-1", created_at=None):
    """Create a mock DB message with the fields PromptBuilder accesses."""
    return SimpleNamespace(role=role, content=content, user_id=user_id, created_at=created_at)


# =============================================================================
# Thread summary exclusion
# =============================================================================


class TestThreadSummaryExclusion:
    """Thread summary is accepted in the signature but NOT included in the prompt."""

    @patch("mypalclara.core.prompt_builder.PERSONALITY", "You are Clara.")
    def test_thread_summary_not_in_prompt(self):
        pb = _make_prompt_builder()
        messages = pb.build_prompt(
            user_mems=[],
            proj_mems=[],
            thread_summary="This is a summary of the thread",
            recent_msgs=[],
            user_message="hello",
        )
        # The summary text should not appear anywhere in the messages
        all_content = " ".join(m.content for m in messages)
        assert "THREAD SUMMARY" not in all_content
        assert "This is a summary of the thread" not in all_content

    @patch("mypalclara.core.prompt_builder.PERSONALITY", "You are Clara.")
    def test_thread_summary_none_works(self):
        pb = _make_prompt_builder()
        messages = pb.build_prompt(
            user_mems=[],
            proj_mems=[],
            thread_summary=None,
            recent_msgs=[],
            user_message="hello",
        )
        assert any(m.content == "hello" for m in messages)


# =============================================================================
# Channel context formatting
# =============================================================================


class TestChannelContext:
    @patch("mypalclara.core.prompt_builder.PERSONALITY", "You are Clara.")
    def test_channel_context_included(self):
        pb = _make_prompt_builder()
        channel_msgs = [
            _make_db_message("user", "[Alice]: hey everyone"),
            _make_db_message("assistant", "Hello Alice!"),
            _make_db_message("user", "[Bob]: what's up"),
        ]
        messages = pb.build_prompt(
            user_mems=[],
            proj_mems=[],
            thread_summary=None,
            recent_msgs=[],
            user_message="hi",
            channel_context=channel_msgs,
        )
        all_content = " ".join(m.content for m in messages)
        assert "CHANNEL CONTEXT" in all_content
        assert "[Alice]: hey everyone" in all_content
        assert "Clara: Hello Alice!" in all_content
        assert "[Bob]: what's up" in all_content

    @patch("mypalclara.core.prompt_builder.PERSONALITY", "You are Clara.")
    def test_channel_context_none_no_section(self):
        pb = _make_prompt_builder()
        messages = pb.build_prompt(
            user_mems=[],
            proj_mems=[],
            thread_summary=None,
            recent_msgs=[],
            user_message="hi",
            channel_context=None,
        )
        all_content = " ".join(m.content for m in messages)
        assert "CHANNEL CONTEXT" not in all_content

    @patch("mypalclara.core.prompt_builder.PERSONALITY", "You are Clara.")
    def test_channel_context_empty_list_no_section(self):
        pb = _make_prompt_builder()
        messages = pb.build_prompt(
            user_mems=[],
            proj_mems=[],
            thread_summary=None,
            recent_msgs=[],
            user_message="hi",
            channel_context=[],
        )
        all_content = " ".join(m.content for m in messages)
        assert "CHANNEL CONTEXT" not in all_content

    @patch("mypalclara.core.prompt_builder.PERSONALITY", "You are Clara.")
    def test_assistant_messages_prefixed_with_clara(self):
        pb = _make_prompt_builder()
        channel_msgs = [
            _make_db_message("assistant", "I can help with that!"),
        ]
        messages = pb.build_prompt(
            user_mems=[],
            proj_mems=[],
            thread_summary=None,
            recent_msgs=[],
            user_message="hi",
            channel_context=channel_msgs,
        )
        all_content = " ".join(m.content for m in messages)
        assert "Clara: I can help with that!" in all_content


# =============================================================================
# Token trimming
# =============================================================================


class TestTokenTrimming:
    @patch("mypalclara.core.prompt_builder.PERSONALITY", "You are Clara.")
    def test_under_budget_no_trimming(self):
        pb = _make_prompt_builder()
        msgs = [
            _make_db_message("user", "msg1"),
            _make_db_message("assistant", "reply1"),
        ]
        messages = pb.build_prompt(
            user_mems=[],
            proj_mems=[],
            thread_summary=None,
            recent_msgs=msgs,
            user_message="hello",
            model_name="claude",
        )
        # With claude's 200k window * 0.8 = 160k, a few messages should never be trimmed
        # Count user/assistant messages (excluding system)
        non_system = [m for m in messages if not isinstance(m, SystemMessage)]
        # 2 history + 1 current = 3
        assert len(non_system) == 3

    @patch("mypalclara.core.prompt_builder.PERSONALITY", "You are Clara.")
    @patch("mypalclara.core.prompt_builder.get_context_window", return_value=100)
    def test_over_budget_trims_history(self, mock_ctx):
        """With a tiny context window, long messages should get trimmed."""
        pb = _make_prompt_builder()

        # Create messages that will exceed 80 tokens (100 * 0.8)
        long_content = "word " * 50  # ~50 tokens
        msgs = [
            _make_db_message("user", long_content),
            _make_db_message("assistant", long_content),
            _make_db_message("user", long_content),
            _make_db_message("assistant", long_content),
        ]
        messages = pb.build_prompt(
            user_mems=[],
            proj_mems=[],
            thread_summary=None,
            recent_msgs=msgs,
            user_message="hello",
            model_name="tiny",
        )
        # Some history should have been trimmed, but current message must remain
        assert messages[-1].content == "hello"
        assert isinstance(messages[-1], UserMessage)
        # Should have fewer messages than original (system + 4 history + current = 6)
        assert len(messages) < 6

    @patch("mypalclara.core.prompt_builder.PERSONALITY", "You are Clara.")
    def test_current_message_never_trimmed(self):
        """The current user message must always survive trimming."""
        pb = _make_prompt_builder()
        messages = pb.build_prompt(
            user_mems=[],
            proj_mems=[],
            thread_summary=None,
            recent_msgs=[],
            user_message="important question",
            model_name="claude",
        )
        assert messages[-1].content == "important question"

    @patch("mypalclara.core.prompt_builder.PERSONALITY", "You are Clara.")
    @patch("mypalclara.core.prompt_builder.get_context_window", return_value=200)
    def test_channel_context_trimmed_before_history(self, mock_ctx):
        """Channel context should be trimmed before direct history."""
        pb = _make_prompt_builder()

        long_content = "word " * 30
        channel_msgs = [_make_db_message("user", f"[User{i}]: {long_content}") for i in range(5)]
        history_msgs = [
            _make_db_message("user", "direct msg"),
            _make_db_message("assistant", "direct reply"),
        ]

        messages = pb.build_prompt(
            user_mems=[],
            proj_mems=[],
            thread_summary=None,
            recent_msgs=history_msgs,
            user_message="current",
            channel_context=channel_msgs,
            model_name="tiny",
        )

        # Current message survives
        assert messages[-1].content == "current"


# =============================================================================
# Token counter module
# =============================================================================


class TestTokenCounter:
    def test_count_tokens_basic(self):
        from mypalclara.core.token_counter import count_tokens

        result = count_tokens("hello world")
        assert result > 0
        assert isinstance(result, int)

    def test_count_tokens_empty(self):
        from mypalclara.core.token_counter import count_tokens

        assert count_tokens("") == 0

    def test_count_message_tokens(self):
        from mypalclara.core.token_counter import count_message_tokens

        msgs = [
            SystemMessage(content="system prompt"),
            UserMessage(content="hello"),
        ]
        result = count_message_tokens(msgs)
        assert result > 0

    def test_get_context_window_claude(self):
        from mypalclara.core.token_counter import get_context_window

        assert get_context_window("claude-sonnet-4-5") == 200_000

    def test_get_context_window_gpt4o(self):
        from mypalclara.core.token_counter import get_context_window

        assert get_context_window("gpt-4o-mini") == 128_000

    def test_get_context_window_unknown(self):
        from mypalclara.core.token_counter import get_context_window

        assert get_context_window("some-unknown-model") == 128_000
