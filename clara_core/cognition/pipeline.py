"""Cognition Pipeline - Main orchestrator for message processing.

This module provides the CognitionPipeline that coordinates all stages:
ROUTER -> EVALUATE -> CONTEXTUALIZE -> RESPOND -> REFLECT

The pipeline:
1. Routes events through rate limiting
2. Evaluates complexity and response strategy
3. Assembles full context from memory and session
4. Generates responses with tool call detection
5. Stores exchanges to memory (fire-and-forget)

CRITICAL: Tool calls are yielded as events, NOT executed internally.
The caller is responsible for:
1. Executing tools externally
2. Creating CognitionEvent(type=TOOL_RESULT) with result
3. Re-entering the pipeline via process(tool_result_event)

This design enables rate limiting at the pipeline level (10 per-request,
20 per-minute) to prevent runaway tool loops.

Tool Result Re-entry Pattern:
    When process() yields a ToolCallEvent, the caller should:

    1. Execute the tool externally (outside the pipeline)
    2. Create a new CognitionEvent with the result:
       ```python
       tool_result_event = CognitionEvent(
           type=EventType.TOOL_RESULT,
           payload={
               "result": tool_result,
               "tool_name": tool_call_event.tool_name,
               "call_id": tool_call_event.call_id,
           },
           metadata=EventMetadata(
               request_id=original_event.request_id,  # IMPORTANT: Same request_id
               user_id=original_event.metadata.user_id,
               channel_id=original_event.metadata.channel_id,
           ),
       )
       ```
    3. Re-enter the pipeline: `async for event in pipeline.process(tool_result_event, tools)`
    4. The router will rate-limit tool results (10 per-request, 20 per-minute)
    5. If rate-limited, a RejectedEvent is yielded instead of continuing
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, AsyncIterator

from clara_core.cognition.contextualize import Contextualizer, ContextualizerConfig
from clara_core.cognition.evaluator import Evaluator, EvaluatorConfig
from clara_core.cognition.reflect import Reflector, ReflectorConfig
from clara_core.cognition.respond import Responder, ResponderConfig
from clara_core.cognition.router import CognitionRouter, RateLimitConfig
from clara_core.cognition.types import (
    CognitionEvent,
    ContextBundle,
    EvaluationResult,
    EventType,
    QuickContext,
    RejectedEvent,
    ResponseCompleteEvent,
    RouteClassification,
    TextChunkEvent,
    ToolCallEvent,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from clara_core.memory import MemoryManager

logger = logging.getLogger(__name__)


# Type alias for pipeline events
PipelineEvent = TextChunkEvent | ToolCallEvent | ResponseCompleteEvent | RejectedEvent


@dataclass
class PipelineConfig:
    """Configuration for the CognitionPipeline."""

    # Stage configurations
    router_config: RateLimitConfig = field(default_factory=RateLimitConfig)
    evaluator_config: EvaluatorConfig = field(default_factory=EvaluatorConfig)
    contextualizer_config: ContextualizerConfig = field(
        default_factory=ContextualizerConfig
    )
    responder_config: ResponderConfig = field(default_factory=ResponderConfig)
    reflector_config: ReflectorConfig = field(default_factory=ReflectorConfig)


class CognitionPipeline:
    """Main orchestrator for the cognition pipeline.

    Coordinates all stages:
    1. ROUTER: Classify events and enforce rate limits
    2. EVALUATE: Assess complexity and determine response strategy
    3. CONTEXTUALIZE: Assemble memories, session, and system prompt
    4. RESPOND: Generate LLM response with tool detection
    5. REFLECT: Store exchange to memory (fire-and-forget)

    Usage:
        pipeline = CognitionPipeline()

        # Process a message
        async for event in pipeline.process(cognition_event, tools):
            if isinstance(event, TextChunkEvent):
                # Stream text to user
                pass
            elif isinstance(event, ToolCallEvent):
                # Execute tool externally
                result = execute_tool(event.tool_name, event.tool_args)
                # Re-enter pipeline with result
                tool_result_event = CognitionEvent(
                    type=EventType.TOOL_RESULT,
                    payload={"result": result, "tool_name": event.tool_name},
                    metadata=original_event.metadata,
                )
                async for e in pipeline.process(tool_result_event, tools):
                    # Handle continuation...
                    pass
            elif isinstance(event, RejectedEvent):
                # Handle rate limit rejection
                pass
            elif isinstance(event, ResponseCompleteEvent):
                # Response complete
                pass

    Attributes:
        config: Pipeline configuration
        router: Rate-limited event router
        evaluator: Message triage and complexity assessment
        contextualizer: Memory and session context assembly
        responder: LLM response generation
        reflector: Fire-and-forget memory storage
    """

    def __init__(
        self,
        config: PipelineConfig | None = None,
        memory_manager: "MemoryManager | None" = None,
        llm_fn: "Callable | None" = None,
    ) -> None:
        """Initialize the cognition pipeline.

        Args:
            config: Optional pipeline configuration
            memory_manager: Optional MemoryManager instance
            llm_fn: Optional LLM function for evaluator
        """
        self.config = config or PipelineConfig()

        # Initialize all stage components
        self.router = CognitionRouter(config=self.config.router_config)
        self.evaluator = Evaluator(
            config=self.config.evaluator_config, llm_fn=llm_fn
        )
        self.contextualizer = Contextualizer(
            config=self.config.contextualizer_config,
            memory_manager=memory_manager,
        )
        self.responder = Responder(config=self.config.responder_config)
        self.reflector = Reflector(
            config=self.config.reflector_config,
            memory_manager=memory_manager,
        )

        # Track current context for reflection
        self._current_context: ContextBundle | None = None
        self._current_event: CognitionEvent | None = None

    async def process(
        self,
        event: CognitionEvent,
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[PipelineEvent]:
        """Process an event through the cognition pipeline.

        This is an async generator that yields:
        - TextChunkEvent: For streaming text
        - ToolCallEvent: For tool calls (NOT executed - caller handles)
        - RejectedEvent: For rate-limited events
        - ResponseCompleteEvent: When generation is complete

        CRITICAL: Tool calls are yielded as ToolCallEvent. The caller must:
        1. Execute the tool externally
        2. Create a new CognitionEvent with type=TOOL_RESULT
        3. Call process() again with the tool result event

        The router rate-limits TOOL_RESULT events to prevent runaway loops.

        Args:
            event: The cognition event to process
            tools: Optional list of tool definitions

        Yields:
            Pipeline events (text chunks, tool calls, rejections, completion)
        """
        request_id = event.request_id

        # Stage 1: ROUTER - Classify and rate limit
        route_decision = self.router.route(event)

        if route_decision.classification == RouteClassification.RATE_LIMITED:
            logger.warning(
                "Event rate-limited: %s (request=%s, type=%s, count=%d/%d)",
                route_decision.reason,
                request_id,
                route_decision.rate_limit_type,
                route_decision.current_count,
                route_decision.max_count,
            )
            yield RejectedEvent(
                reason=route_decision.reason,
                event=event,
                rate_limit_info={
                    "type": route_decision.rate_limit_type,
                    "current": route_decision.current_count,
                    "max": route_decision.max_count,
                },
                request_id=request_id,
            )
            return

        if not route_decision.should_process:
            logger.debug("Event skipped: %s", route_decision.reason)
            yield RejectedEvent(
                reason=route_decision.reason,
                event=event,
                request_id=request_id,
            )
            return

        # Stage 2: EVALUATE - Determine response strategy
        quick_context = self._build_quick_context(route_decision.quick_context)
        evaluation = await self.evaluator.evaluate(event, quick_context)

        if not evaluation.should_respond:
            logger.debug(
                "Evaluation: no response needed (%s)",
                evaluation.reasoning,
            )
            yield RejectedEvent(
                reason=evaluation.reasoning,
                event=event,
                request_id=request_id,
            )
            return

        logger.debug(
            "Evaluation: %s complexity, tier=%s (%s)",
            evaluation.complexity,
            evaluation.suggested_tier,
            evaluation.reasoning,
        )

        # Stage 3: CONTEXTUALIZE - Build full context
        context = await self.contextualizer.contextualize(event, evaluation)

        # Store for reflection
        self._current_context = context
        self._current_event = event

        logger.debug(
            "Context built: %d memories, %d session msgs",
            len(context.memories),
            len(context.session_messages),
        )

        # Stage 4: RESPOND - Generate LLM response
        response_complete: ResponseCompleteEvent | None = None

        async for response_event in self.responder.generate(
            context=context,
            tools=tools,
            evaluation=evaluation,
            request_id=request_id,
        ):
            if isinstance(response_event, ResponseCompleteEvent):
                response_complete = response_event

            yield response_event

        # Stage 5: REFLECT - Store to memory (fire-and-forget)
        if response_complete is not None:
            await self.reflector.reflect(event, context, response_complete)

    def _build_quick_context(
        self,
        router_context: dict[str, Any],
    ) -> QuickContext:
        """Build QuickContext from router's extracted context.

        Args:
            router_context: Context dict from router

        Returns:
            QuickContext for evaluator
        """
        return QuickContext(
            recent_message_count=router_context.get("content_length", 0),
            is_dm=router_context.get("is_dm", False),
            has_mention=router_context.get("has_mention", False),
            is_reply_chain=router_context.get("is_reply_chain", False),
        )

    def reset_request(self, request_id: str) -> None:
        """Reset rate limit counters for a specific request.

        Call this when a request completes to clean up state.

        Args:
            request_id: The request ID to reset
        """
        self.router.reset_request(request_id)

    def reset_all(self) -> None:
        """Reset all pipeline state.

        Useful for testing or when restarting the pipeline.
        """
        self.router.reset_all()
        self._current_context = None
        self._current_event = None

    def get_stats(self) -> dict[str, Any]:
        """Get current pipeline statistics.

        Returns:
            Dict with router stats and other pipeline info
        """
        return {
            "router": self.router.get_stats(),
            "has_current_context": self._current_context is not None,
        }


def create_pipeline(
    memory_manager: "MemoryManager | None" = None,
    max_tool_calls_per_request: int = 10,
    max_tool_calls_per_minute: int = 20,
) -> CognitionPipeline:
    """Factory function to create a configured CognitionPipeline.

    Args:
        memory_manager: Optional MemoryManager instance
        max_tool_calls_per_request: Per-request tool call limit
        max_tool_calls_per_minute: Per-minute tool call limit

    Returns:
        Configured CognitionPipeline instance
    """
    config = PipelineConfig(
        router_config=RateLimitConfig(
            max_tool_calls_per_request=max_tool_calls_per_request,
            max_tool_calls_per_minute=max_tool_calls_per_minute,
        ),
    )
    return CognitionPipeline(config=config, memory_manager=memory_manager)
