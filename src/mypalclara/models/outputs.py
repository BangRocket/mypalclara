"""
Cognitive output models.

These represent things Clara notices or wants to remember
during her processing - observations and memories.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class CognitiveOutput(BaseModel):
    """
    Something Clara noticed or wants to remember.

    Types:
    - remember: Store as a memory (persisted in Cortex)
    - observe: Internal observation (may inform future behavior)
    """

    type: Literal["remember", "observe"]
    content: str
    category: Optional[str] = None  # "fact", "preference", "pattern", etc.
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: dict = Field(default_factory=dict)
