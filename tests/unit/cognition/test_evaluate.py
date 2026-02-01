"""Tests for the cognition evaluator module."""

import pytest

from clara_core.cognition.evaluator import (
    Evaluator,
    EvaluatorConfig,
    create_evaluator,
)
from clara_core.cognition.types import (
    CognitionEvent,
    EvaluationResult,
    EventMetadata,
    EventType,
    QuickContext,
)


@pytest.fixture
def evaluator():
    """Create an evaluator with LLM disabled for fast tests."""
    config = EvaluatorConfig(
        bot_user_ids={"bot-123", "bot-456"},
        mention_patterns=[r"@clara\b", r"hey clara"],
        command_prefix="!",
        use_llm_evaluation=False,
    )
    return Evaluator(config=config)


@pytest.fixture
def evaluator_with_mock_llm():
    """Create an evaluator with a mock LLM for testing LLM evaluation."""

    async def mock_llm(messages):
        """Mock LLM that returns a valid JSON response."""
        return '{"should_respond": true, "complexity": "high", "suggested_tier": "high", "tone": "question", "reasoning": "Complex coding question"}'

    config = EvaluatorConfig(
        bot_user_ids={"bot-123"},
        use_llm_evaluation=True,
    )
    return Evaluator(config=config, llm_fn=mock_llm)


def make_event(content: str, user_id: str = "user-1") -> CognitionEvent:
    """Helper to create a message event."""
    return CognitionEvent(
        type=EventType.MESSAGE,
        payload={"content": content},
        metadata=EventMetadata(user_id=user_id),
    )


class TestPatternMatchingIgnore:
    """Tests for fast-path IGNORE patterns."""

    @pytest.mark.asyncio
    async def test_bot_own_message_ignored(self, evaluator):
        """Bot's own messages should be ignored."""
        event = make_event("Hello world", user_id="bot-123")
        result = await evaluator.evaluate(event)

        assert result.should_respond is False
        assert "Bot's own message" in result.reasoning

    @pytest.mark.asyncio
    async def test_empty_message_ignored(self, evaluator):
        """Empty messages should be ignored."""
        event = make_event("")
        result = await evaluator.evaluate(event)

        assert result.should_respond is False
        assert "Empty message" in result.reasoning

    @pytest.mark.asyncio
    async def test_whitespace_only_ignored(self, evaluator):
        """Whitespace-only messages should be ignored."""
        event = make_event("   \t\n  ")
        result = await evaluator.evaluate(event)

        assert result.should_respond is False
        assert "Empty message" in result.reasoning

    @pytest.mark.asyncio
    async def test_system_join_message_ignored(self, evaluator):
        """System join notifications should be ignored."""
        event = make_event("[User has joined the channel]")
        result = await evaluator.evaluate(event)

        assert result.should_respond is False
        assert "Skip pattern" in result.reasoning

    @pytest.mark.asyncio
    async def test_system_leave_message_ignored(self, evaluator):
        """System leave notifications should be ignored."""
        event = make_event("[User has left the channel]")
        result = await evaluator.evaluate(event)

        assert result.should_respond is False
        assert "Skip pattern" in result.reasoning

    @pytest.mark.asyncio
    async def test_system_prefix_ignored(self, evaluator):
        """System-prefixed messages should be ignored."""
        event = make_event("<System> Server maintenance in 5 minutes")
        result = await evaluator.evaluate(event)

        assert result.should_respond is False
        assert "Skip pattern" in result.reasoning


class TestPatternMatchingRespond:
    """Tests for fast-path RESPOND patterns."""

    @pytest.mark.asyncio
    async def test_dm_always_respond(self, evaluator):
        """Direct messages should always get a response."""
        event = make_event("Hello there")
        context = QuickContext(is_dm=True)
        result = await evaluator.evaluate(event, context)

        assert result.should_respond is True
        assert "Direct message" in result.reasoning

    @pytest.mark.asyncio
    async def test_mention_flag_respond(self, evaluator):
        """Messages with has_mention flag should get response."""
        event = make_event("What time is it?")
        context = QuickContext(has_mention=True)
        result = await evaluator.evaluate(event, context)

        assert result.should_respond is True
        assert "Bot mentioned" in result.reasoning

    @pytest.mark.asyncio
    async def test_mention_pattern_in_content_respond(self, evaluator):
        """Messages matching mention pattern should get response."""
        event = make_event("@clara what's the weather?")
        result = await evaluator.evaluate(event)

        assert result.should_respond is True
        assert "Mention pattern" in result.reasoning

    @pytest.mark.asyncio
    async def test_casual_mention_respond(self, evaluator):
        """Casual mention patterns should trigger response."""
        event = make_event("hey clara, can you help me?")
        result = await evaluator.evaluate(event)

        assert result.should_respond is True
        assert "Mention pattern" in result.reasoning

    @pytest.mark.asyncio
    async def test_command_prefix_respond(self, evaluator):
        """Messages starting with command prefix should get response."""
        event = make_event("!help")
        result = await evaluator.evaluate(event)

        assert result.should_respond is True
        assert "Command prefix" in result.reasoning

    @pytest.mark.asyncio
    async def test_question_detection_in_dm(self, evaluator):
        """Questions in DM should be flagged."""
        event = make_event("What time is it?")
        context = QuickContext(is_dm=True)
        result = await evaluator.evaluate(event, context)

        assert result.is_question is True


