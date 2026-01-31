"""Standalone CLI adapter for the Clara Gateway.

Interactive command-line interface that connects to the gateway.

Usage:
    poetry run python -m adapters.cli

Environment variables:
    CLARA_GATEWAY_URL - Gateway WebSocket URL (default: ws://127.0.0.1:18789)
    CLI_USER_ID - User identifier (default: cli-user)
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv

load_dotenv()

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from adapters.cli.gateway_client import CLIGatewayClient
from config.logging import get_logger, init_logging

init_logging()
logger = get_logger("adapters.cli")

# Configuration
GATEWAY_URL = os.getenv("CLARA_GATEWAY_URL", "ws://127.0.0.1:18789")
USER_ID = os.getenv("CLI_USER_ID", "cli-user")
HISTORY_FILE = Path.home() / ".clara_cli_history"


async def main() -> None:
    """Run the CLI interface."""
    console = Console()

    # Print welcome
    console.print(
        Panel(
            "[bold blue]Clara CLI[/bold blue]\n"
            f"Gateway: {GATEWAY_URL}\n"
            "Type 'exit' or 'quit' to exit. Ctrl+C to cancel.",
            title="Welcome",
            border_style="blue",
        )
    )

    # Create gateway client
    client = CLIGatewayClient(
        console=console,
        user_id=USER_ID,
        gateway_url=GATEWAY_URL,
    )

    # Connect to gateway
    console.print("[yellow]Connecting to gateway...[/yellow]")
    if not await client.connect():
        console.print("[red]Failed to connect to gateway[/red]")
        console.print("Make sure the gateway is running: poetry run python -m gateway")
        return

    console.print("[green]Connected![/green]\n")

    # Create prompt session with history
    session: PromptSession[str] = PromptSession(
        history=FileHistory(str(HISTORY_FILE)),
    )

    try:
        while True:
            try:
                # Get user input
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: session.prompt("You: "),
                )

                # Check for exit commands
                if user_input.lower().strip() in ("exit", "quit", "bye"):
                    console.print("[yellow]Goodbye![/yellow]")
                    break

                # Skip empty input
                if not user_input.strip():
                    continue

                # Detect tier override
                tier = None
                content = user_input
                tier_prefixes = {
                    "!high": "high",
                    "!opus": "high",
                    "!mid": "mid",
                    "!sonnet": "mid",
                    "!low": "low",
                    "!haiku": "low",
                    "!fast": "low",
                }
                for prefix, t in tier_prefixes.items():
                    if content.lower().startswith(prefix):
                        tier = t
                        content = content[len(prefix) :].strip()
                        break

                # Send message
                console.print()  # Blank line before response
                response = await client.send_cli_message(content, tier_override=tier)

                # Print final response with markdown
                if response:
                    console.print()  # Blank line
                    console.print(Markdown(response))
                    console.print()  # Blank line after response

            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted[/yellow]")
                continue
            except EOFError:
                break

    finally:
        await client.disconnect()
        console.print("[grey]Disconnected[/grey]")


def run() -> None:
    """Entry point for the CLI."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
