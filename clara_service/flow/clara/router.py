"""Agent router for ClaraFlow.

Decides which specialized agent(s) to invoke based on the user's request.
Uses a combination of keyword matching (fast) and LLM routing (accurate).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from clara_service.agents.base import AgentResult, BaseAgent
from clara_service.agents.code import CodeAgent
from clara_service.agents.file import FileAgent
from clara_service.agents.github import GitHubAgent
from clara_service.agents.search import SearchAgent

if TYPE_CHECKING:
    pass


logger = logging.getLogger(__name__)


class AgentRouter:
    """Routes requests to specialized agents.

    The router:
    1. Uses keyword matching for quick filtering
    2. Can use LLM for more nuanced routing decisions
    3. Returns results from the selected agent(s)
    """

    def __init__(self):
        """Initialize the router with available agents."""
        self._agents: dict[str, BaseAgent] = {}
        self._register_agents()

    def _register_agents(self) -> None:
        """Register all available agents."""
        agents = [
            CodeAgent(),
            SearchAgent(),
            GitHubAgent(),
            FileAgent(),
        ]
        for agent in agents:
            self._agents[agent.name] = agent
            logger.info(f"[router] Registered agent: {agent.name}")

    @property
    def agents(self) -> dict[str, BaseAgent]:
        """Get all registered agents."""
        return self._agents

    def get_agent(self, name: str) -> BaseAgent | None:
        """Get an agent by name."""
        return self._agents.get(name)

    def find_agents_for_query(self, query: str) -> list[BaseAgent]:
        """Find agents that can potentially handle a query.

        Uses keyword matching for fast filtering.

        Args:
            query: The user's query or task

        Returns:
            List of agents that might handle this query
        """
        matching = []
        for agent in self._agents.values():
            if agent.can_handle(query):
                matching.append(agent)
        return matching

    def route(
        self,
        query: str,
        user_id: str = "default",
        context: str = "",
        on_agent_start: callable = None,
        on_agent_end: callable = None,
    ) -> AgentResult | None:
        """Route a query to the appropriate agent and execute.

        Args:
            query: The user's query or task
            user_id: User ID for sandbox isolation
            context: Additional context
            on_agent_start: Callback(agent_name) when agent starts
            on_agent_end: Callback(agent_name, success, error) when agent ends

        Returns:
            AgentResult from the selected agent, or None if no agent matches
        """
        # Find matching agents
        candidates = self.find_agents_for_query(query)

        if not candidates:
            logger.info(f"[router] No agents matched query: {query[:50]}...")
            return None

        # For now, use the first matching agent
        # TODO: Use LLM to select best agent when multiple match
        agent = candidates[0]
        logger.info(f"[router] Routing to: {agent.name}")

        # Notify start
        if on_agent_start:
            on_agent_start(agent.name)

        # Execute with user context
        try:
            if hasattr(agent, "execute") and "user_id" in agent.execute.__code__.co_varnames:
                result = agent.execute(query, context=context, user_id=user_id)
            else:
                result = agent.execute(query, context=context)

            # Notify end with error if failed
            if on_agent_end:
                error = result.error if result and not result.success else None
                on_agent_end(agent.name, result.success if result else False, error)

            return result
        except Exception as e:
            # Notify failure with exception message
            if on_agent_end:
                on_agent_end(agent.name, False, str(e))
            raise

    def route_with_llm(
        self,
        query: str,
        llm_callable,
        user_id: str = "default",
        context: str = "",
    ) -> AgentResult | None:
        """Route using LLM to select the best agent.

        Args:
            query: The user's query or task
            llm_callable: Function to call LLM for routing decision
            user_id: User ID for sandbox isolation
            context: Additional context

        Returns:
            AgentResult from the selected agent, or None if no agent should handle it
        """
        # Build agent descriptions for LLM
        agent_list = "\n".join([
            f"- {agent.name}: {agent.description}"
            for agent in self._agents.values()
        ])

        routing_prompt = f"""Given the user's request, decide which agent (if any) should handle it.

Available agents:
{agent_list}

User request: {query}

If an agent should handle this, respond with just the agent name (e.g., "Code Agent").
If no agent is needed (just conversation), respond with "NONE".
"""

        try:
            # Call LLM for routing decision
            messages = [{"role": "user", "content": routing_prompt}]
            decision = llm_callable(messages).strip()

            if decision == "NONE" or decision.lower() == "none":
                logger.info("[router] LLM decided no agent needed")
                return None

            # Find the selected agent
            agent = self.get_agent(decision)
            if not agent:
                # Try fuzzy matching
                for name, a in self._agents.items():
                    if decision.lower() in name.lower():
                        agent = a
                        break

            if agent:
                logger.info(f"[router] LLM selected: {agent.name}")
                if hasattr(agent, "execute") and "user_id" in agent.execute.__code__.co_varnames:
                    return agent.execute(query, context=context, user_id=user_id)
                else:
                    return agent.execute(query, context=context)
            else:
                logger.warning(f"[router] LLM selected unknown agent: {decision}")
                return None

        except Exception as e:
            logger.error(f"[router] LLM routing failed: {e}")
            # Fall back to keyword matching
            return self.route(query, user_id, context)


# Global singleton
_router: AgentRouter | None = None


def get_router() -> AgentRouter:
    """Get the global agent router."""
    global _router
    if _router is None:
        _router = AgentRouter()
    return _router
