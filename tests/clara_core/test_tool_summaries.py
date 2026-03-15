"""Tests for human-readable tool summary generation."""

import pytest

from mypalclara.core.tool_summaries import build_tool_summary_section


def _make_tool(name: str, desc: str) -> dict:
    return {"name": name, "description": desc, "parameters": {}}


class TestToolSummaries:
    def test_basic_summary(self):
        tools = [_make_tool("memory_search", "Search memories by semantic query")]
        lines = build_tool_summary_section(tools)
        text = "\n".join(lines)
        assert "memory_search" in text
        assert "Search memories" in text

    def test_grouping_by_prefix(self):
        tools = [
            _make_tool("mcp__github__list_issues", "List GitHub issues"),
            _make_tool("mcp__github__create_issue", "Create a GitHub issue"),
            _make_tool("memory_search", "Search memories"),
        ]
        lines = build_tool_summary_section(tools)
        text = "\n".join(lines)
        assert "Core" in text
        assert "MCP" in text

    def test_subagent_grouping(self):
        tools = [
            _make_tool("subagent_spawn", "Create a sub-agent"),
            _make_tool("memory_search", "Search memories"),
        ]
        lines = build_tool_summary_section(tools)
        text = "\n".join(lines)
        assert "Subagent" in text

    def test_budget_enforcement(self):
        tools = [_make_tool(f"tool_{i}", f"Description for tool {i} " * 20) for i in range(100)]
        lines = build_tool_summary_section(tools, max_chars=500)
        text = "\n".join(lines)
        assert len(text) <= 600
        assert "more tools" in text

    def test_description_truncated_at_80_chars(self):
        tools = [_make_tool("tool_a", "A" * 200)]
        lines = build_tool_summary_section(tools)
        text = "\n".join(lines)
        assert "A" * 81 not in text

    def test_empty_tools(self):
        lines = build_tool_summary_section([])
        assert len(lines) == 0

    def test_first_sentence_extraction(self):
        tools = [_make_tool("tool_a", "First sentence. Second sentence. Third.")]
        lines = build_tool_summary_section(tools)
        text = "\n".join(lines)
        assert "First sentence" in text
        assert "Second sentence" not in text

    def test_core_group_first(self):
        tools = [
            _make_tool("subagent_spawn", "Create a sub-agent"),
            _make_tool("memory_search", "Search memories"),
            _make_tool("mcp__slack__send", "Send a message"),
        ]
        lines = build_tool_summary_section(tools)
        text = "\n".join(lines)
        core_pos = text.find("Core")
        mcp_pos = text.find("MCP")
        sub_pos = text.find("Subagent")
        assert core_pos < mcp_pos
        assert core_pos < sub_pos
