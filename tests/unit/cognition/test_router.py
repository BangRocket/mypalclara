"""Tests for cognition router rate limiting."""

import time
from unittest.mock import patch

import pytest

from clara_core.cognition.router import CognitionRouter, RateLimitConfig
from clara_core.cognition.types import (
    CognitionEvent,
    EventMetadata,
    EventType,
    RouteClassification,
)


@pytest.fixture
def router():
    """Create a fresh router for each test."""
    return CognitionRouter()


@pytest.fixture
def router_low_limits():
    """Create a router with low limits for testing."""
    config = RateLimitConfig(
        max_tool_calls_per_request=3,
        max_tool_calls_per_minute=5,
        window_seconds=60.0,
    )
    return CognitionRouter(config=config)


def make_tool_result_event(request_id: str = "test-request") -> CognitionEvent:
    """Create a tool result event for testing."""
    return CognitionEvent(
        type=EventType.TOOL_RESULT,
        payload={"result": "test result"},
        metadata=EventMetadata(request_id=request_id),
    )


def make_message_event(content: str = "Hello") -> CognitionEvent:
    """Create a message event for testing."""
    return CognitionEvent(
        type=EventType.MESSAGE,
        payload={"content": content},
        metadata=EventMetadata(request_id="test-request"),
    )


class TestRouterBasics:
    """Basic router functionality tests."""

    def test_message_event_passes_through(self, router):
        """MESSAGE events should always pass through."""
        event = make_message_event("Hello")
        decision = router.route(event)

        assert decision.classification == RouteClassification.PROCESS
        assert decision.should_process is True
        assert decision.is_rate_limited is False

    def test_tool_result_within_limits(self, router):
        """Tool results within limits should pass through."""
        event = make_tool_result_event()
        decision = router.route(event)

        assert decision.classification == RouteClassification.PROCESS
        assert decision.should_process is True
        assert decision.is_rate_limited is False

    def test_quick_context_extraction(self, router):
        """Router should extract quick context from messages."""
        event = make_message_event("Hello, how are you?")
        decision = router.route(event)

        assert "has_content" in decision.quick_context
        assert "is_greeting" in decision.quick_context
        assert "is_question" in decision.quick_context
        assert decision.quick_context["is_question"] is True

    def test_quick_context_greeting_detection(self, router):
        """Router should detect greetings."""
        event = make_message_event("hello")
        decision = router.route(event)

        assert decision.quick_context["is_greeting"] is True

    def test_quick_context_command_detection(self, router):
        """Router should detect commands."""
        event = make_message_event("!help")
        decision = router.route(event)

        assert decision.quick_context["is_command"] is True


class TestPerRequestLimit:
    """Tests for per-request rate limiting."""

    def test_per_request_limit_triggers_after_max(self, router_low_limits):
        """Per-request limit should trigger after 3 tool results."""
        request_id = "test-request-1"

        # First 3 should pass
        for i in range(3):
            event = make_tool_result_event(request_id)
            decision = router_low_limits.route(event)
            assert decision.should_process is True, f"Call {i+1} should pass"

        # 4th should be rejected
        event = make_tool_result_event(request_id)
        decision = router_low_limits.route(event)

        assert decision.classification == RouteClassification.RATE_LIMITED
        assert decision.should_process is False
        assert decision.is_rate_limited is True
        assert decision.rate_limit_type == "per_request"
        assert decision.current_count == 4
        assert decision.max_count == 3

    def test_per_request_limit_separate_requests(self, router_low_limits):
        """Different request IDs should have separate counters."""
        # Exhaust limit for request 1
        for i in range(4):
            event = make_tool_result_event("request-1")
            router_low_limits.route(event)

        # Request 2 should still work
        event = make_tool_result_event("request-2")
        decision = router_low_limits.route(event)

        assert decision.should_process is True
        assert decision.is_rate_limited is False


class TestPerMinuteLimit:
    """Tests for per-minute (sliding window) rate limiting."""

    def test_per_minute_limit_triggers_after_max(self, router_low_limits):
        """Per-minute limit should trigger after 5 total tool results."""
        # Use different request IDs to avoid per-request limit
        for i in range(5):
            event = make_tool_result_event(f"request-{i}")
            decision = router_low_limits.route(event)
            assert decision.should_process is True, f"Call {i+1} should pass"

        # 6th should be rejected (even with new request ID)
        event = make_tool_result_event("request-6")
        decision = router_low_limits.route(event)

        assert decision.classification == RouteClassification.RATE_LIMITED
        assert decision.should_process is False
        assert decision.is_rate_limited is True
        assert decision.rate_limit_type == "per_minute"
        assert decision.current_count == 6
        assert decision.max_count == 5

    def test_per_minute_limit_resets_after_window(self):
        """Per-minute limit should reset after window expires."""
        config = RateLimitConfig(
            max_tool_calls_per_request=10,
            max_tool_calls_per_minute=2,
            window_seconds=0.1,  # 100ms window for fast testing
        )
        router = CognitionRouter(config=config)

        # Exhaust the limit
        for i in range(2):
            event = make_tool_result_event(f"request-{i}")
            router.route(event)

        # Should be limited now
        event = make_tool_result_event("request-3")
        decision = router.route(event)
        assert decision.is_rate_limited is True

        # Wait for window to expire
        time.sleep(0.15)

        # Should work again
        event = make_tool_result_event("request-4")
        decision = router.route(event)
        assert decision.should_process is True
        assert decision.is_rate_limited is False