class TestLLMEvaluation:
    """Tests for LLM-based evaluation."""

    @pytest.mark.asyncio
    async def test_llm_evaluation_called_for_ambiguous(self, evaluator_with_mock_llm):
        """Ambiguous messages should trigger LLM evaluation."""
        event = make_event("I need help with my Python code")
        result = await evaluator_with_mock_llm.evaluate(event)

        # Mock returns high complexity
        assert result.should_respond is True
        assert result.complexity == "high"
        assert result.suggested_tier == "high"
        assert result.tone == "question"

    @pytest.mark.asyncio
    async def test_llm_evaluation_parsing(self):
        """Test parsing various LLM response formats."""
        evaluator = Evaluator()

        # Standard JSON
        result = evaluator._parse_llm_response(
            '{"should_respond": true, "complexity": "low", "tone": "greeting"}'
        )
        assert result.should_respond is True
        assert result.complexity == "low"
        assert result.is_greeting is True

        # JSON with markdown code block
        result = evaluator._parse_llm_response(
            """```json
{"should_respond": false, "complexity": "medium", "tone": "statement"}
```"""
        )
        assert result.should_respond is False
        assert result.complexity == "medium"

        # JSON with extra text
        result = evaluator._parse_llm_response(
            'Here is the analysis: {"should_respond": true, "complexity": "high"} done.'
        )
        assert result.should_respond is True
        assert result.complexity == "high"

    @pytest.mark.asyncio
    async def test_llm_error_defaults_to_respond(self):
        """LLM errors should default to responding."""

        async def failing_llm(messages):
            raise RuntimeError("API error")

        config = EvaluatorConfig(use_llm_evaluation=True)
        evaluator = Evaluator(config=config, llm_fn=failing_llm)

        event = make_event("Some message")
        result = await evaluator.evaluate(event)

        # Should still respond despite error
        assert result.should_respond is True
        assert "failed" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_llm_parse_error_defaults_to_respond(self):
        """LLM returning invalid JSON should default to responding."""

        async def bad_json_llm(messages):
            return "This is not JSON at all"

        config = EvaluatorConfig(use_llm_evaluation=True)
        evaluator = Evaluator(config=config, llm_fn=bad_json_llm)

        event = make_event("Some message")
        result = await evaluator.evaluate(event)

        # Should still respond despite parse error
        assert result.should_respond is True
        assert "Parse error" in result.reasoning


class TestComplexityToTierMapping:
    """Tests for complexity to model tier mapping."""

    @pytest.mark.asyncio
    async def test_low_complexity_maps_to_low_tier(self):
        """Low complexity should suggest low tier."""
        evaluator = Evaluator()
        result = evaluator._parse_llm_response(
            '{"should_respond": true, "complexity": "low"}'
        )
        assert result.suggested_tier == "low"

    @pytest.mark.asyncio
    async def test_medium_complexity_maps_to_mid_tier(self):
        """Medium complexity should suggest mid tier."""
        evaluator = Evaluator()
        result = evaluator._parse_llm_response(
            '{"should_respond": true, "complexity": "medium"}'
        )
        assert result.suggested_tier == "mid"

    @pytest.mark.asyncio
    async def test_high_complexity_maps_to_high_tier(self):
        """High complexity should suggest high tier."""
        evaluator = Evaluator()
        result = evaluator._parse_llm_response(
            '{"should_respond": true, "complexity": "high"}'
        )
        assert result.suggested_tier == "high"

    @pytest.mark.asyncio
    async def test_explicit_tier_overrides_complexity(self):
        """Explicit suggested_tier should override complexity-based default."""
        evaluator = Evaluator()
        result = evaluator._parse_llm_response(
            '{"should_respond": true, "complexity": "low", "suggested_tier": "high"}'
        )
        assert result.suggested_tier == "high"


class TestNonMessageEvents:
    """Tests for non-message event handling."""

    @pytest.mark.asyncio
    async def test_tool_result_event(self, evaluator):
        """Tool result events should trigger response."""
        event = CognitionEvent(
            type=EventType.TOOL_RESULT,
            payload={"result": "file created"},
        )
        result = await evaluator.evaluate(event)

        assert result.should_respond is True
        assert "Tool result" in result.reasoning

    @pytest.mark.asyncio
    async def test_system_event(self, evaluator):
        """System events should not trigger response."""
        event = CognitionEvent(
            type=EventType.SYSTEM,
            payload={"event": "session_timeout"},
        )
        result = await evaluator.evaluate(event)

        assert result.should_respond is False
        assert "System event" in result.reasoning

    @pytest.mark.asyncio
    async def test_scheduled_event(self, evaluator):
        """Scheduled events should trigger response."""
        event = CognitionEvent(
            type=EventType.SCHEDULED,
            payload={"task": "daily_summary"},
        )
        result = await evaluator.evaluate(event)

        assert result.should_respond is True
        assert "Scheduled" in result.reasoning


class TestFactoryFunction:
    """Tests for the create_evaluator factory."""

    def test_create_evaluator_defaults(self):
        """Factory with defaults should work."""
        evaluator = create_evaluator()
        assert evaluator.config.use_llm_evaluation is True
        assert evaluator.config.command_prefix == "!"

    def test_create_evaluator_custom_config(self):
        """Factory with custom config should apply settings."""
        evaluator = create_evaluator(
            bot_user_ids={"bot-1", "bot-2"},
            mention_patterns=[r"@mybot"],
            command_prefix="/",
            use_llm=False,
        )
        assert "bot-1" in evaluator.config.bot_user_ids
        assert evaluator.config.command_prefix == "/"
        assert evaluator.config.use_llm_evaluation is False
