"""Tests for intentions system."""

from datetime import datetime, timedelta, UTC

import pytest

from clara_core.intentions import (
    CheckStrategy,
    TriggerType,
    _check_context_trigger,
    _check_keyword_trigger,
    _check_time_trigger,
    _check_topic_trigger,
    _parse_trigger_conditions,
    format_intentions_for_prompt,
)


class TestParseConditions:
    """Tests for trigger condition parsing."""

    def test_parse_dict(self):
        """Dict conditions should pass through."""
        conditions = {"type": "keyword", "keywords": ["test"]}
        result = _parse_trigger_conditions(conditions)
        assert result == conditions

    def test_parse_json_string(self):
        """JSON string should be parsed."""
        conditions = '{"type": "keyword", "keywords": ["test"]}'
        result = _parse_trigger_conditions(conditions)
        assert result["type"] == "keyword"
        assert result["keywords"] == ["test"]

    def test_parse_invalid_json(self):
        """Invalid JSON should return default."""
        result = _parse_trigger_conditions("not valid json")
        assert result["type"] == "keyword"
        assert result["keywords"] == []


class TestKeywordTrigger:
    """Tests for keyword trigger checking."""

    def test_exact_match(self):
        """Exact keyword match should fire."""
        conditions = {"keywords": ["meeting"]}
        should_fire, details = _check_keyword_trigger(
            "Let's schedule a meeting",
            conditions,
        )
        assert should_fire is True
        assert "meeting" in details["matched_keywords"]

    def test_case_insensitive(self):
        """Keywords should match case-insensitively by default."""
        conditions = {"keywords": ["MEETING"]}
        should_fire, details = _check_keyword_trigger(
            "let's schedule a meeting",
            conditions,
        )
        assert should_fire is True

    def test_case_sensitive(self):
        """Case sensitive matching when specified."""
        conditions = {"keywords": ["MEETING"], "case_sensitive": True}
        should_fire, _ = _check_keyword_trigger(
            "let's schedule a meeting",
            conditions,
        )
        assert should_fire is False

    def test_multiple_keywords(self):
        """Any matching keyword should fire."""
        conditions = {"keywords": ["meeting", "standup", "sync"]}
        should_fire, details = _check_keyword_trigger(
            "time for the standup",
            conditions,
        )
        assert should_fire is True
        assert "standup" in details["matched_keywords"]

    def test_no_match(self):
        """No matching keywords should not fire."""
        conditions = {"keywords": ["meeting", "standup"]}
        should_fire, _ = _check_keyword_trigger(
            "going to lunch",
            conditions,
        )
        assert should_fire is False

    def test_regex_pattern(self):
        """Regex pattern should match."""
        conditions = {"regex": r"interview.*schedule"}
        should_fire, details = _check_keyword_trigger(
            "need to interview schedule update",
            conditions,
        )
        assert should_fire is True
        assert any("regex:" in kw for kw in details["matched_keywords"])


class TestTopicTrigger:
    """Tests for topic trigger checking."""

    def test_exact_overlap(self):
        """High word overlap should fire."""
        conditions = {"topic": "project deadline", "threshold": 0.5}
        should_fire, details = _check_topic_trigger(
            "what's the deadline for the project?",
            conditions,
        )
        assert should_fire is True

    def test_no_overlap(self):
        """No word overlap should not fire."""
        conditions = {"topic": "project deadline", "threshold": 0.5}
        should_fire, _ = _check_topic_trigger(
            "how's the weather today?",
            conditions,
        )
        assert should_fire is False

    def test_empty_topic(self):
        """Empty topic should not fire."""
        conditions = {"topic": "", "threshold": 0.5}
        should_fire, _ = _check_topic_trigger(
            "anything here",
            conditions,
        )
        assert should_fire is False


