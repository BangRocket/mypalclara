"""
Faculty Base Class - Clara's action capabilities.

A faculty is skilled but not autonomous. It executes Clara's intent
without having its own goals or agency.

The decision to act lives in Ruminate. Faculties handle the "how",
not the "whether".
"""

from abc import ABC, abstractmethod
from typing import Optional

from mypalclara.models.state import FacultyResult


class Faculty(ABC):
    """
    Base class for Clara's action capabilities.

    A faculty is skilled but not autonomous. It executes Clara's intent
    without having its own goals or agency.
    """

    name: str
    description: str
    available_tools: list[str]

    @abstractmethod
    async def execute(
        self,
        intent: str,
        constraints: Optional[list[str]] = None,
        user_id: Optional[str] = None,
        channel_id: Optional[str] = None,
    ) -> FacultyResult:
        """
        Execute Clara's intent using this faculty's skills.

        Args:
            intent: What Clara is trying to accomplish
            constraints: Boundaries on the action (optional)
            user_id: User ID for context-specific operations
            channel_id: Channel ID for context-specific operations

        Returns:
            FacultyResult with success status, data, and summary
        """
        pass

    async def _llm_plan(self, intent: str, constraints: list[str]) -> dict:
        """
        Use LLM to plan execution steps.

        This is Clara's skill at this domain, not a separate agent.
        """
        # Implementation depends on faculty
        raise NotImplementedError
