"""Cognition Router - Event classification and rate limiting.

This module provides the CognitionRouter that:
- Classifies incoming events by type
- Enforces rate limits to prevent runaway tool loops
- Extracts quick context for fast-path decisions
- Routes events to appropriate pipeline stages
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

from clara_core.cognition.types import (
    CognitionEvent,
    EventType,
    RouteClassification,
    RouteDecision,
)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    max_tool_calls_per_request: int = 10  # Per single request
    max_tool_calls_per_minute: int = 20  # Sliding window
    window_seconds: float = 60.0  # Time window for per-minute limit


@dataclass
class RateLimitState:
    """Tracks rate limit state for a key."""

    request_counts: dict[str, int] = field(default_factory=dict)
    minute_timestamps: list[float] = field(default_factory=list)


class CognitionRouter:
    """Routes cognition events with rate limiting.

    The router is the entry point to the cognition pipeline. It:
    1. Classifies events by type (MESSAGE, TOOL_RESULT, SYSTEM, SCHEDULED)
    2. Enforces rate limits on tool results to prevent runaway loops
    3. Extracts quick context for fast-path decisions
    4. Returns a RouteDecision indicating how to proceed

    Rate Limiting:
    - Per-request limit: MAX_TOOL_CALLS_PER_REQUEST (default: 10)
      Prevents a single request from triggering too many tool calls.

    - Per-minute limit: MAX_TOOL_CALLS_PER_MINUTE (default: 20)
      Prevents sustained high tool usage across requests.

    Only TOOL_RESULT events are subject to rate limiting.
    MESSAGE, SYSTEM, and SCHEDULED events always pass through.
    """

    def __init__(self, config: RateLimitConfig | None = None) -> None:
        """Initialize the router.

        Args:
            config: Rate limit configuration. Uses defaults if not provided.
        """
        self.config = config or RateLimitConfig()
        self._state = RateLimitState()
        self._lock = Lock()

    def route(self, event: CognitionEvent) -> RouteDecision:
        """Route an event through rate limiting and classification.

        Args:
            event: The cognition event to route.

        Returns:
            RouteDecision indicating how to handle the event.
        """
        # Non-tool-result events bypass rate limiting
        if event.type != EventType.TOOL_RESULT:
            return RouteDecision(
                classification=RouteClassification.PROCESS,
                event=event,
                quick_context=self._extract_quick_context(event),
            )

        # Check rate limits for tool results
        rate_limit_result = self._check_rate_limits(event)
        if rate_limit_result is not None:
            return rate_limit_result

        # Tool result within limits - allow processing
        return RouteDecision(
            classification=RouteClassification.PROCESS,
            event=event,
            quick_context=self._extract_quick_context(event),
        )

    def _check_rate_limits(self, event: CognitionEvent) -> RouteDecision | None:
        """Check rate limits for a tool result event.

        Returns None if within limits, or a rate-limited RouteDecision if exceeded.
        """
        with self._lock:
            now = time.time()
            request_id = event.metadata.rate_limit_key or event.metadata.request_id

            # Check per-request limit
            current_request_count = self._state.request_counts.get(request_id, 0) + 1
            if current_request_count > self.config.max_tool_calls_per_request:
                return RouteDecision(
                    classification=RouteClassification.RATE_LIMITED,
                    event=event,
                    reason=f"Per-request tool call limit exceeded ({self.config.max_tool_calls_per_request})",
                    is_rate_limited=True,
                    rate_limit_type="per_request",
                    current_count=current_request_count,
                    max_count=self.config.max_tool_calls_per_request,
                )

            # Clean up old timestamps outside the window
            cutoff = now - self.config.window_seconds
            self._state.minute_timestamps = [
                ts for ts in self._state.minute_timestamps if ts > cutoff
            ]

            # Check per-minute limit
            current_minute_count = len(self._state.minute_timestamps) + 1
            if current_minute_count > self.config.max_tool_calls_per_minute:
                return RouteDecision(
                    classification=RouteClassification.RATE_LIMITED,
                    event=event,
                    reason=f"Per-minute tool call limit exceeded ({self.config.max_tool_calls_per_minute})",
                    is_rate_limited=True,
                    rate_limit_type="per_minute",
                    current_count=current_minute_count,
                    max_count=self.config.max_tool_calls_per_minute,
                )

            # Within limits - record this call
            self._state.request_counts[request_id] = current_request_count
            self._state.minute_timestamps.append(now)

            return None

    def _extract_quick_context(self, event: CognitionEvent) -> dict[str, Any]:
        """Extract quick context for fast-path decisions.

        This provides lightweight analysis without full LLM evaluation.
        """
        content = event.content.lower().strip() if event.content else ""

        # Quick heuristics for common patterns
        quick_context: dict[str, Any] = {
            "has_content": bool(content),
            "content_length": len(content),
            "is_short": len(content) < 50,
        }

        # Greeting detection
        greetings = {"hi", "hello", "hey", "good morning", "good afternoon", "good evening"}
        quick_context["is_greeting"] = any(
            content.startswith(g) or content == g for g in greetings
        )

        # Question detection
        quick_context["is_question"] = content.endswith("?") or content.startswith(
            ("what", "why", "how", "when", "where", "who", "which", "can", "could", "would", "should", "is", "are", "do", "does")
        )

        # Command detection (starts with !)
        quick_context["is_command"] = content.startswith("!")

        # Tool mention detection
        tool_keywords = {"run", "execute", "search", "calculate", "look up", "find", "create", "save", "send"}
        quick_context["may_need_tools"] = any(kw in content for kw in tool_keywords)

        return quick_context

    def reset_request(self, request_id: str) -> None:
        """Reset rate limit counters for a specific request.

        Call this when a request completes to clean up state.
        """
        with self._lock:
            self._state.request_counts.pop(request_id, None)

    def reset_all(self) -> None:
        """Reset all rate limit state.

        Useful for testing or when restarting the pipeline.
        """
        with self._lock:
            self._state = RateLimitState()

    def get_stats(self) -> dict[str, Any]:
        """Get current rate limit statistics."""
        with self._lock:
            now = time.time()
            cutoff = now - self.config.window_seconds

            # Count active timestamps in window
            active_count = sum(
                1 for ts in self._state.minute_timestamps if ts > cutoff
            )

            return {
                "active_requests": len(self._state.request_counts),
                "tool_calls_in_window": active_count,
                "window_seconds": self.config.window_seconds,
                "config": {
                    "max_per_request": self.config.max_tool_calls_per_request,
                    "max_per_minute": self.config.max_tool_calls_per_minute,
                },
            }
