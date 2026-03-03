"""Tests for compositional prompt builder with modes and section budgets."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from mypalclara.core.llm.messages import SystemMessage, UserMessage
from mypalclara.core.prompt_builder import PromptBuilder, PromptMode


class TestPromptModes:
    def _make_builder(self):
        return PromptBuilder(agent_id="test", llm_callable=None)

    @patch("mypalclara.core.prompt_builder.PERSONALITY", "You are Clara.")
    def test_none_mode_returns_minimal(self):
        builder = self._make_builder()
        messages = builder.build_prompt(
            user_mems=[],
            proj_mems=[],
            thread_summary="",
            recent_msgs=[],
            user_message="hi",
            mode=PromptMode.NONE,
        )
        # Should return just system + user
        assert len(messages) == 2
        assert messages[-1].content == "hi"

    @patch("mypalclara.core.prompt_builder.PERSONALITY", "You are Clara.")
    def test_none_mode_system_message_has_bot_name(self):
        builder = self._make_builder()
        messages = builder.build_prompt(
            user_mems=[],
            proj_mems=[],
            thread_summary="",
            recent_msgs=[],
            user_message="hi",
            mode=PromptMode.NONE,
        )
        # System message should mention the bot name
        assert isinstance(messages[0], SystemMessage)
        assert "Clara" in messages[0].content

    @patch("mypalclara.core.prompt_builder.PERSONALITY", "You are Clara.")
    def test_none_mode_ignores_memories(self):
        builder = self._make_builder()
        messages = builder.build_prompt(
            user_mems=["likes coffee"],
            proj_mems=["project detail"],
            thread_summary="some summary",
            recent_msgs=[],
            user_message="hi",
            mode=PromptMode.NONE,
        )
        # Should still be just 2 messages, ignoring memories
        assert len(messages) == 2
        all_content = " ".join(m.content for m in messages)
        assert "coffee" not in all_content

    @patch("mypalclara.core.prompt_builder.PERSONALITY", "You are Clara.")
    def test_full_mode_preserves_existing_behavior(self):
        builder = self._make_builder()
        messages = builder.build_prompt(
            user_mems=["likes coffee"],
            proj_mems=[],
            thread_summary="",
            recent_msgs=[],
            user_message="hello",
            mode=PromptMode.FULL,
        )
        # Full mode should have system message with persona + context
        assert any("Clara" in m.content for m in messages if hasattr(m, "content"))
        assert messages[-1].content == "hello"

    @patch("mypalclara.core.prompt_builder.PERSONALITY", "You are Clara.")
    def test_full_mode_includes_memories(self):
        builder = self._make_builder()
        messages = builder.build_prompt(
            user_mems=["likes coffee"],
            proj_mems=[],
            thread_summary="",
            recent_msgs=[],
            user_message="hello",
            mode=PromptMode.FULL,
        )
        all_content = " ".join(m.content for m in messages)
        assert "coffee" in all_content

    @patch("mypalclara.core.prompt_builder.PERSONALITY", "You are Clara.")
    def test_default_mode_is_full(self):
        builder = self._make_builder()
        # Call without mode parameter — should work (backward compatible)
        messages = builder.build_prompt(
            user_mems=[],
            proj_mems=[],
            thread_summary="",
            recent_msgs=[],
            user_message="test",
        )
        assert len(messages) >= 2

    @patch("mypalclara.core.prompt_builder.PERSONALITY", "You are Clara.")
    def test_minimal_mode_includes_persona(self):
        builder = self._make_builder()
        messages = builder.build_prompt(
            user_mems=["likes coffee"],
            proj_mems=["project detail"],
            thread_summary="",
            recent_msgs=[],
            user_message="hi",
            mode=PromptMode.MINIMAL,
        )
        # Should have persona in system message
        assert isinstance(messages[0], SystemMessage)
        assert "Clara" in messages[0].content
        # Should have user message at end
        assert messages[-1].content == "hi"

    @patch("mypalclara.core.prompt_builder.PERSONALITY", "You are Clara.")
    def test_minimal_mode_skips_memories(self):
        builder = self._make_builder()
        messages = builder.build_prompt(
            user_mems=["likes coffee"],
            proj_mems=["project detail"],
            thread_summary="",
            recent_msgs=[],
            user_message="hi",
            mode=PromptMode.MINIMAL,
        )
        all_content = " ".join(m.content for m in messages)
        # Minimal mode should NOT include memories, emotions, topics, or graph
        assert "coffee" not in all_content
        assert "project detail" not in all_content

    @patch("mypalclara.core.prompt_builder.PERSONALITY", "You are Clara.")
    def test_minimal_mode_includes_runtime(self):
        builder = self._make_builder()
        messages = builder.build_prompt(
            user_mems=[],
            proj_mems=[],
            thread_summary="",
            recent_msgs=[],
            user_message="hi",
            mode=PromptMode.MINIMAL,
        )
        all_content = " ".join(m.content for m in messages)
        # Minimal mode should include runtime info
        assert "Runtime" in all_content or "Agent" in all_content


class TestSectionBuilders:
    def _make_builder(self):
        return PromptBuilder(agent_id="test_agent", llm_callable=None)

    def test_build_datetime_includes_timestamp(self):
        builder = self._make_builder()
        lines = builder._build_datetime()
        assert len(lines) > 0
        assert any("202" in line for line in lines)

    def test_build_datetime_includes_header(self):
        builder = self._make_builder()
        lines = builder._build_datetime()
        assert lines[0] == "## Current Date & Time"

    def test_build_runtime_includes_agent_id(self):
        builder = self._make_builder()
        lines = builder._build_runtime()
        assert any("test_agent" in line for line in lines)

    def test_build_runtime_includes_header(self):
        builder = self._make_builder()
        lines = builder._build_runtime()
        assert lines[0] == "## Runtime"

    def test_build_runtime_includes_os_and_python(self):
        builder = self._make_builder()
        lines = builder._build_runtime()
        joined = "\n".join(lines)
        assert "OS:" in joined
        assert "Python:" in joined


class TestSectionBudgets:
    def test_short_text_unchanged(self):
        result = PromptBuilder._apply_section_budget("short", 1000)
        assert result == "short"

    def test_exact_budget_unchanged(self):
        text = "A" * 100
        result = PromptBuilder._apply_section_budget(text, 100)
        assert result == text

    def test_long_text_truncated_70_20(self):
        text = "A" * 200
        result = PromptBuilder._apply_section_budget(text, 100)
        assert len(result) < 200
        assert result.startswith("A" * 70)
        assert result.endswith("A" * 20)
        assert "truncated" in result

    def test_truncation_marker_includes_sizes(self):
        text = "X" * 500
        result = PromptBuilder._apply_section_budget(text, 100)
        # Marker should mention the original size and kept sizes
        assert "70" in result
        assert "20" in result
        assert "500" in result

    def test_truncation_preserves_head_and_tail_content(self):
        # Build text with distinct head and tail
        text = "HEAD" * 50 + "TAIL" * 50
        result = PromptBuilder._apply_section_budget(text, 100)
        # Head portion should start with HEAD content
        assert result.startswith("HEAD")
        # Tail portion should end with TAIL content
        assert result.endswith("TAIL")


class TestPromptModeEnum:
    def test_enum_values(self):
        assert PromptMode.FULL.value == "full"
        assert PromptMode.MINIMAL.value == "minimal"
        assert PromptMode.NONE.value == "none"

    def test_enum_members(self):
        members = list(PromptMode)
        assert len(members) == 3


class TestConstants:
    def test_section_max_chars_exists(self):
        from mypalclara.core.prompt_builder import SECTION_MAX_CHARS

        assert SECTION_MAX_CHARS == 10_000

    def test_total_system_max_chars_exists(self):
        from mypalclara.core.prompt_builder import TOTAL_SYSTEM_MAX_CHARS

        assert TOTAL_SYSTEM_MAX_CHARS == 200_000
