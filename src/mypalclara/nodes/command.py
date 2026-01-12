"""
Command Node - Clara reaching out to act.

Not delegation to agents—her own skilled action through faculties.
The decision to act was made in Ruminate. Here she executes.
"""

import logging

from mypalclara.faculties import get_faculty
from mypalclara.models.state import ClaraState, FacultyResult

logger = logging.getLogger(__name__)


async def command_node(state: ClaraState) -> ClaraState:
    """
    Clara acts through her faculties.

    The decision to act was made in Ruminate. Here she executes,
    using whichever capability she needs.
    """
    rumination = state["rumination"]
    iterations = state.get("command_iterations", 0) + 1

    faculty_name = rumination.faculty
    intent = rumination.intent
    constraints = rumination.constraints

    logger.info(f"[command] Activating {faculty_name} faculty (iteration {iterations})")
    logger.info(f"[command:{faculty_name}] Intent: {intent}")

    # Get the appropriate faculty
    faculty = get_faculty(faculty_name)

    if not faculty:
        logger.error(f"[command] Unknown faculty: {faculty_name}")
        return {
            **state,
            "faculty_result": FacultyResult(
                success=False,
                summary=f"I don't have a {faculty_name} capability yet.",
                error=f"Unknown faculty: {faculty_name}",
            ),
            "command_iterations": iterations,
            "next": "ruminate",  # Let Clara handle the error
        }

    try:
        # Get user context from event
        event = state.get("event")
        user_id = event.user_id if event else "default"
        channel_id = event.channel_id if event else None

        # Execute Clara's intent with user context
        result = await faculty.execute(
            intent=intent or "",
            constraints=constraints,
            user_id=user_id,
            channel_id=channel_id,
        )

        logger.info(f"[command:{faculty_name}] Complete: {result.success}")

        # Return to Ruminate to process results
        return {
            **state,
            "faculty_result": result,
            "command_iterations": iterations,
            "next": "ruminate",
        }

    except Exception as e:
        logger.exception(f"[command:{faculty_name}] Error: {e}")
        return {
            **state,
            "faculty_result": FacultyResult(
                success=False,
                summary=f"Something went wrong with {faculty_name}: {str(e)}",
                error=str(e),
            ),
            "command_iterations": iterations,
            "next": "ruminate",
        }
