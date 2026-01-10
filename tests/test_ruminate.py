"""Tests for the Ruminate node."""

import pytest

from mypalclara.models.state import FacultyResult
from mypalclara.nodes.ruminate import (
    _synthesize_from_iterations,
    parse_rumination_response,
)


class TestParseRuminationResponse:
    """Tests for the parse_rumination_response function."""

    def test_parses_speak_decision(self):
        """Parse a speak decision with response."""
        text = """
        <decision>speak</decision>
        <reasoning>User asked a simple question</reasoning>
        <response>Hello! How can I help you today?</response>
        """
        result = parse_rumination_response(text)
        assert result.decision == "speak"
        assert result.reasoning == "User asked a simple question"
        assert result.response_draft == "Hello! How can I help you today?"
        assert result.faculty is None
        assert result.intent is None

    def test_parses_command_decision(self):
        """Parse a command decision with faculty and intent."""
        text = """
        <decision>command</decision>
        <reasoning>User wants to see their GitHub issues</reasoning>
        <faculty>github</faculty>
        <intent>List open issues in the repo</intent>
        """
        result = parse_rumination_response(text)
        assert result.decision == "command"
        assert result.reasoning == "User wants to see their GitHub issues"
        assert result.faculty == "github"
        assert result.intent == "List open issues in the repo"
        assert result.response_draft is None

    def test_parses_wait_decision(self):
        """Parse a wait decision."""
        text = """
        <decision>wait</decision>
        <reasoning>Message wasn't directed at me</reasoning>
        <wait_reason>Not addressed directly</wait_reason>
        """
        result = parse_rumination_response(text)
        assert result.decision == "wait"
        assert result.reasoning == "Message wasn't directed at me"
        assert result.wait_reason == "Not addressed directly"

    def test_parses_cognitive_outputs(self):
        """Parse remember and observe tags."""
        text = """
        <decision>speak</decision>
        <reasoning>Noted user preference</reasoning>
        <response>Got it!</response>
        <remember>User prefers dark mode</remember>
        <observe>User seems tired today</observe>
        """
        result = parse_rumination_response(text)
        assert len(result.cognitive_outputs) == 2

        remember_output = next(o for o in result.cognitive_outputs if o.type == "remember")
        assert remember_output.content == "User prefers dark mode"
        assert remember_output.importance == 0.5

        observe_output = next(o for o in result.cognitive_outputs if o.type == "observe")
        assert observe_output.content == "User seems tired today"
        assert observe_output.importance == 0.3

    def test_defaults_to_speak_on_invalid_decision(self):
        """Invalid decision defaults to speak."""
        text = """
        <decision>invalid</decision>
        <reasoning>Some reasoning</reasoning>
        """
        result = parse_rumination_response(text)
        assert result.decision == "speak"

    def test_defaults_to_speak_on_missing_decision(self):
        """Missing decision tag defaults to speak."""
        text = """
        <reasoning>Some reasoning</reasoning>
        <response>Hello!</response>
        """
        result = parse_rumination_response(text)
        assert result.decision == "speak"

    def test_fallback_response_when_no_tag(self):
        """Use full text as response when no <response> tag present."""
        text = "Hello! I'm Clara, nice to meet you."
        result = parse_rumination_response(text)
        assert result.decision == "speak"
        assert "Clara" in result.response_draft


class TestSynthesizeFromIterations:
    """Tests for the _synthesize_from_iterations fallback."""

    def test_synthesize_successful_result(self):
        """Synthesize response from successful faculty result."""
        state = {
            "event": None,
            "faculty_result": FacultyResult(
                success=True,
                summary="Found 3 open issues",
                data={"issues": []},
            ),
        }
        response = _synthesize_from_iterations(state)
        assert "Found 3 open issues" in response

    def test_synthesize_error_result(self):
        """Synthesize response from failed faculty result."""
        state = {
            "event": None,
            "faculty_result": FacultyResult(
                success=False,
                summary="",
                error="Repository not found",
            ),
        }
        response = _synthesize_from_iterations(state)
        assert "Repository not found" in response
        assert "trouble" in response

    def test_synthesize_no_result(self):
        """Synthesize response when no faculty result."""
        state = {
            "event": None,
        }
        response = _synthesize_from_iterations(state)
        assert "tangled" in response or "rephrase" in response
