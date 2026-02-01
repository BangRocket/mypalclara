"""Main CLI application entry point.

Uses Typer for a modern CLI experience with:
- Automatic help generation
- Command groups
- Rich output formatting
- Lazy loading for fast startup
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

# Create the main app
app = typer.Typer(
    name="clara",
    help="Clara AI Assistant - Personal AI gateway and assistant",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=True,
)

# Console for rich output
console = Console()

# Profile for environment switching
_profile: str | None = None


def get_profile() -> str | None:
    """Get the current profile."""
    return _profile or os.getenv("CLARA_PROFILE")


def set_profile(profile: str | None) -> None:
    """Set the current profile."""
    global _profile
    _profile = profile
    if profile:
        os.environ["CLARA_PROFILE"] = profile


# =============================================================================
# Lazy-loaded command groups
# =============================================================================


def _load_gateway_commands() -> typer.Typer:
    """Lazy load gateway commands."""
    from clara_core.cli.commands.gateway import gateway_app
    return gateway_app


def _load_channel_commands() -> typer.Typer:
    """Lazy load channel commands."""
    from clara_core.cli.commands.channels import channels_app
    return channels_app


def _load_plugin_commands() -> typer.Typer:
    """Lazy load plugin commands."""
    from clara_core.cli.commands.plugins import plugins_app
    return plugins_app


def _load_config_commands() -> typer.Typer:
    """Lazy load config commands."""
    from clara_core.cli.commands.config import config_app
    return config_app


def _load_status_commands() -> typer.Typer:
    """Lazy load status commands."""
    from clara_core.cli.commands.status import status_app
    return status_app


# Register command groups (lazy loaded on first access)
app.add_typer(_load_gateway_commands(), name="gateway", help="Gateway server management")
app.add_typer(_load_channel_commands(), name="channels", help="Channel plugin management")
app.add_typer(_load_plugin_commands(), name="plugins", help="Extension plugin management")
app.add_typer(_load_config_commands(), name="config", help="Configuration management")
app.add_typer(_load_status_commands(), name="status", help="Status and diagnostics")


# =============================================================================
# Top-level commands
# =============================================================================


@app.command()
def chat(
    message: Optional[str] = typer.Argument(None, help="Message to send (interactive if omitted)"),
    agent: str = typer.Option("clara", "--agent", "-a", help="Agent/persona to use"),
    tier: str = typer.Option("mid", "--tier", "-t", help="Model tier (low, mid, high)"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Configuration profile"),
) -> None:
    """Start an interactive chat session or send a single message.

    Examples:
        clara chat                      # Interactive mode
        clara chat "Hello, Clara!"      # Single message
        clara chat -a flo "Hi there"    # Use different agent
        clara chat -t high "Complex question"  # Use high-tier model
    """
    if profile:
        set_profile(profile)

    from clara_core.cli.commands.chat import run_chat
    run_chat(message=message, agent=agent, tier=tier)


@app.command()
def version() -> None:
    """Show Clara version information."""

    version_file = Path(__file__).parent.parent.parent / "VERSION"
    if version_file.exists():
        version = version_file.read_text().strip()
    else:
        version = "unknown"

    console.print(Panel(
        f"[bold blue]Clara[/bold blue] version [green]{version}[/green]\n\n"
        f"Python: {sys.version.split()[0]}\n"
        f"Platform: {sys.platform}",
        title="Version Info",
        border_style="blue",
    ))


@app.command()
def doctor() -> None:
    """Run diagnostics and check system health.

    Checks:
    - Configuration validity
    - Database connectivity
    - Gateway connectivity
    - Memory system (mem0) status
    - Channel plugin status
    """
    from clara_core.cli.commands.doctor import run_doctor
    run_doctor()


@app.command()
def onboard() -> None:
    """Run the interactive onboarding wizard.

    Guides you through:
    - Initial configuration
    - LLM provider setup
    - Channel connections (Discord, etc.)
    - Memory system setup
    """
    from clara_core.cli.commands.onboard import run_onboard
    run_onboard()


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Bind address"),
    port: int = typer.Option(18789, "--port", "-p", help="Port number"),
    profile: Optional[str] = typer.Option(None, "--profile", help="Configuration profile"),
    detach: bool = typer.Option(False, "--detach", "-d", help="Run in background"),
) -> None:
    """Start the Clara gateway server.

    The gateway server handles:
    - WebSocket connections from channel adapters
    - Message processing and LLM orchestration
    - Tool execution
    - Plugin management

    Examples:
        clara serve                     # Start on default port
        clara serve -p 8080             # Start on port 8080
        clara serve --detach            # Run in background
    """
    if profile:
        set_profile(profile)

    from clara_core.cli.commands.gateway import start_gateway
    start_gateway(host=host, port=port, detach=detach)


@app.callback()
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress non-essential output"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Configuration profile"),
) -> None:
    """Clara AI Assistant - Personal AI gateway and assistant.

    Clara is a personal AI assistant platform that enables you to run your own
    AI gateway and interact with it across multiple messaging channels.

    Use --help on any command for more information.
    """
    if profile:
        set_profile(profile)

    # Set log level based on verbosity
    if verbose:
        os.environ["LOG_LEVEL"] = "DEBUG"
    elif quiet:
        os.environ["LOG_LEVEL"] = "ERROR"


def run() -> None:
    """Run the CLI application."""
    app()


if __name__ == "__main__":
    run()
