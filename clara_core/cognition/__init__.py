"""Clara Cognition Pipeline - Event-driven message processing.

This package provides the cognition pipeline that transforms messages into responses
through five coordinated stages:

    ROUTER -> EVALUATE -> CONTEXTUALIZE -> RESPOND -> REFLECT

Module Structure:
    types.py        - Event types, metadata, and data structures
    router.py       - Rate-limited event classification
    evaluator.py    - Fast message triage and complexity assessment
    contextualize.py - Memory and session context assembly
    respond.py      - LLM response generation with tool detection
    reflect.py      - Fire-and-forget memory storage
    pipeline.py     - Main orchestrator coordinating all stages

Pipeline Stages:
    1. ROUTER: Classify events (MESSAGE, TOOL_RESULT, SYSTEM, SCHEDULED)
       and enforce rate limits (10 per-request, 20 per-minute tool calls)

    2. EVALUATE: Pattern matching for fast-path decisions, LLM evaluation
       for nuanced cases, complexity and tier assessment

    3. CONTEXTUALIZE: Fetch memories from mem0, load session context,
       assemble complete ContextBundle for generation

    4. RESPOND: Call LLM with context, stream text chunks, detect tool
       calls and yield as ToolCallEvent (NOT executed internally)

    5. REFLECT: Store exchange to memory asynchronously (fire-and-forget),
       track interaction patterns

Main Entry Point:
    CognitionPipeline - The main orchestrator that coordinates all stages

    Usage:
        from clara_core.cognition import CognitionPipeline, CognitionEvent, EventType

        pipeline = CognitionPipeline()
        event = CognitionEvent(type=EventType.MESSAGE, payload={"content": "Hello"})

        async for response in pipeline.process(event, tools=my_tools):
            if isinstance(response, TextChunkEvent):
                # Stream to user
                pass
            elif isinstance(response, ToolCallEvent):
                # Execute tool externally, re-enter pipeline with result
                pass
            elif isinstance(response, ResponseCompleteEvent):
                # Done
                pass

Stage Components (for testing/extension):
    - CognitionRouter: Rate-limited routing
    - Evaluator: Message triage
    - Contextualizer: Context assembly
    - Responder: LLM generation
    - Reflector: Memory storage
"""

# Core types
from clara_core.cognition.types import (
    CognitionEvent,
    ContextBundle,
    EvaluationResult,
    EventMetadata,
    EventType,
    QuickContext,
    RejectedEvent,
    ResponseCompleteEvent,
    RouteClassification,
    RouteDecision,
    TextChunkEvent,
    ToolCallEvent,
)

# Router
from clara_core.cognition.router import CognitionRouter, RateLimitConfig

# Evaluator
from clara_core.cognition.evaluator import Evaluator, EvaluatorConfig, create_evaluator

# Contextualizer
from clara_core.cognition.contextualize import (
    Contextualizer,
    ContextualizerConfig,
    SessionInfo,
    create_contextualizer,
)

# Responder
from clara_core.cognition.respond import (
    Responder,
    ResponderConfig,
    create_responder,
)

# Reflector
from clara_core.cognition.reflect import (
    Reflector,
    ReflectorConfig,
    ReflectionMetadata,
    create_reflector,
)

# Pipeline orchestrator (main entry point)
from clara_core.cognition.pipeline import (
    CognitionPipeline,
    PipelineConfig,
    PipelineEvent,
    create_pipeline,
)


__all__ = [
    # === Main Entry Point ===
    "CognitionPipeline",
    "PipelineConfig",
    "PipelineEvent",
    "create_pipeline",
    # === Core Types ===
    "CognitionEvent",
    "EventType",
    "EventMetadata",
    "QuickContext",
    # === Stage: Router ===
    "CognitionRouter",
    "RateLimitConfig",
    "RouteDecision",
    "RouteClassification",
    # === Stage: Evaluator ===
    "Evaluator",
    "EvaluatorConfig",
    "EvaluationResult",
    "create_evaluator",
    # === Stage: Contextualizer ===
    "Contextualizer",
    "ContextualizerConfig",
    "ContextBundle",
    "SessionInfo",
    "create_contextualizer",
    # === Stage: Responder ===
    "Responder",
    "ResponderConfig",
    "create_responder",
    # === Stage: Reflector ===
    "Reflector",
    "ReflectorConfig",
    "ReflectionMetadata",
    "create_reflector",
    # === Stream Events ===
    "TextChunkEvent",
    "ToolCallEvent",
    "ResponseCompleteEvent",
    "RejectedEvent",
]
