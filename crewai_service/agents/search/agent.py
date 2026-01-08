"""Web search agent.

Specializes in finding information on the web.
"""

from __future__ import annotations

from crewai import Agent

from crewai_service.agents.base import BaseAgent
from crewai_service.agents.search.tools import SEARCH_TOOLS


class SearchAgent(BaseAgent):
    """Agent specialized in web search and research.

    Capabilities:
    - Search the web for current information
    - Find documentation and tutorials
    - Research topics in depth
    """

    @property
    def name(self) -> str:
        return "Search Agent"

    @property
    def description(self) -> str:
        return "Searches the web for current information, documentation, and research"

    @property
    def capabilities(self) -> list[str]:
        return [
            "search",
            "web",
            "google",
            "find",
            "lookup",
            "research",
            "news",
            "current",
            "latest",
            "documentation",
            "docs",
            "tutorial",
            "how to",
            "what is",
        ]

    def _create_agent(self) -> Agent:
        """Create the CrewAI Agent with search tools."""
        return Agent(
            role="Web Researcher",
            goal="Find accurate and relevant information from the web",
            backstory=(
                "You are an expert web researcher who finds high-quality information. "
                "You use search tools to find current, accurate data and synthesize "
                "it into clear, useful answers. You cite sources and distinguish "
                "between facts and opinions."
            ),
            tools=SEARCH_TOOLS,
            verbose=False,
            allow_delegation=False,
        )
