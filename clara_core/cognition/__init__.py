"""Clara Cognition Pipeline - Event-driven message processing.

This package provides the cognition pipeline that transforms messages into responses:
- Event typing and classification
- Rate-limited routing
- Context evaluation
- Memory integration
- Response generation

The pipeline stages are:
1. Router: Classify events and enforce rate limits
2. Evaluator: Assess complexity and determine response strategy
3. Context Builder: Assemble memories, session, and system prompt
4. Generator: Stream LLM responses with tool handling
5. Reflector: Post-response learning and memory extraction

Usage:
    from clara_core.cognition import (
        CognitionRouter,
        CognitionEvent,
        EventType,
        RouteDecision,
    )

    router = CognitionRouter()
    event = CognitionEvent(type=EventType.MESSAGE, payload={"content": "Hello"})
    decision = router.route(event)
"""

from clara_core.cognition.types import (
    CognitionEvent,
    ContextBundle,
    EvaluationResult,
    EventMetadata,
    EventType,
    QuickContext,
    RejectedEvent,
    ResponseCompleteEvent,
    RouteDecision,
    TextChunkEvent,
    ToolCallEvent,
)

# Import router conditionally to avoid circular import during development
try:
    from clara_core.cognition.router import CognitionRouter
except ImportError:
    CognitionRouter = None  # type: ignore

# Import evaluator
from clara_core.cognition.evaluator import Evaluator, EvaluatorConfig, create_evaluator

__all__ = [
    # Core types
    "CognitionEvent",
    "EventType",
    "EventMetadata",
    "QuickContext",
    # Router
    "CognitionRouter",
    "RouteDecision",
    # Evaluator
    "Evaluator",
    "EvaluatorConfig",
    "create_evaluator",
    # Pipeline types
    "EvaluationResult",
    "ContextBundle",
    # Stream events
    "TextChunkEvent",
    "ToolCallEvent",
    "ResponseCompleteEvent",
    "RejectedEvent",
]
