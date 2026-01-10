"""
Evaluate Node - Clara's reflexive triage.

Fast pattern matching, no LLM calls. This is Clara's reflex, not her thought.

Decisions:
- proceed: Worth Clara's attention, continue to Ruminate
- ignore: Not worth responding to (matches ignore patterns)
- wait: Considered but nothing to do (not addressed in assistant mode)
"""

import logging
import re

from mypalclara.cortex import cortex_manager
from mypalclara.models.events import ChannelMode, Event
from mypalclara.models.state import ClaraState, EvaluationResult, QuickContext

logger = logging.getLogger(__name__)

# Patterns Clara instinctively ignores (trained reflexes)
IGNORE_PATTERNS = [
    r"^(ok|okay|k|sure|yep|yeah|yes|no|nope)[\s!.]*$",
    r"^(thanks|thank you|thx|ty)[\s!.]*$",
    r"^(lol|lmao|haha|hehe|😂|🤣)[\s!.]*$",
    r"^\W*$",  # Empty or punctuation only
    r"^[!./]\w+",  # Bot commands for other bots (Dyno, MEE6, etc.)
]

# Minimum content length worth considering
MIN_CONTENT_LENGTH = 3


def should_ignore(event: Event, quick_context: QuickContext) -> tuple[bool, str]:
    """
    Pattern-based rejection. No LLM call.
    Returns (should_ignore, reason).
    """
    # Channel is off
    if event.channel_mode == ChannelMode.OFF:
        return True, "channel mode is OFF"

    # No content
    if not event.content:
        return True, "no content"

    content = event.content.strip().lower()

    # Too short
    if len(content) < MIN_CONTENT_LENGTH:
        return True, f"content too short ({len(content)} chars)"

    # Matches ignore pattern
    for pattern in IGNORE_PATTERNS:
        if re.match(pattern, content, re.IGNORECASE):
            return True, "matches ignore pattern"

    return False, ""


def should_proceed(event: Event, quick_context: QuickContext) -> tuple[bool, str]:
    """
    Determine if this event needs Clara's attention.
    Returns (should_proceed, reason).
    """
    # Always respond to DMs
    if event.is_dm:
        return True, "direct message"

    # Always respond when mentioned
    if event.mentioned:
        return True, "mentioned directly"

    # Always respond to replies to Clara
    if event.reply_to_clara:
        return True, "reply to Clara"

    # In conversational mode, engage more freely
    if event.channel_mode == ChannelMode.CONVERSATIONAL:
        return True, "conversational channel"

    # In quiet mode, only direct address
    if event.channel_mode == ChannelMode.QUIET:
        return False, "quiet mode, not directly addressed"

    # Default assistant mode: need to be addressed
    return False, "not addressed in assistant mode"


async def evaluate_node(state: ClaraState) -> ClaraState:
    """
    Fast triage. No heavy reasoning—pattern matching and simple rules.
    This is Clara's reflex, not her thought.
    """
    event = state["event"]

    logger.info(
        f"[evaluate] Reflex check: message from {event.user_name} " f"(DM: {event.is_dm}, mentioned: {event.mentioned})"
    )

    # Get lightweight context (identity + session, no semantic search)
    quick_context = await cortex_manager.get_quick_context(event.user_id)

    # Check ignore patterns first
    ignore, ignore_reason = should_ignore(event, quick_context)
    if ignore:
        logger.info(f"[evaluate] Decision: ignore ({ignore_reason})")
        return {
            **state,
            "evaluation": EvaluationResult(
                decision="ignore",
                reasoning=ignore_reason,
                quick_context=quick_context,
            ),
            "next": "end",
        }

    # Check if we should proceed
    proceed, proceed_reason = should_proceed(event, quick_context)
    if proceed:
        logger.info(f"[evaluate] Decision: proceed ({proceed_reason})")
        return {
            **state,
            "evaluation": EvaluationResult(
                decision="proceed",
                reasoning=proceed_reason,
                quick_context=quick_context,
            ),
            "quick_context": quick_context,
            "next": "ruminate",
        }

    # Default: wait (we considered it but nothing to do)
    logger.info(f"[evaluate] Decision: wait ({proceed_reason})")
    return {
        **state,
        "evaluation": EvaluationResult(
            decision="wait",
            reasoning="no engagement trigger",
            quick_context=quick_context,
        ),
        "next": "end",
    }