class TestTimeTrigger:
    """Tests for time trigger checking."""

    def test_at_time_past(self):
        """Past time should fire."""
        past_time = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        conditions = {"at": past_time}
        now = datetime.now(UTC).replace(tzinfo=None)

        should_fire, details = _check_time_trigger(now, conditions)
        assert should_fire is True
        assert details["type"] == "at"

    def test_at_time_future(self):
        """Future time should not fire."""
        future_time = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        conditions = {"at": future_time}
        now = datetime.now(UTC).replace(tzinfo=None)

        should_fire, _ = _check_time_trigger(now, conditions)
        assert should_fire is False

    def test_after_time_past(self):
        """After past time should fire."""
        past_time = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        conditions = {"after": past_time}
        now = datetime.now(UTC).replace(tzinfo=None)

        should_fire, details = _check_time_trigger(now, conditions)
        assert should_fire is True
        assert details["type"] == "after"

    def test_invalid_time_format(self):
        """Invalid time format should not fire."""
        conditions = {"at": "not a valid time"}
        now = datetime.now(UTC).replace(tzinfo=None)

        should_fire, _ = _check_time_trigger(now, conditions)
        assert should_fire is False


class TestContextTrigger:
    """Tests for context trigger checking."""

    def test_channel_match(self):
        """Channel name match should fire."""
        conditions = {"conditions": {"channel_name": "work"}}
        context = {"channel_name": "work-chat"}

        should_fire, details = _check_context_trigger(context, conditions)
        assert should_fire is True

    def test_channel_no_match(self):
        """Channel name mismatch should not fire."""
        conditions = {"conditions": {"channel_name": "work"}}
        context = {"channel_name": "general"}

        should_fire, _ = _check_context_trigger(context, conditions)
        assert should_fire is False

    def test_is_dm_match(self):
        """DM match should fire."""
        conditions = {"conditions": {"is_dm": True}}
        context = {"is_dm": True}

        should_fire, _ = _check_context_trigger(context, conditions)
        assert should_fire is True

    def test_is_dm_mismatch(self):
        """DM mismatch should not fire."""
        conditions = {"conditions": {"is_dm": True}}
        context = {"is_dm": False}

        should_fire, _ = _check_context_trigger(context, conditions)
        assert should_fire is False

    def test_multiple_conditions(self):
        """Multiple conditions must all match."""
        conditions = {"conditions": {"channel_name": "work", "is_dm": False}}
        context = {"channel_name": "work-chat", "is_dm": False}

        should_fire, _ = _check_context_trigger(context, conditions)
        assert should_fire is True

    def test_multiple_conditions_partial_fail(self):
        """Partial match should not fire."""
        conditions = {"conditions": {"channel_name": "work", "is_dm": True}}
        context = {"channel_name": "work-chat", "is_dm": False}

        should_fire, _ = _check_context_trigger(context, conditions)
        assert should_fire is False

    def test_empty_conditions(self):
        """Empty conditions should not fire."""
        conditions = {"conditions": {}}
        context = {"channel_name": "test"}

        should_fire, _ = _check_context_trigger(context, conditions)
        assert should_fire is False


class TestFormatIntentions:
    """Tests for formatting intentions for prompt."""

    def test_empty_list(self):
        """Empty list should return empty string."""
        result = format_intentions_for_prompt([])
        assert result == ""

    def test_single_intention(self):
        """Single intention should format correctly."""
        intentions = [
            {"content": "Remember to follow up on the interview"}
        ]
        result = format_intentions_for_prompt(intentions)

        assert "Reminders" in result
        assert "Remember to follow up on the interview" in result

    def test_multiple_intentions(self):
        """Multiple intentions should all be included."""
        intentions = [
            {"content": "First reminder"},
            {"content": "Second reminder"},
        ]
        result = format_intentions_for_prompt(intentions)

        assert "First reminder" in result
        assert "Second reminder" in result

    def test_max_intentions(self):
        """Should respect max_intentions limit."""
        intentions = [
            {"content": f"Reminder {i}"} for i in range(10)
        ]
        result = format_intentions_for_prompt(intentions, max_intentions=2)

        assert "Reminder 0" in result
        assert "Reminder 1" in result
        assert "Reminder 5" not in result
