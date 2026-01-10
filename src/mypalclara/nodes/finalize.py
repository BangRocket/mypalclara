"""
Finalize Node - After acting/speaking, Clara reflects.

- Process cognitive outputs from Ruminate
- Store memories to Cortex
- Update session state
"""

import logging
from datetime import datetime

from mypalclara import memory
from mypalclara.models.state import ClaraState

logger = logging.getLogger(__name__)


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

    return {**state, "complete": True, "next": "end"}


def _extract_topic(event, rumination) -> str:
    """Extract topic from event for session tracking."""
    if rumination and rumination.reasoning:
        # Could use LLM to extract topic, but keep it simple for now
        return rumination.reasoning[:100]
    return event.content[:100] if event.content else "unknown"
