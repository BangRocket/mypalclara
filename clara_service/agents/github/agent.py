"""GitHub agent.

Specializes in GitHub operations: repos, issues, PRs, files.
"""

from __future__ import annotations

from clara_service.agents.base import BaseAgent
from clara_service.agents.github.tools import GITHUB_TOOLS
from crewai import Agent


class GitHubAgent(BaseAgent):
    """Agent specialized in GitHub operations.

    Capabilities:
    - Search and browse repositories
    - List and create issues
    - List and review pull requests
    - Read file contents
    - Get user profiles
    """

    @property
    def name(self) -> str:
        return "GitHub Agent"

    @property
    def description(self) -> str:
        return "Interacts with GitHub: repos, issues, PRs, files, and users"

    @property
    def capabilities(self) -> list[str]:
        return [
            "github",
            "repository",
            "repo",
            "issue",
            "pull request",
            "pr",
            "commit",
            "branch",
            "code review",
            "merge",
            "fork",
            "star",
            "contributor",
            "release",
        ]

    def _create_agent(self) -> Agent:
        """Create the CrewAI Agent with GitHub tools."""
        return Agent(
            role="GitHub Specialist",
            goal="Help with GitHub operations - repositories, issues, PRs, and code",
            backstory=(
                "You are an expert in GitHub workflows and collaboration. "
                "You help manage repositories, track issues, review pull requests, "
                "and navigate codebases. You provide clear summaries and actionable insights."
            ),
            tools=GITHUB_TOOLS,
            verbose=False,
            allow_delegation=False,
        )
