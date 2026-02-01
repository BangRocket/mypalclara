"""Cognition Pipeline Types - Event and data structures for the cognition pipeline.

This module defines all the types used throughout the cognition pipeline:
- Event types for message classification
- Cognition events with metadata
- Evaluation results
- Context bundles for LLM generation
- Route decisions
- Stream event types
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class EventType(Enum):
    """Classification of incoming events to the cognition pipeline."""

    MESSAGE = "message"  # User message (text, image, etc.)
    TOOL_RESULT = "tool_result"  # Result from a tool execution
    SYSTEM = "system"  # System-generated event (session timeout, etc.)
    SCHEDULED = "scheduled"  # Scheduled task execution


@dataclass
class EventMetadata:
    """Metadata attached to cognition events."""

    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: str = ""  # Channel/platform identifier (e.g., "discord", "telegram")
    rate_limit_key: str = ""  # Key for rate limiting (e.g., request_id)
    user_id: str = ""
    channel_id: str = ""
    request_id: str = ""
    session_id: str = ""

    def __post_init__(self) -> None:
        """Set rate_limit_key from request_id if not provided."""
        if not self.rate_limit_key and self.request_id:
            self.rate_limit_key = self.request_id


@dataclass
class CognitionEvent:
    """An event entering the cognition pipeline.

    This is the primary input type for the pipeline. Events are classified
    by type and carry arbitrary payload data plus metadata for routing.
    """

    type: EventType
    payload: dict[str, Any] = field(default_factory=dict)
    metadata: EventMetadata = field(default_factory=EventMetadata)

    @property
    def content(self) -> str:
        """Extract text content from payload, if present."""
        return self.payload.get("content", "")

    @property
    def request_id(self) -> str:
        """Shortcut to metadata.request_id."""
        return self.metadata.request_id

    @property
    def user_id(self) -> str:
        """Shortcut to metadata.user_id."""
        return self.metadata.user_id


@dataclass
class QuickContext:
    """Minimal context for fast evaluation decisions.

    Extracted without full memory fetch to enable quick pattern matching.
    Used by the Evaluator to make fast-path decisions without expensive
    context building.
    """

    recent_message_count: int = 0  # Messages in current session
    is_dm: bool = False  # Direct message (always respond)
    has_mention: bool = False  # Bot was mentioned
    channel_activity_level: str = "normal"  # "quiet", "normal", "active"
    is_reply_chain: bool = False  # Part of ongoing conversation
    last_response_time: float | None = None  # Unix timestamp of last bot response


@dataclass
class EvaluationResult:
    """Result of evaluating a cognition event.

    Produced by the evaluator to guide response generation.
    """

    should_respond: bool = True  # Whether to generate a response
    complexity: str = "low"  # "low", "medium", "high"
    suggested_tier: str = "mid"  # Model tier: "low", "mid", "high"
    tone: str = "neutral"  # Detected emotional tone
    reasoning: str = ""  # Explanation for the evaluation

    # Quick context for fast-path decisions
    is_greeting: bool = False
    is_question: bool = False
    requires_tools: bool = False
    estimated_tokens: int = 0


@dataclass
class ContextBundle:
    """Complete context assembled for LLM generation.

    Contains everything needed to generate a response.
    """

    # Memory context
    memories: list[str] = field(default_factory=list)  # Relevant mem0 memories
    project_memories: list[str] = field(default_factory=list)  # Project-specific memories

    # Session context
    session_id: str = ""
    session_messages: list[dict[str, Any]] = field(default_factory=list)
    previous_session_snapshot: list[dict[str, Any]] = field(default_factory=list)

    # User context
    user_id: str = ""
    user_name: str = ""
    emotional_state: str = "neutral"

    # System configuration
    system_prompt: str = ""
    persona: str = ""

    # Assembled messages for LLM
    messages: list[dict[str, Any]] = field(default_factory=list)

    # Channel context
    channel_id: str = ""
    channel_type: str = ""  # "dm", "group", "server"


class RouteClassification(Enum):
    """How the router classified an event."""

    PROCESS = "process"  # Normal processing
    RATE_LIMITED = "rate_limited"  # Rejected due to rate limit
    SKIP = "skip"  # Should be skipped (e.g., bot's own message)
    DEFER = "defer"  # Defer to later (e.g., batch with other messages)


@dataclass
class RouteDecision:
    """Decision made by the router for an event.

    Determines how the event should proceed through the pipeline.
    """

    classification: RouteClassification
    event: CognitionEvent
    reason: str = ""

    # Rate limit info
    is_rate_limited: bool = False
    rate_limit_type: str = ""  # "per_request" or "per_minute"
    current_count: int = 0
    max_count: int = 0

    # Quick context extracted by router
    quick_context: dict[str, Any] = field(default_factory=dict)

    @property
    def should_process(self) -> bool:
        """Whether the event should continue through the pipeline."""
        return self.classification == RouteClassification.PROCESS


# --- Stream Event Types ---
# These are yielded by the generator during response streaming


@dataclass
class TextChunkEvent:
    """A chunk of text being streamed from the LLM."""

    text: str
    is_final: bool = False  # True for the last chunk
    request_id: str = ""


@dataclass
class ToolCallEvent:
    """A tool call detected in the LLM response."""

    tool_name: str
    tool_args: dict[str, Any] = field(default_factory=dict)
    call_id: str = ""  # Unique ID for this tool call
    request_id: str = ""

    # Execution status (filled after execution)
    executed: bool = False
    result: Any = None
    error: str | None = None


@dataclass
class RejectedEvent:
    """An event that was rejected by the pipeline."""

    reason: str
    event: CognitionEvent
    rate_limit_info: dict[str, Any] = field(default_factory=dict)
    request_id: str = ""
