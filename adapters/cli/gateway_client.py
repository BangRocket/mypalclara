"""CLI gateway client for the Clara Gateway.

Connects a command-line interface to the gateway for processing.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.text import Text

from adapters.base import GatewayClient
from config.logging import get_logger
from gateway.protocol import ChannelInfo, UserInfo

logger = get_logger("adapters.cli.gateway")


class CLIGatewayClient(GatewayClient):
    """CLI-specific gateway client.

    Handles terminal output with Rich formatting and live streaming display.
    """

    def __init__(
        self,
        console: Console | None = None,
        user_id: str = "cli-user",
        gateway_url: str | None = None,
    ) -> None:
        """Initialize the CLI gateway client.

        Args:
            console: Rich Console for output
            user_id: User identifier
            gateway_url: Optional gateway URL override
        """
        super().__init__(
            platform="cli",
            capabilities=["streaming"],
            gateway_url=gateway_url,
        )
        self.console = console or Console()
        self.user_id = user_id
        self._live: Live | None = None
        self._current_text = ""
        self._current_tools = 0
        self._response_event: asyncio.Event | None = None

    async def send_cli_message(
        self,
        content: str,
        tier_override: str | None = None,
    ) -> str:
        """Send a message and wait for the response.

        Args:
            content: Message content
            tier_override: Optional model tier

        Returns:
            Complete response text
        """
        # Reset state
        self._current_text = ""
        self._current_tools = 0
        self._response_event = asyncio.Event()

        # Build user info
        user = UserInfo(
            id=f"cli-{self.user_id}",
            platform_id=self.user_id,
            name=self.user_id,
        )

        # Build channel info (CLI is always a "dm")
        channel = ChannelInfo(
            id=f"cli-{self.user_id}",
            type="dm",
            name="terminal",
        )

        # Send to gateway
        request_id = await self.send_message(
            user=user,
            channel=channel,
            content=content,
            tier_override=tier_override,
        )

        # Wait for response with live display
        with Live(
            Spinner("dots", text="Thinking..."),
            console=self.console,
            refresh_per_second=4,
        ) as live:
            self._live = live
            try:
                # Wait for response_end event
                await asyncio.wait_for(
                    self._response_event.wait(),
                    timeout=300.0,  # 5 minute timeout
                )
            except asyncio.TimeoutError:
                self.console.print("[red]Response timeout[/red]")
            finally:
                self._live = None

        return self._current_text

    async def on_response_start(self, message: Any) -> None:
        """Handle response start."""
        if self._live:
            self._live.update(Spinner("dots", text="Generating..."))

    async def on_response_chunk(self, message: Any) -> None:
        """Handle streaming response chunk."""
        self._current_text = message.accumulated or (self._current_text + message.chunk)

        if self._live:
            # Show current text with markdown rendering
            try:
                md = Markdown(self._current_text)
                self._live.update(md)
            except Exception:
                self._live.update(Text(self._current_text))

    async def on_response_end(self, message: Any) -> None:
        """Handle response completion."""
        self._current_text = message.full_text
        self._current_tools = message.tool_count

        # Signal completion
        if self._response_event:
            self._response_event.set()

    async def on_tool_start(self, message: Any) -> None:
        """Handle tool execution start."""
        self._current_tools = message.step

        if self._live:
            tool_text = f"{message.emoji} {message.tool_name}... (step {message.step})"
            self._live.update(
                Panel(
                    Text(tool_text, style="yellow"),
                    title="Tool",
                    border_style="yellow",
                )
            )

    async def on_tool_result(self, message: Any) -> None:
        """Handle tool execution result."""
        if self._live:
            status = "✓" if message.success else "✗"
            color = "green" if message.success else "red"
            tool_text = f"{status} {message.tool_name}"
            self._live.update(
                Panel(
                    Text(tool_text, style=color),
                    title="Tool Result",
                    border_style=color,
                )
            )
            # Brief pause to show result
            await asyncio.sleep(0.3)
            # Return to thinking spinner
            self._live.update(Spinner("dots", text="Continuing..."))

    async def on_error(self, message: Any) -> None:
        """Handle gateway error."""
        await super().on_error(message)
        self.console.print(f"[red]Error: {message.message}[/red]")
        if self._response_event:
            self._response_event.set()

    async def on_cancelled(self, message: Any) -> None:
        """Handle request cancellation."""
        await super().on_cancelled(message)
        self.console.print("[yellow]Request cancelled[/yellow]")
        if self._response_event:
            self._response_event.set()
