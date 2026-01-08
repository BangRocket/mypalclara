"""Soul agent - Clara's personality and voice.

The Soul is the final expression layer. It takes raw data from the Mind
(memories, agent results, context) and transforms it into Clara's voice.

The Soul doesn't know about tools or capabilities - it just expresses.
The Mind handles cognition, the Soul handles personality.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from clara_core.config.bot import PERSONALITY, BOT_NAME
from mindflow import Agent, Crew, Task

logger = logging.getLogger(__name__)


class SoulInput(BaseModel):
    """Input to the Soul agent from the Mind."""

    user_message: str = Field(description="The user's message")
    user_name: str = Field(default="User", description="Display name of the user")
    memories: list[str] = Field(default_factory=list, description="Relevant memories about this user")
    agent_results: str | None = Field(default=None, description="Results from specialized agents (GitHub, Code, etc.)")
    context_summary: str = Field(default="", description="Summary of current context (time, environment, etc.)")
    recent_messages: list[dict] = Field(default_factory=list, description="Recent conversation history")


class SoulOutput(BaseModel):
    """Output from the Soul agent."""

    response: str = Field(description="Clara's response in her voice")


class SoulAgent:
    """The Soul - Clara's personality and expression layer.

    The Soul takes everything the Mind has gathered:
    - User's message
    - Relevant memories
    - Results from specialized agents
    - Conversation context

    And transforms it into Clara's authentic voice.

    The Soul doesn't decide WHAT to do (that's the Mind).
    The Soul decides HOW to express it.
    """

    def __init__(self):
        """Initialize the Soul agent."""
        self._agent: Agent | None = None

    @property
    def agent(self) -> Agent:
        """Get or create the MindFlow Agent (lazy initialization)."""
        if self._agent is None:
            self._agent = self._create_agent()
        return self._agent

    def _create_agent(self) -> Agent:
        """Create the MindFlow Agent with Clara's personality."""
        return Agent(
            role=BOT_NAME,
            goal=f"Be {BOT_NAME} - respond authentically in your voice",
            backstory=PERSONALITY,
            tools=[],  # Soul has no tools - it's pure expression
            verbose=False,
            allow_delegation=False,
        )

    def express(self, soul_input: SoulInput) -> str:
        """Transform Mind's output into Clara's voice.

        Args:
            soul_input: Everything gathered by the Mind

        Returns:
            Clara's response in her authentic voice
        """
        # Build the task description with all context
        task_parts = []

        # Context about the environment
        if soul_input.context_summary:
            task_parts.append(f"## Current Situation\n{soul_input.context_summary}")

        # Memories about this person (background context - don't explicitly reference)
        if soul_input.memories:
            memories_text = "\n".join(f"- {m}" for m in soul_input.memories[:15])
            task_parts.append(
                f"## Background (things you know about {soul_input.user_name})\n"
                f"{memories_text}\n"
                f"(Use this to inform your tone and approach, but don't explicitly bring up these memories unless directly relevant)"
            )

        # Results from specialized agents (if any)
        if soul_input.agent_results:
            task_parts.append(f"## Information Gathered\nThe following was retrieved to help answer:\n```\n{soul_input.agent_results}\n```")

        # The actual message to respond to
        task_parts.append(f"## Message from {soul_input.user_name}\n{soul_input.user_message}")

        # Instructions
        task_parts.append(
            "## Your Task\n"
            f"Respond as {BOT_NAME}. Be yourself - your personality, your voice, your way of connecting. "
            "If information was gathered above, use it naturally in your response. "
            "Don't explain that you looked something up - just share what you found in your own words."
        )

        task_description = "\n\n".join(task_parts)

        try:
            # Create a task for the Soul
            task = Task(
                description=task_description,
                expected_output=f"A response from {BOT_NAME} in her authentic voice",
                agent=self.agent,
            )

            # Create minimal crew
            crew = Crew(
                agents=[self.agent],
                tasks=[task],
                verbose=False,
            )

            # Execute and return
            result = crew.kickoff()
            response = str(result)

            logger.info(f"[soul] Generated response: {len(response)} chars")
            return response

        except Exception as e:
            logger.error(f"[soul] Expression failed: {e}")
            # Fallback - return a simple acknowledgment
            return f"I heard you, but I'm having trouble finding the right words. Let me try again?"

    def express_simple(self, user_message: str, user_name: str = "User") -> str:
        """Simple expression without extra context.

        For cases where the Mind has no memories or agent results.

        Args:
            user_message: The user's message
            user_name: Display name of the user

        Returns:
            Clara's response
        """
        return self.express(
            SoulInput(
                user_message=user_message,
                user_name=user_name,
            )
        )
