"""
Finalize Node - After acting/speaking, Clara reflects.

- Process cognitive outputs from Ruminate
- Store memories to Cortex
- Update session state
- Detect if Clara should auto-continue (spawn a follow-up)
"""

import logging
import re
from datetime import datetime

from mypalclara import memory
from mypalclara.models.events import Event, EventType
from mypalclara.models.state import ClaraState

logger = logging.getLogger(__name__)

# Patterns that indicate Clara is about to do something
# These should trigger a continuation event
CONTINUATION_PATTERNS = [
    # "Let me..." patterns
    r"let me (?:go ahead and |just |quickly )?(?P<action>check|look|search|find|get|run|try|see|pull up|grab|fetch)",
    # "I'll..." patterns
    r"i'?ll (?:go ahead and |just |quickly )?(?P<action>check|look|search|find|get|run|try|see|pull up|grab|fetch)",
    # "Give me a..." patterns
    r"give me (?:a )?(?:sec|second|moment|minute).*(?:to |while i )(?P<action>\w+)",
    # "One moment..." patterns
    r"one (?:sec|second|moment).*(?:while i |let me )(?P<action>\w+)",
    # "Looking into..." patterns
    r"(?:looking into|checking on|searching for|pulling up|running) (?P<action>.+?)(?:\.\.\.|$)",
    # "Let me do X for you" patterns
    r"let me (?P<action>.+?) for you",
]

# Compiled patterns for efficiency
_CONTINUATION_REGEXES = [re.compile(p, re.IGNORECASE) for p in CONTINUATION_PATTERNS]


def _detect_continuation_intent(response: str) -> str | None:
    """
    Detect if Clara's response indicates she's about to do something.

    Returns the detected action/intent if found, None otherwise.
    """
    if not response:
        return None

    # Check first ~200 chars (the continuation intent is usually at the start)
    check_text = response[:300]

    for pattern in _CONTINUATION_REGEXES:
        match = pattern.search(check_text)
        if match:
            # Extract the action from named group or full match
            action = match.group("action") if "action" in pattern.groupindex else match.group(0)
            return action.strip()

    return None


async def finalize_node(state: ClaraState) -> ClaraState:
    """
    After acting/speaking, Clara reflects.

    - Process cognitive outputs from Ruminate
    - Store memories to Cortex
    - Update session state
    """
    event = state["event"]
    rumination = state.get("rumination")
    response = state.get("response")

    # Store cognitive outputs
    if rumination and rumination.cognitive_outputs:
        logger.info(f"[finalize] === STORING {len(rumination.cognitive_outputs)} COGNITIVE OUTPUT(S) ===")
        for i, output in enumerate(rumination.cognitive_outputs, 1):
            if output.type == "remember":
                logger.info(
                    f"[finalize] [{i}] REMEMBER (importance={output.importance}, category={output.category}): "
                    f"{output.content[:100]}..."
                )
                await memory.remember(
                    user_id=event.user_id,
                    content=output.content,
                    importance=output.importance,
                    category=output.category,
                    metadata=output.metadata,
                )
            elif output.type == "observe":
                logger.info(f"[finalize] [{i}] OBSERVE: {output.content[:100]}...")
                # Store observations as low-importance memories
                # They're still valuable context even if not "permanent" facts
                await memory.remember(
                    user_id=event.user_id,
                    content=output.content,
                    importance=output.importance,  # Usually 0.3, short TTL
                    category="observation",
                    metadata={"type": "observe"},
                )
            elif output.type == "identity":
                logger.info(f"[finalize] [{i}] IDENTITY: {output.content[:100]}...")
                # Store as identity fact - this goes to Redis identity store
                # which is always loaded for the user
                await memory.update_identity(
                    user_id=event.user_id,
                    content=output.content,
                )
    else:
        logger.debug("[finalize] No cognitive outputs to store")

    # Update session
    session_updates = {
        "last_topic": _extract_topic(event, rumination),
        "last_active": datetime.utcnow().isoformat(),
        "last_response": response[:200] if response else None,
        "user_name": event.user_name,
    }
    logger.debug(f"[finalize] Updating session for user={event.user_id}: {list(session_updates.keys())}")
    await memory.update_session(user_id=event.user_id, updates=session_updates)

    logger.info(f"[finalize] === COMPLETE for user={event.user_id} ===")

    # Check if Clara should auto-continue
    continuation_event = None
    if event.can_spawn and response:
        intent = _detect_continuation_intent(response)
        if intent:
            logger.info(f"[finalize] Detected continuation intent: '{intent}'")
            # Create a continuation event that cannot spawn further
            continuation_event = Event(
                id=f"{event.id}-cont",
                type=EventType.MESSAGE,
                user_id=event.user_id,
                user_name=event.user_name,
                channel_id=event.channel_id,
                guild_id=event.guild_id,
                content=f"[Continue: {intent}]",  # Internal prompt
                is_dm=event.is_dm,
                mentioned=True,  # Treat as direct address
                channel_mode=event.channel_mode,
                can_spawn=False,  # IMPORTANT: Cannot spawn another
                is_continuation=True,
                continuation_context=intent,
                metadata={"parent_event_id": event.id},
            )
            logger.info(f"[finalize] Created continuation event: {continuation_event.id}")

    return {
        **state,
        "complete": True,
        "next": "end",
        "continuation_event": continuation_event,
    }


def _extract_topic(event, rumination) -> str:
    """Extract topic from event for session tracking."""
    if rumination and rumination.reasoning:
        # Could use LLM to extract topic, but keep it simple for now
        return rumination.reasoning[:100]
    return event.content[:100] if event.content else "unknown"
