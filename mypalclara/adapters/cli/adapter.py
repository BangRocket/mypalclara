"""CLI adapter for Clara.

Implements the PlatformAdapter interface for command-line interaction.
Uses Rich for formatted console output and integrates with prompt_toolkit
for input handling.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncIterator

from rich.console import Console
from rich.markdown import Markdown

from mypalclara.core.platform import PlatformAdapter, PlatformContext, PlatformMessage

logger = logging.getLogger("cli.adapter")


class CLIAdapter(PlatformAdapter):
    """CLI platform adapter for terminal-based interaction.

    Provides a simple, clean interface for Clara in the terminal:
    - Renders responses as formatted Markdown via Rich
    - Exposes console for streaming output
    - No typing indicators (not needed in CLI)

    Attributes:
        console: Rich Console instance for output rendering
    """

    def __init__(self, console: Console | None = None) -> None:
        """Initialize the CLI adapter.

        Args:
            console: Optional Rich Console for output. Creates default if not provided.
        """
        self.console = console or Console()
        logger.debug("CLIAdapter initialized")

    @property
    def platform_name(self) -> str:
        """Return the platform identifier."""
        return "cli"

    def create_context(self, user_id: str) -> PlatformContext:
        """Create a PlatformContext for CLI interaction.

        CLI doesn't have channels or guilds - just a single user session.

        Args:
            user_id: The user identifier

        Returns:
            PlatformContext with CLI-specific settings
        """
        return PlatformContext(
            platform="cli",
            channel=None,  # CLI has no channel concept
            user=None,  # No user object needed
            message=None,
            channel_name="terminal",
        )

    def create_message(
        self,
        user_id: str,
        content: str,
        timestamp: datetime | None = None,
    ) -> PlatformMessage:
        """Create a PlatformMessage from CLI input.

        Args:
            user_id: The user identifier
            content: The message content from user input
            timestamp: Optional timestamp, defaults to now

        Returns:
            PlatformMessage representing the CLI input
        """
        return PlatformMessage(
            user_id=self.format_user_id(user_id),
            platform="cli",
            platform_user_id=user_id,
            content=content,
            channel_id="terminal",
            timestamp=timestamp or datetime.now(),
            metadata={
                "is_dm": True,  # CLI is always a direct conversation
            },
        )

    async def send_message(
        self,
        context: PlatformContext,
        content: str,
        files: list[Any] | None = None,
    ) -> None:
        """Send a message to the CLI (render to console).

        Renders the content as formatted Markdown using Rich.

        Args:
            context: The platform context (unused in CLI)
            content: The message content to render
            files: Optional files (logged but not displayed inline)

        Returns:
            None (CLI doesn't return message objects)
        """
        if not content:
            return

        # Render content as Markdown
        md = Markdown(content)
        self.console.print(md)

        # Note any files that would be attached
        if files:
            logger.debug(f"Files attached (not rendered): {len(files)} file(s)")

    async def send_typing_indicator(self, context: PlatformContext) -> None:
        """Show a typing indicator (no-op for CLI).

        CLI doesn't need typing indicators since output appears immediately.

        Args:
            context: The platform context (unused)
        """
        pass  # No typing indicator needed in CLI

    @asynccontextmanager
    async def streaming_context(self) -> AsyncIterator[Console]:
        """Context manager for streaming output.

        Provides access to the console for live streaming output
        during LLM response generation.

        Usage:
            async with adapter.streaming_context() as console:
                with Live(console=console) as live:
                    # Stream content here
                    pass

        Yields:
            The Rich Console instance for streaming
        """
        yield self.console