class TestMessagesBypassLimits:
    """Tests ensuring MESSAGE events bypass all rate limits."""

    def test_message_bypasses_per_request_limit(self, router_low_limits):
        """MESSAGE events should bypass per-request limits."""
        request_id = "test-request"

        # Exhaust tool result limit
        for i in range(4):
            event = make_tool_result_event(request_id)
            router_low_limits.route(event)

        # MESSAGE with same request ID should still work
        message_event = CognitionEvent(
            type=EventType.MESSAGE,
            payload={"content": "Hello"},
            metadata=EventMetadata(request_id=request_id),
        )
        decision = router_low_limits.route(message_event)

        assert decision.should_process is True
        assert decision.is_rate_limited is False

    def test_message_bypasses_per_minute_limit(self, router_low_limits):
        """MESSAGE events should bypass per-minute limits."""
        # Exhaust per-minute limit
        for i in range(6):
            event = make_tool_result_event(f"request-{i}")
            router_low_limits.route(event)

        # MESSAGE should still work
        message_event = make_message_event("Hello")
        decision = router_low_limits.route(message_event)

        assert decision.should_process is True
        assert decision.is_rate_limited is False

    def test_system_events_bypass_limits(self, router_low_limits):
        """SYSTEM events should bypass rate limits."""
        # Exhaust limits
        for i in range(6):
            event = make_tool_result_event(f"request-{i}")
            router_low_limits.route(event)

        # SYSTEM event should work
        system_event = CognitionEvent(
            type=EventType.SYSTEM,
            payload={"action": "session_timeout"},
            metadata=EventMetadata(request_id="test"),
        )
        decision = router_low_limits.route(system_event)

        assert decision.should_process is True
        assert decision.is_rate_limited is False


class TestResetFunctions:
    """Tests for rate limit reset functions."""

    def test_reset_request_clears_single_counter(self, router_low_limits):
        """reset_request should clear only the specified request counter."""
        # Add some counts
        for i in range(3):
            event = make_tool_result_event("request-1")
            router_low_limits.route(event)

        event = make_tool_result_event("request-2")
        router_low_limits.route(event)

        # Reset request-1
        router_low_limits.reset_request("request-1")

        # request-1 should work again
        event = make_tool_result_event("request-1")
        decision = router_low_limits.route(event)
        assert decision.should_process is True

    def test_reset_all_clears_everything(self, router_low_limits):
        """reset_all should clear all rate limit state."""
        # Exhaust both limits
        for i in range(6):
            event = make_tool_result_event(f"request-{i}")
            router_low_limits.route(event)

        # Verify limited
        event = make_tool_result_event("new-request")
        decision = router_low_limits.route(event)
        assert decision.is_rate_limited is True

        # Reset all
        router_low_limits.reset_all()

        # Should work again
        event = make_tool_result_event("another-request")
        decision = router_low_limits.route(event)
        assert decision.should_process is True
        assert decision.is_rate_limited is False

    def test_get_stats(self, router_low_limits):
        """get_stats should return current state."""
        # Add some activity
        for i in range(3):
            event = make_tool_result_event(f"request-{i}")
            router_low_limits.route(event)

        stats = router_low_limits.get_stats()

        assert stats["active_requests"] == 3
        assert stats["tool_calls_in_window"] == 3
        assert stats["config"]["max_per_request"] == 3
        assert stats["config"]["max_per_minute"] == 5


class TestDefaultLimits:
    """Tests for default rate limit values."""

    def test_default_per_request_limit_is_10(self, router):
        """Default per-request limit should be 10."""
        for i in range(10):
            event = make_tool_result_event("test-request")
            decision = router.route(event)
            assert decision.should_process is True, f"Call {i+1} should pass"

        # 11th should be rejected
        event = make_tool_result_event("test-request")
        decision = router.route(event)
        assert decision.is_rate_limited is True
        assert decision.max_count == 10

    def test_default_per_minute_limit_is_20(self, router):
        """Default per-minute limit should be 20."""
        # Use different request IDs to avoid per-request limit
        for i in range(20):
            event = make_tool_result_event(f"request-{i}")
            decision = router.route(event)
            assert decision.should_process is True, f"Call {i+1} should pass"

        # 21st should be rejected
        event = make_tool_result_event("request-21")
        decision = router.route(event)
        assert decision.is_rate_limited is True
        assert decision.max_count == 20
