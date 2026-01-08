"""Code execution agent.

Specializes in running Python code, shell commands, and file operations
in a sandboxed environment.
"""

from __future__ import annotations

from clara_service.agents.base import AgentResult, BaseAgent
from clara_service.agents.code.tools import CODE_TOOLS, set_user_context
from mindflow import Agent


class CodeAgent(BaseAgent):
    """Agent specialized in code execution and file operations.

    Capabilities:
    - Execute Python code in a sandbox
    - Install pip packages
    - Run shell commands
    - Read/write files in the workspace
    - List directory contents
    """

    @property
    def name(self) -> str:
        return "Code Agent"

    @property
    def description(self) -> str:
        return "Executes Python code, shell commands, and manages files in a sandbox"

    @property
    def capabilities(self) -> list[str]:
        return [
            "python",
            "code",
            "execute",
            "run",
            "script",
            "program",
            "install",
            "pip",
            "package",
            "shell",
            "bash",
            "command",
            "file",
            "read",
            "write",
            "create",
        ]

    def _create_agent(self) -> Agent:
        """Create the CrewAI Agent with code execution tools."""
        return Agent(
            role="Python Code Executor",
            goal="Execute Python code and shell commands safely in a sandboxed environment",
            backstory=(
                "You are a skilled Python developer who executes code in a secure sandbox. "
                "You can run Python scripts, install packages, execute shell commands, "
                "and manage files. You always test code before providing results and "
                "handle errors gracefully. You return factual results, not conversational fluff."
            ),
            tools=CODE_TOOLS,
            verbose=False,
            allow_delegation=False,
        )

    def execute(self, task_description: str, context: str = "", user_id: str = "default") -> "AgentResult":
        """Execute a code-related task.

        Args:
            task_description: What to do (e.g., "Run this Python code: print('hello')")
            context: Additional context
            user_id: User ID for sandbox isolation

        Returns:
            AgentResult with execution output
        """
        # Set user context for sandbox tools
        set_user_context(user_id)

        # Call parent execute
        from clara_service.agents.base import AgentResult
        return super().execute(task_description, context)
