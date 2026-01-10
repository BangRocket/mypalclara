"""
Finalize Node - After acting/speaking, Clara reflects.

- Process cognitive outputs from Ruminate
- Store memories to Cortex
- Update session state
"""

import logging
from datetime import datetime

from mypalclara.cortex import cortex_manager
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
        for output in rumination.cognitive_outputs:
            if output.type == "remember":
                logger.info(f"[finalize] Storing memory (importance: {output.importance})")
                await cortex_manager.remember(
                    user_id=event.user_id,
                    content=output.content,
                    importance=output.importance,
                    category=output.category,
                    metadata=output.metadata,
                )
            elif output.type == "observe":
                logger.info("[finalize] Recording observation")
                # ORS integration - for now just log
                # Future: await ors.note(output)

    # Update session
    await cortex_manager.update_session(
        user_id=event.user_id,
        updates={
            "last_topic": _extract_topic(event, rumination),
            "last_active": datetime.utcnow().isoformat(),
            "last_response": response[:200] if response else None,
            "user_name": event.user_name,
        },
    )

    logger.info("[finalize] Complete")

    return {**state, "complete": True, "next": "end"}


def _extract_topic(event, rumination) -> str:
    """Extract topic from event for session tracking."""
    if rumination and rumination.reasoning:
        # Could use LLM to extract topic, but keep it simple for now
        return rumination.reasoning[:100]
    return event.content[:100] if event.content else "unknown"
