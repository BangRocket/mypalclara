"""Tests for tool loop detection."""

import pytest

from mypalclara.core.tool_guard import LoopAction, ToolLoopGuard


class TestGenericRepeat:
    def test_allow_normal_calls(self):
        guard = ToolLoopGuard()
        for i in range(9):
            result = guard.check(f"tool_{i}", {"arg": i})
            assert result.action == LoopAction.ALLOW

    def test_warn_at_10_identical_calls(self):
        guard = ToolLoopGuard()
        for i in range(9):
            guard.check("read_file", {"path": "/foo"})
            guard.record_result("read_file", {"path": "/foo"}, f"result_{i}")
        result = guard.check("read_file", {"path": "/foo"})
        assert result.action == LoopAction.WARN
        assert result.pattern == "generic_repeat"

    def test_stop_at_30_identical_calls(self):
        guard = ToolLoopGuard()
        for i in range(29):
            guard.check("read_file", {"path": "/foo"})
            guard.record_result("read_file", {"path": "/foo"}, f"result_{i}")
        result = guard.check("read_file", {"path": "/foo"})
        assert result.action == LoopAction.STOP
        assert result.pattern == "generic_repeat"

    def test_different_args_not_repeated(self):
        guard = ToolLoopGuard()
        for i in range(15):
            result = guard.check("read_file", {"path": f"/file_{i}"})
            assert result.action == LoopAction.ALLOW
            guard.record_result("read_file", {"path": f"/file_{i}"}, f"content_{i}")


class TestPollNoProgress:
    def test_stop_on_unchanged_results(self):
        guard = ToolLoopGuard()
        for i in range(4):
            guard.check("get_status", {"id": "123"})
            guard.record_result("get_status", {"id": "123"}, "status: pending")
        result = guard.check("get_status", {"id": "123"})
        assert result.action == LoopAction.STOP
        assert result.pattern == "poll_no_progress"

    def test_allow_when_results_change(self):
        guard = ToolLoopGuard()
        for i in range(10):
            guard.check("get_status", {"id": "123"})
            guard.record_result("get_status", {"id": "123"}, f"status: step_{i}")
        result = guard.check("get_status", {"id": "123"})
        assert result.action != LoopAction.STOP


class TestPingPong:
    def test_detect_ping_pong(self):
        guard = ToolLoopGuard()
        for _ in range(2):
            guard.check("read_file", {"path": "/a"})
            guard.record_result("read_file", {"path": "/a"}, "content_a")
            guard.check("write_file", {"path": "/b"})
            guard.record_result("write_file", {"path": "/b"}, "ok")
        result = guard.check("read_file", {"path": "/a"})
        assert result.action == LoopAction.STOP
        assert result.pattern == "ping_pong"

    def test_no_false_positive_with_variation(self):
        guard = ToolLoopGuard()
        guard.check("read_file", {"path": "/a"})
        guard.record_result("read_file", {"path": "/a"}, "content_a")
        guard.check("write_file", {"path": "/b"})
        guard.record_result("write_file", {"path": "/b"}, "ok")
        guard.check("read_file", {"path": "/a"})
        guard.record_result("read_file", {"path": "/a"}, "content_a")
        guard.check("search", {"q": "something"})
        guard.record_result("search", {"q": "something"}, "results")
        result = guard.check("read_file", {"path": "/a"})
        assert result.action == LoopAction.ALLOW


class TestCircuitBreaker:
    def test_circuit_breaker_hard_stop(self):
        guard = ToolLoopGuard()
        for i in range(29):
            guard.check("tool_a", {"x": 1})
            guard.record_result("tool_a", {"x": 1}, "same_result")
        result = guard.check("tool_a", {"x": 1})
        assert result.action == LoopAction.STOP


class TestReset:
    def test_reset_clears_history(self):
        guard = ToolLoopGuard()
        for i in range(15):
            guard.check("tool_a", {"x": 1})
            guard.record_result("tool_a", {"x": 1}, "same")
        guard.reset()
        result = guard.check("tool_a", {"x": 1})
        assert result.action == LoopAction.ALLOW
