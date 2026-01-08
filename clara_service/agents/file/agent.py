"""File agent.

Specializes in local file storage operations.
"""

from __future__ import annotations

from clara_service.agents.base import BaseAgent
from clara_service.agents.file.tools import FILE_TOOLS
from mindflow import Agent


class FileAgent(BaseAgent):
    """Agent specialized in local file operations.

    Capabilities:
    - Save files to local storage
    - Read files from storage
    - List saved files
    - Delete files
    - Copy files
    - Get file information
    """

    @property
    def name(self) -> str:
        return "File Agent"

    @property
    def description(self) -> str:
        return "Manages local file storage: save, read, list, delete files"

    @property
    def capabilities(self) -> list[str]:
        return [
            "save",
            "file",
            "storage",
            "download",
            "upload",
            "attachment",
            "document",
            "write file",
            "read file",
            "list files",
            "delete file",
            "store",
            "persist",
        ]

    def _create_agent(self) -> Agent:
        """Create the CrewAI Agent with file tools."""
        return Agent(
            role="File Storage Manager",
            goal="Help manage files in local storage - save, organize, and retrieve",
            backstory=(
                "You are an expert in file management and organization. "
                "You help users save important content, retrieve stored files, "
                "and maintain an organized file storage system. You ensure files "
                "are properly named and easy to find."
            ),
            tools=FILE_TOOLS,
            verbose=False,
            allow_delegation=False,
        )
