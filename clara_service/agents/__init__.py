"""Specialized agents for ClaraFlow.

Each agent owns a small set of related tools and knows how to use them well.
Clara (Flow) orchestrates these agents - they are workers, not conversationalists.
"""

from clara_service.agents.base import AgentResult, BaseAgent

__all__ = ["BaseAgent", "AgentResult"]
