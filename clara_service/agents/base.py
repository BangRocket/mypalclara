"""Base agent pattern for specialized agents.

Agents are workers that Clara's Flow orchestrates. They:
- Own 3-8 related tools max
- Have a clear role description
- Return structured results, not conversational fluff
- Are experts in their domain
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from crewai import Agent, Crew, Task


class AgentResult(BaseModel):
    """Structured result from an agent execution."""

    success: bool = True
    output: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class BaseAgent(ABC):
    """Base class for specialized agents.

    Subclasses must implement:
    - _create_agent(): Create the CrewAI Agent with tools
    - name: Human-readable name for logging/routing

    Usage:
        agent = CodeAgent()
        result = agent.execute("Run this Python code: print('hello')")
    """

    def __init__(self):
        """Initialize the agent."""
        self._agent: Agent | None = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for this agent."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Brief description of what this agent does (for routing)."""
        pass

    @property
    @abstractmethod
    def capabilities(self) -> list[str]:
        """List of capabilities/keywords for routing decisions."""
        pass

    @abstractmethod
    def _create_agent(self) -> Agent:
        """Create and configure the CrewAI Agent with tools.

        Returns:
            Configured CrewAI Agent
        """
        pass

    @property
    def agent(self) -> Agent:
        """Get or create the CrewAI Agent (lazy initialization)."""
        if self._agent is None:
            self._agent = self._create_agent()
        return self._agent

    def execute(self, task_description: str, context: str = "") -> AgentResult:
        """Execute a task using this agent.

        Args:
            task_description: What the agent should do
            context: Additional context (e.g., user info, prior conversation)

        Returns:
            AgentResult with output and any structured data
        """
        try:
            # Create a task for this agent
            task = Task(
                description=task_description,
                expected_output="Complete the task and return results",
                agent=self.agent,
            )

            # Create a minimal crew with just this agent
            crew = Crew(
                agents=[self.agent],
                tasks=[task],
                verbose=False,
            )

            # Execute and get result
            result = crew.kickoff()

            return AgentResult(
                success=True,
                output=str(result),
                data={},
            )

        except Exception as e:
            return AgentResult(
                success=False,
                output="",
                error=str(e),
            )

    def can_handle(self, query: str) -> bool:
        """Check if this agent can likely handle the given query.

        Used by the router for quick filtering before LLM-based routing.

        Args:
            query: The user's query or task description

        Returns:
            True if this agent might be able to handle the query
        """
        query_lower = query.lower()
        return any(cap.lower() in query_lower for cap in self.capabilities)
