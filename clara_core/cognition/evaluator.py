"""Cognition Evaluator - Fast message triage and complexity assessment.

This module implements the EVALUATE stage of the cognition pipeline:
- Pattern matching for obvious ignore/respond cases (no LLM call)
- LLM-based evaluation for nuanced decisions (low-tier model)
- Complexity assessment and model tier suggestions
- Tone detection for response calibration

The evaluator acts as a fast gateway before expensive context building,
reducing costs by quickly triaging messages that don't need full processing.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from clara_core.cognition.types import CognitionEvent, EvaluationResult, EventType

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


@dataclass
class QuickContext:
    """Minimal context for fast evaluation decisions.

    Extracted without full memory fetch to enable quick pattern matching.
    """

    recent_message_count: int = 0  # Messages in current session
    is_dm: bool = False  # Direct message (always respond)
    has_mention: bool = False  # Bot was mentioned
    channel_activity_level: str = "normal"  # "quiet", "normal", "active"
    is_reply_chain: bool = False  # Part of ongoing conversation
    last_response_time: float | None = None  # Unix timestamp


@dataclass
class EvaluatorConfig:
    """Configuration for the Evaluator."""

    # Bot identity patterns
    bot_user_ids: set[str] = field(default_factory=set)
    mention_patterns: list[str] = field(default_factory=list)  # Regex patterns for mentions
    command_prefix: str = "!"  # Command prefix that triggers response

    # Skip patterns (regex)
    skip_patterns: list[str] = field(
        default_factory=lambda: [
            r"^\[.*joined.*\]$",  # Join messages
            r"^\[.*left.*\]$",  # Leave messages
            r"^<System>",  # System messages
        ]
    )

    # LLM evaluation settings
    use_llm_evaluation: bool = True  # Whether to use LLM for unclear cases
    llm_timeout: float = 2.0  # Max time for LLM evaluation


class Evaluator:
    """Evaluates messages to determine response strategy.

    The evaluator has three decision paths:
    1. Fast-path IGNORE: Bot's own messages, system notifications, empty
    2. Fast-path RESPOND: Direct mentions, DMs, command prefix
    3. LLM evaluation: All other cases (when enabled)

    Attributes:
        config: Evaluator configuration
        _llm_fn: Optional async LLM function for nuanced evaluation
    """

    def __init__(
        self,
        config: EvaluatorConfig | None = None,
        llm_fn: Callable | None = None,
    ) -> None:
        """Initialize the evaluator.

        Args:
            config: Optional configuration, uses defaults if not provided
            llm_fn: Optional async function for LLM evaluation.
                    Signature: async (messages: list[dict]) -> str
                    If not provided, uses clara_core.llm.get_quick_llm_response
        """
        self.config = config or EvaluatorConfig()
        self._llm_fn = llm_fn

        # Compile regex patterns for performance
        self._skip_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.config.skip_patterns
        ]
        self._mention_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.config.mention_patterns
        ]

    async def evaluate(
        self,
        event: CognitionEvent,
        quick_context: QuickContext | None = None,
    ) -> EvaluationResult:
        """Evaluate an event and determine response strategy.

        Args:
            event: The cognition event to evaluate
            quick_context: Optional pre-extracted quick context

        Returns:
            EvaluationResult with response decision and metadata
        """
        start_time = time.monotonic()
        quick_context = quick_context or QuickContext()

        # Non-message events are handled specially
        if event.type != EventType.MESSAGE:
            return self._evaluate_non_message(event)

        content = event.content.strip()
        user_id = event.user_id

        # Fast-path 1: Obvious IGNORE cases
        ignore_result = self._is_obvious_ignore(content, user_id, quick_context)
        if ignore_result is not None:
            logger.debug(
                "Fast-path IGNORE: %s (%.3fs)",
                ignore_result.reasoning,
                time.monotonic() - start_time,
            )
            return ignore_result

        # Fast-path 2: Obvious RESPOND cases
        respond_result = self._is_obvious_respond(content, quick_context)
        if respond_result is not None:
            logger.debug(
                "Fast-path RESPOND: %s (%.3fs)",
                respond_result.reasoning,
                time.monotonic() - start_time,
            )
            return respond_result

        # LLM evaluation for nuanced cases
        if self.config.use_llm_evaluation:
            try:
                result = await self._llm_evaluate(content, quick_context)
                logger.debug(
                    "LLM evaluation: should_respond=%s, complexity=%s (%.3fs)",
                    result.should_respond,
                    result.complexity,
                    time.monotonic() - start_time,
                )
                return result
            except Exception as e:
                logger.warning("LLM evaluation failed, defaulting to respond: %s", e)
                return EvaluationResult(
                    should_respond=True,
                    complexity="medium",
                    suggested_tier="mid",
                    reasoning=f"LLM evaluation failed ({e}), defaulting to respond",
                )

        # Default: respond with medium complexity
        return EvaluationResult(
            should_respond=True,
            complexity="medium",
            suggested_tier="mid",
            reasoning="No fast-path match, LLM disabled, defaulting to respond",
        )

    def _evaluate_non_message(self, event: CognitionEvent) -> EvaluationResult:
        """Handle non-message events."""
        if event.type == EventType.TOOL_RESULT:
            return EvaluationResult(
                should_respond=True,
                complexity="low",
                suggested_tier="mid",
                reasoning="Tool result - continue conversation",
            )
        elif event.type == EventType.SYSTEM:
            return EvaluationResult(
                should_respond=False,
                complexity="low",
                suggested_tier="low",
                reasoning="System event - no response needed",
            )
        elif event.type == EventType.SCHEDULED:
            return EvaluationResult(
                should_respond=True,
                complexity="medium",
                suggested_tier="mid",
                reasoning="Scheduled task - execute",
            )
        return EvaluationResult(
            should_respond=False,
            reasoning=f"Unknown event type: {event.type}",
        )

    def _is_obvious_ignore(
        self,
        content: str,
        user_id: str,
        context: QuickContext,
    ) -> EvaluationResult | None:
        """Check for fast-path IGNORE patterns.

        Returns EvaluationResult with should_respond=False, or None if no match.
        """
        # Bot's own messages
        if user_id in self.config.bot_user_ids:
            return EvaluationResult(
                should_respond=False,
                complexity="low",
                suggested_tier="low",
                reasoning="Bot's own message",
            )

        # Empty or whitespace-only
        if not content:
            return EvaluationResult(
                should_respond=False,
                complexity="low",
                suggested_tier="low",
                reasoning="Empty message",
            )

        # System notifications (join/leave, etc.)
        for pattern in self._skip_patterns:
            if pattern.match(content):
                return EvaluationResult(
                    should_respond=False,
                    complexity="low",
                    suggested_tier="low",
                    reasoning=f"Skip pattern match: {pattern.pattern}",
                )

        return None

    def _is_obvious_respond(
        self,
        content: str,
        context: QuickContext,
    ) -> EvaluationResult | None:
        """Check for fast-path RESPOND patterns.

        Returns EvaluationResult with should_respond=True, or None if no match.
        """
        # Direct message (always respond)
        if context.is_dm:
            return EvaluationResult(
                should_respond=True,
                complexity="medium",
                suggested_tier="mid",
                reasoning="Direct message",
                is_question=content.endswith("?"),
            )

        # Bot mentioned
        if context.has_mention:
            return EvaluationResult(
                should_respond=True,
                complexity="medium",
                suggested_tier="mid",
                reasoning="Bot mentioned",
                is_question=content.endswith("?"),
            )

        # Check mention patterns in content
        for pattern in self._mention_patterns:
            if pattern.search(content):
                return EvaluationResult(
                    should_respond=True,
                    complexity="medium",
                    suggested_tier="mid",
                    reasoning=f"Mention pattern match: {pattern.pattern}",
                    is_question=content.endswith("?"),
                )

        # Command prefix
        if self.config.command_prefix and content.startswith(self.config.command_prefix):
            return EvaluationResult(
                should_respond=True,
                complexity="medium",
                suggested_tier="mid",
                reasoning="Command prefix",
            )

        return None

    async def _llm_evaluate(
        self,
        content: str,
        context: QuickContext,
    ) -> EvaluationResult:
        """Use LLM for nuanced evaluation decisions.

        Args:
            content: Message content
            context: Quick context for additional signals

        Returns:
            EvaluationResult from LLM analysis
        """
        # Build evaluation prompt
        prompt = self._build_evaluation_prompt(content, context)

        # Get LLM function
        if self._llm_fn is None:
            from clara_core.llm import get_quick_llm_response

            self._llm_fn = get_quick_llm_response

        messages = [
            {
                "role": "system",
                "content": "You are an AI assistant message classifier. "
                "Respond ONLY with valid JSON, no other text.",
            },
            {"role": "user", "content": prompt},
        ]

        response = await self._llm_fn(messages)
        return self._parse_llm_response(response)

    def _build_evaluation_prompt(
        self,
        content: str,
        context: QuickContext,
    ) -> str:
        """Build the prompt for LLM evaluation."""
        context_info = []
        if context.is_reply_chain:
            context_info.append("- Part of ongoing conversation")
        if context.recent_message_count > 0:
            context_info.append(f"- {context.recent_message_count} messages in session")
        if context.channel_activity_level != "normal":
            context_info.append(f"- Channel activity: {context.channel_activity_level}")

        context_str = "\n".join(context_info) if context_info else "None"

        return f"""Analyze this message and determine:
1. should_respond: Should the AI assistant respond? (true/false)
2. complexity: How complex is the request? (low/medium/high)
3. suggested_tier: What model tier should handle it? (low/mid/high)
4. tone: What is the message tone? (question/request/statement/greeting/other)
5. reasoning: Brief explanation (10 words max)

Message: "{content[:500]}"

Context:
{context_str}

Consider:
- Greetings/casual chat = low complexity, low tier
- Simple questions/lookups = low complexity, low tier
- Multi-step requests/coding = high complexity, high tier
- Analysis/reasoning = medium-high complexity, mid-high tier

Respond with JSON only:
{{"should_respond": true, "complexity": "low", "suggested_tier": "low", "tone": "greeting", "reasoning": "..."}}"""

    def _parse_llm_response(self, response: str) -> EvaluationResult:
        """Parse LLM response into EvaluationResult.

        Handles various response formats and edge cases gracefully.
        """
        try:
            # Try to extract JSON from response
            response = response.strip()

            # Handle markdown code blocks
            if response.startswith("```"):
                lines = response.split("\n")
                json_lines = []
                in_block = False
                for line in lines:
                    if line.startswith("```"):
                        in_block = not in_block
                        continue
                    if in_block:
                        json_lines.append(line)
                response = "\n".join(json_lines)

            # Find JSON object in response
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                response = response[start:end]

            data = json.loads(response)

            # Map tone to booleans
            tone = data.get("tone", "other")
            is_greeting = tone == "greeting"
            is_question = tone == "question"

            # Map complexity to tier if not provided
            complexity = data.get("complexity", "medium")
            suggested_tier = data.get("suggested_tier")
            if not suggested_tier:
                suggested_tier = {
                    "low": "low",
                    "medium": "mid",
                    "high": "high",
                }.get(complexity, "mid")

            return EvaluationResult(
                should_respond=data.get("should_respond", True),
                complexity=complexity,
                suggested_tier=suggested_tier,
                tone=tone,
                reasoning=data.get("reasoning", "LLM evaluation"),
                is_greeting=is_greeting,
                is_question=is_question,
            )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("Failed to parse LLM response: %s (response: %s)", e, response[:200])
            # Default to responding on parse failure
            return EvaluationResult(
                should_respond=True,
                complexity="medium",
                suggested_tier="mid",
                reasoning=f"Parse error: {e}",
            )


def create_evaluator(
    bot_user_ids: set[str] | None = None,
    mention_patterns: list[str] | None = None,
    command_prefix: str = "!",
    use_llm: bool = True,
) -> Evaluator:
    """Factory function to create a configured Evaluator.

    Args:
        bot_user_ids: Set of bot user IDs to ignore
        mention_patterns: Regex patterns that indicate bot mentions
        command_prefix: Prefix that triggers response (default "!")
        use_llm: Whether to use LLM for unclear cases

    Returns:
        Configured Evaluator instance
    """
    config = EvaluatorConfig(
        bot_user_ids=bot_user_ids or set(),
        mention_patterns=mention_patterns or [],
        command_prefix=command_prefix,
        use_llm_evaluation=use_llm,
    )
    return Evaluator(config=config)
