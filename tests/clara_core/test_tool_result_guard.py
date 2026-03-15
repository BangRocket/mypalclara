"""Tests for intelligent tool result size capping."""

import json

import pytest

from mypalclara.core.tool_result_guard import ToolResultGuard


class TestTextTruncation:
    def test_short_text_not_truncated(self):
        guard = ToolResultGuard(max_chars=1000)
        result = guard.cap("tool", "call_1", "short text")
        assert result.content == "short text"
        assert not result.was_truncated

    def test_long_text_70_20_split(self):
        guard = ToolResultGuard(max_chars=100)
        text = "A" * 200
        result = guard.cap("tool", "call_1", text)
        assert result.was_truncated
        assert result.strategy == "text_70_20"
        assert len(result.content) <= 120  # 100 + marker overhead
        assert result.content.startswith("A" * 70)
        assert result.content.endswith("A" * 20)
        assert "truncated" in result.content

    def test_preserves_original_size(self):
        guard = ToolResultGuard(max_chars=100)
        text = "X" * 500
        result = guard.cap("tool", "call_1", text)
        assert result.original_size == 500


class TestJsonTruncation:
    def test_small_json_not_truncated(self):
        guard = ToolResultGuard(max_chars=1000)
        data = json.dumps({"key": "value"})
        result = guard.cap("tool", "call_1", data)
        assert not result.was_truncated

    def test_large_json_array_trimmed(self):
        guard = ToolResultGuard(max_chars=200)
        data = json.dumps({"items": [f"item_{i}" for i in range(100)]})
        result = guard.cap("tool", "call_1", data)
        assert result.was_truncated
        assert result.strategy == "json"
        parsed = json.loads(result.content.split("\n...[")[0])
        assert len(parsed["items"]) == 5

    def test_invalid_json_falls_back_to_text(self):
        guard = ToolResultGuard(max_chars=100)
        text = "{not valid json" + "x" * 200
        result = guard.cap("tool", "call_1", text)
        assert result.was_truncated
        assert result.strategy == "text_70_20"


class TestErrorResults:
    def test_error_not_truncated(self):
        guard = ToolResultGuard(max_chars=50)
        error = "Error: " + "x" * 200
        result = guard.cap("tool", "call_1", error)
        assert not result.was_truncated
        assert result.content == error

    def test_traceback_not_truncated(self):
        guard = ToolResultGuard(max_chars=50)
        error = "Traceback (most recent call last):\n" + "x" * 200
        result = guard.cap("tool", "call_1", error)
        assert not result.was_truncated


class TestToolNameNormalization:
    def test_unknown_tool_name_preserved(self):
        guard = ToolResultGuard(max_chars=1000)
        result = guard.cap("", "call_1", "output")
        assert result.content == "output"
