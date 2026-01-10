"""Tests for the Evaluate node."""

import pytest

from mypalclara.models.events import ChannelMode, Event, EventType
from mypalclara.models.state import QuickContext
from mypalclara.nodes.evaluate import should_ignore, should_proceed


class TestShouldIgnore:
    """Tests for the should_ignore function."""

    def test_ignores_empty_content(self, sample_quick_context):
        """Empty content should be ignored."""
        event = Event(
            id="1",
            type=EventType.MESSAGE,
            user_id="u1",
            user_name="User",
            channel_id="c1",
            content="",
            channel_mode=ChannelMode.ASSISTANT,
        )
        ignore, reason = should_ignore(event, sample_quick_context)
        assert ignore is True
        assert "no content" in reason

    def test_ignores_short_content(self, sample_quick_context):
        """Very short content should be ignored."""
        event = Event(
            id="1",
            type=EventType.MESSAGE,
            user_id="u1",
            user_name="User",
            channel_id="c1",
            content="ok",
            channel_mode=ChannelMode.ASSISTANT,
        )
        ignore, reason = should_ignore(event, sample_quick_context)
        assert ignore is True
        assert "too short" in reason

    def test_ignores_simple_acknowledgments(self, sample_quick_context):
        """Simple acknowledgments like 'ok', 'thanks' should be ignored."""
        for content in ["ok", "okay", "thanks", "thank you", "lol", "haha"]:
            event = Event(
                id="1",
                type=EventType.MESSAGE,
                user_id="u1",
                user_name="User",
                channel_id="c1",
                content=content,
                channel_mode=ChannelMode.ASSISTANT,
            )
            ignore, _ = should_ignore(event, sample_quick_context)
            assert ignore is True, f"'{content}' should be ignored"

    def test_ignores_bot_commands(self, sample_quick_context):
        """Bot commands for other bots should be ignored."""
        for content in ["!play something", "/help", ".roll 20"]:
            event = Event(
                id="1",
                type=EventType.MESSAGE,
                user_id="u1",
                user_name="User",
                channel_id="c1",
                content=content,
                channel_mode=ChannelMode.ASSISTANT,
            )
            ignore, _ = should_ignore(event, sample_quick_context)
            assert ignore is True, f"'{content}' should be ignored"

    def test_ignores_channel_off(self, sample_quick_context):
        """Messages in OFF channels should be ignored."""
        event = Event(
            id="1",
            type=EventType.MESSAGE,
            user_id="u1",
            user_name="User",
            channel_id="c1",
            content="Hello Clara!",
            channel_mode=ChannelMode.OFF,
        )
        ignore, reason = should_ignore(event, sample_quick_context)
        assert ignore is True
        assert "OFF" in reason

    def test_does_not_ignore_real_message(self, sample_quick_context):
        """Real messages should not be ignored."""
        event = Event(
            id="1",
            type=EventType.MESSAGE,
            user_id="u1",
            user_name="User",
            channel_id="c1",
            content="Hello Clara, how are you today?",
            channel_mode=ChannelMode.ASSISTANT,
        )
        ignore, _ = should_ignore(event, sample_quick_context)
        assert ignore is False


class TestShouldProceed:
    """Tests for the should_proceed function."""

    def test_proceeds_on_dm(self, sample_quick_context):
        """DMs should always proceed."""
        event = Event(
            id="1",
            type=EventType.MESSAGE,
            user_id="u1",
            user_name="User",
            channel_id="c1",
            content="Hello",
            is_dm=True,
            channel_mode=ChannelMode.ASSISTANT,
        )
        proceed, reason = should_proceed(event, sample_quick_context)
        assert proceed is True
        assert "direct message" in reason

    def test_proceeds_on_mention(self, sample_quick_context):
        """Messages mentioning Clara should proceed."""
        event = Event(
            id="1",
            type=EventType.MESSAGE,
            user_id="u1",
            user_name="User",
            channel_id="c1",
            content="@Clara hello",
            mentioned=True,
            channel_mode=ChannelMode.ASSISTANT,
        )
        proceed, reason = should_proceed(event, sample_quick_context)
        assert proceed is True
        assert "mentioned" in reason

    def test_proceeds_on_reply(self, sample_quick_context):
        """Replies to Clara should proceed."""
        event = Event(
            id="1",
            type=EventType.MESSAGE,
            user_id="u1",
            user_name="User",
            channel_id="c1",
            content="Thanks!",
            reply_to_clara=True,
            channel_mode=ChannelMode.ASSISTANT,
        )
        proceed, reason = should_proceed(event, sample_quick_context)
        assert proceed is True
        assert "reply" in reason

    def test_proceeds_in_conversational_mode(self, sample_quick_context):
        """Conversational channels should proceed freely."""
        event = Event(
            id="1",
            type=EventType.MESSAGE,
            user_id="u1",
            user_name="User",
            channel_id="c1",
            content="What do you think?",
            channel_mode=ChannelMode.CONVERSATIONAL,
        )
        proceed, reason = should_proceed(event, sample_quick_context)
        assert proceed is True
        assert "conversational" in reason

    def test_does_not_proceed_in_quiet_mode(self, sample_quick_context):
        """Quiet channels should not proceed without direct address."""
        event = Event(
            id="1",
            type=EventType.MESSAGE,
            user_id="u1",
            user_name="User",
            channel_id="c1",
            content="Hello everyone",
            channel_mode=ChannelMode.QUIET,
        )
        proceed, reason = should_proceed(event, sample_quick_context)
        assert proceed is False
        assert "quiet" in reason

    def test_does_not_proceed_in_assistant_mode_without_address(self, sample_quick_context):
        """Assistant mode should not proceed without being addressed."""
        event = Event(
            id="1",
            type=EventType.MESSAGE,
            user_id="u1",
            user_name="User",
            channel_id="c1",
            content="Hello everyone",
            channel_mode=ChannelMode.ASSISTANT,
        )
        proceed, reason = should_proceed(event, sample_quick_context)
        assert proceed is False
        assert "assistant" in reason.lower()
