"""
Speak Node - Prepare Clara's response for delivery.

The response was drafted in Ruminate. Here we finalize it
and prepare for platform delivery.
"""

import logging

from mypalclara.models.state import ClaraState

logger = logging.getLogger(__name__)


async def speak_node(state: ClaraState) -> ClaraState:
    """
    Prepare Clara's response for delivery.

    The response was drafted in Ruminate. Here we finalize it
    and prepare for Discord delivery.
    """
    rumination = state["rumination"]
    response = rumination.response_draft

    if not response:
        logger.warning("[speak] No response draft available")
        response = "..."  # Fallback

    logger.info(f"[speak] Response ready ({len(response)} chars)")

    return {
        **state,
        "response": response,
        "next": "finalize",
    }
