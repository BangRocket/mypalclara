"""
State models for Clara's LangGraph processing.

ClaraState is the TypedDict that flows through the graph,
accumulating context and results at each node.
"""

from typing import Literal, Optional, TypedDict

from pydantic import BaseModel, Field

from mypalclara.models.events import Event
from mypalclara.models.outputs import CognitiveOutput


class QuickContext(BaseModel):
    """
    Lightweight context for Evaluate (no semantic search).

    Fast retrieval from Redis - identity + session only.
    """

    user_id: str
    user_name: str
    identity_facts: list[str] = Field(default_factory=list)
    session: dict = Field(default_factory=dict)
    last_interaction: Optional[str] = None


class MemoryContext(BaseModel):
    """
    Full context for Ruminate (includes semantic retrieval).

    Contains everything Clara knows about this user and situation.
    """

    user_id: str
    user_name: str

    # Identity layer (always present)
    identity_facts: list[str] = Field(default_factory=list)

    # Session layer (current conversation)
    session: dict = Field(default_factory=dict)

    # Working memory (recent, emotionally weighted)
    working_memories: list[dict] = Field(default_factory=list)

    # Long-term retrieval (semantic search results)
    retrieved_memories: list[dict] = Field(default_factory=list)

    # Project context (if applicable)
    project_context: Optional[dict] = None


class EvaluationResult(BaseModel):
    """Output of Evaluate node - reflexive triage."""

    decision: Literal["proceed", "ignore", "wait"]
    reasoning: str
    quick_context: Optional[QuickContext] = None


class RuminationResult(BaseModel):
    """Output of Clara's conscious thought in Ruminate node."""

    decision: Literal["speak", "command", "wait"]
    reasoning: str  # Internal reasoning for debugging

    # If decision == "speak"
    response_draft: Optional[str] = None

    # If decision == "command"
    faculty: Optional[str] = None  # "github" | "browser" | etc.
    intent: Optional[str] = None  # What she's trying to accomplish
    constraints: list[str] = Field(default_factory=list)

    # If decision == "wait"
    wait_reason: Optional[str] = None

    # Things to remember/observe
    cognitive_outputs: list[CognitiveOutput] = Field(default_factory=list)


class FacultyResult(BaseModel):
    """Output of a faculty execution in Command node."""

    success: bool
    data: Optional[dict] = None
    summary: str  # Human-readable summary for Clara
    error: Optional[str] = None
    needs_followup: bool = False


class ClaraState(TypedDict, total=False):
    """
    LangGraph state for Clara's processing.

    This flows through the graph, accumulating results at each node.
    """

    # Input
    event: Event

    # After Evaluate
    evaluation: EvaluationResult
    quick_context: QuickContext

    # After Ruminate
    rumination: RuminationResult
    memory_context: MemoryContext

    # After Command
    faculty_result: FacultyResult
    command_iterations: int  # Track loops to prevent infinite cycling

    # After Speak
    response: str

    # Routing
    next: str

    # Completion
    complete: bool
