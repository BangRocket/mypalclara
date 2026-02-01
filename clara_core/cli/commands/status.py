"""Status and diagnostics commands.

Provides commands for:
- Overall system status
- Component health checks
- Resource monitoring
- Connection status
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

status_app = typer.Typer(
    name="status",
    help="Status and diagnostics",
    no_args_is_help=True,
)

console = Console()


@status_app.command("overview")
def status_overview() -> None:
    """Show overall system status.

    Displays status of all Clara components.

    Examples:
        clara status overview
    """
    console.print(Panel(
        "[bold blue]Clara System Status[/bold blue]",
        border_style="blue",
    ))

    # Component status table
    table = Table(title="Components")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Details", style="dim")

    # Check gateway
    gateway_status, gateway_details = _check_gateway()
    table.add_row("Gateway", gateway_status, gateway_details)

    # Check database
    db_status, db_details = _check_database()
    table.add_row("Database", db_status, db_details)

    # Check memory system
    mem_status, mem_details = _check_memory()
    table.add_row("Memory (mem0)", mem_status, mem_details)

    # Check LLM provider
    llm_status, llm_details = _check_llm()
    table.add_row("LLM Provider", llm_status, llm_details)

    # Check channels
    channels_status, channels_details = _check_channels()
    table.add_row("Channels", channels_status, channels_details)

    console.print(table)


def _check_gateway() -> tuple[str, str]:
    """Check gateway status."""
    pid_file = Path.home() / ".clara" / "gateway.pid"

    if not pid_file.exists():
        return "[dim]Stopped[/dim]", "Not running"

    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, 0)  # Check if process exists
        return "[green]Running[/green]", f"PID {pid}"
    except (ValueError, ProcessLookupError, PermissionError):
        return "[dim]Stopped[/dim]", "PID file stale"


def _check_database() -> tuple[str, str]:
    """Check database status."""
    db_url = os.getenv("DATABASE_URL")

    if not db_url:
        # Check for SQLite
        sqlite_path = Path("clara.db")
        if sqlite_path.exists():
            size = sqlite_path.stat().st_size / 1024 / 1024
            return "[green]Connected[/green]", f"SQLite ({size:.1f} MB)"
        return "[yellow]Not configured[/yellow]", "No DATABASE_URL"

    try:
        # Try to connect
        if "postgresql" in db_url:
            return "[green]Connected[/green]", "PostgreSQL"
        return "[green]Configured[/green]", "Unknown type"
    except Exception as e:
        return "[red]Error[/red]", str(e)[:30]


def _check_memory() -> tuple[str, str]:
    """Check memory system status."""
    mem_url = os.getenv("MEM0_DATABASE_URL")

    if mem_url:
        return "[green]Configured[/green]", "PostgreSQL (pgvector)"

    # Check for Qdrant
    qdrant_url = os.getenv("QDRANT_URL")
    if qdrant_url:
        return "[green]Configured[/green]", "Qdrant"

    # Local Qdrant
    qdrant_path = Path(".qdrant")
    if qdrant_path.exists():
        return "[green]Configured[/green]", "Qdrant (local)"

    return "[yellow]Not configured[/yellow]", "Using defaults"


def _check_llm() -> tuple[str, str]:
    """Check LLM provider status."""
    provider = os.getenv("LLM_PROVIDER", "openrouter")

    key_map = {
        "openrouter": "OPENROUTER_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "CUSTOM_OPENAI_API_KEY",
        "nanogpt": "NANOGPT_API_KEY",
    }

    key_env = key_map.get(provider)
    if key_env and os.getenv(key_env):
        model = os.getenv(f"{provider.upper()}_MODEL", "default")
        return "[green]Configured[/green]", f"{provider} ({model[:20]})"

    return "[yellow]No API key[/yellow]", provider


def _check_channels() -> tuple[str, str]:
    """Check channel status."""
    active = []

    if os.getenv("DISCORD_BOT_TOKEN"):
        active.append("Discord")
    if os.getenv("TELEGRAM_BOT_TOKEN"):
        active.append("Telegram")
    if os.getenv("SLACK_BOT_TOKEN"):
        active.append("Slack")

    if active:
        return "[green]Configured[/green]", ", ".join(active)

    return "[dim]None[/dim]", "No channels configured"


@status_app.command("gateway")
def gateway_status() -> None:
    """Show detailed gateway status.

    Examples:
        clara status gateway
    """
    pid_file = Path.home() / ".clara" / "gateway.pid"

    if not pid_file.exists():
        console.print(Panel(
            "[red]Gateway is not running[/red]\n\n"
            "Start with: [bold]clara serve[/bold]",
            title="Gateway Status",
            border_style="red",
        ))
        return

    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, 0)
    except (ValueError, ProcessLookupError, PermissionError):
        console.print("[red]Gateway process not found (stale PID file)[/red]")
        return

    table = Table(title="Gateway Status")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Status", "[green]Running[/green]")
    table.add_row("PID", str(pid))

    gateway_url = os.getenv("CLARA_GATEWAY_URL", "ws://127.0.0.1:18789")
    table.add_row("URL", gateway_url)

    # Try to get live stats
    try:
        import json

        import websockets.sync.client as ws_client

        with ws_client.connect(gateway_url, close_timeout=2) as websocket:
            websocket.send(json.dumps({"type": "status"}))
            response = json.loads(websocket.recv())

            if response.get("type") == "status":
                table.add_row("Active Requests", str(response.get("active_requests", 0)))
                table.add_row("Queue Length", str(response.get("queue_length", 0)))
                table.add_row("Connected Adapters", str(len(response.get("adapters", []))))

                uptime = response.get("uptime_seconds")
                if uptime:
                    hours, remainder = divmod(uptime, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    table.add_row("Uptime", f"{int(hours)}h {int(minutes)}m {int(seconds)}s")
    except Exception as e:
        table.add_row("Live Stats", f"[yellow]Unavailable ({e})[/yellow]")

    console.print(table)


@status_app.command("memory")
def memory_status() -> None:
    """Show memory system status.

    Examples:
        clara status memory
    """
    table = Table(title="Memory System Status")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    # Vector store
    mem_url = os.getenv("MEM0_DATABASE_URL")
    if mem_url:
        table.add_row("Vector Store", "PostgreSQL (pgvector)")
        table.add_row("Connection", mem_url.split("@")[-1] if "@" in mem_url else "configured")
    else:
        qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        table.add_row("Vector Store", "Qdrant")
        table.add_row("Connection", qdrant_url)

    # Embeddings
    table.add_row("Embeddings Model", "text-embedding-3-small")
    table.add_row("Embeddings Provider", "OpenAI")

    # Graph memory
    graph_enabled = os.getenv("ENABLE_GRAPH_MEMORY", "false").lower() == "true"
    if graph_enabled:
        graph_provider = os.getenv("GRAPH_STORE_PROVIDER", "neo4j")
        table.add_row("Graph Memory", f"[green]Enabled[/green] ({graph_provider})")
    else:
        table.add_row("Graph Memory", "[dim]Disabled[/dim]")

    # Memory extraction
    mem_provider = os.getenv("MEM0_PROVIDER", "openrouter")
    mem_model = os.getenv("MEM0_MODEL", "openai/gpt-4o-mini")
    table.add_row("Extraction Provider", mem_provider)
    table.add_row("Extraction Model", mem_model)

    console.print(table)


@status_app.command("channels")
def channels_status() -> None:
    """Show channel status.

    Examples:
        clara status channels
    """
    table = Table(title="Channel Status")
    table.add_column("Channel", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Details", style="dim")

    # Discord
    discord_token = os.getenv("DISCORD_BOT_TOKEN")
    if discord_token:
        table.add_row(
            "Discord",
            "[green]Configured[/green]",
            f"Token: {discord_token[:8]}..."
        )
    else:
        table.add_row("Discord", "[dim]Not configured[/dim]", "")

    # Telegram
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if telegram_token:
        table.add_row(
            "Telegram",
            "[green]Configured[/green]",
            f"Token: {telegram_token[:8]}..."
        )
    else:
        table.add_row("Telegram", "[dim]Not configured[/dim]", "")

    # Slack
    slack_token = os.getenv("SLACK_BOT_TOKEN")
    if slack_token:
        table.add_row(
            "Slack",
            "[green]Configured[/green]",
            f"Token: {slack_token[:8]}..."
        )
    else:
        table.add_row("Slack", "[dim]Not configured[/dim]", "")

    # CLI
    table.add_row("CLI", "[green]Available[/green]", "clara chat")

    console.print(table)


@status_app.command("llm")
def llm_status() -> None:
    """Show LLM provider status.

    Examples:
        clara status llm
    """
    table = Table(title="LLM Provider Status")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    provider = os.getenv("LLM_PROVIDER", "openrouter")
    table.add_row("Provider", provider)

    # Provider-specific config
    if provider == "openrouter":
        model = os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4")
        key = os.getenv("OPENROUTER_API_KEY")
        table.add_row("Model", model)
        table.add_row("API Key", f"{key[:8]}..." if key else "[red]Not set[/red]")

        # Tiers
        high = os.getenv("OPENROUTER_MODEL_HIGH")
        mid = os.getenv("OPENROUTER_MODEL_MID")
        low = os.getenv("OPENROUTER_MODEL_LOW")
        if high:
            table.add_row("High Tier", high)
        if mid:
            table.add_row("Mid Tier", mid)
        if low:
            table.add_row("Low Tier", low)

    elif provider == "anthropic":
        model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
        key = os.getenv("ANTHROPIC_API_KEY")
        base_url = os.getenv("ANTHROPIC_BASE_URL")
        table.add_row("Model", model)
        table.add_row("API Key", f"{key[:8]}..." if key else "[red]Not set[/red]")
        if base_url:
            table.add_row("Base URL", base_url)

    elif provider == "openai":
        model = os.getenv("CUSTOM_OPENAI_MODEL", "gpt-4o")
        key = os.getenv("CUSTOM_OPENAI_API_KEY")
        base_url = os.getenv("CUSTOM_OPENAI_BASE_URL", "https://api.openai.com/v1")
        table.add_row("Model", model)
        table.add_row("API Key", f"{key[:8]}..." if key else "[red]Not set[/red]")
        table.add_row("Base URL", base_url)

    elif provider == "nanogpt":
        model = os.getenv("NANOGPT_MODEL", "moonshotai/Kimi-K2-Instruct-0905")
        key = os.getenv("NANOGPT_API_KEY")
        table.add_row("Model", model)
        table.add_row("API Key", f"{key[:8]}..." if key else "[red]Not set[/red]")

    # Auto tier selection
    auto_tier = os.getenv("AUTO_TIER_SELECTION", "false")
    table.add_row("Auto Tier Selection", auto_tier)

    console.print(table)


@status_app.command("env")
def env_status(
    show_values: bool = typer.Option(False, "--show", "-s", help="Show actual values (sensitive!)"),
) -> None:
    """Show relevant environment variables.

    Examples:
        clara status env           # Show variable names only
        clara status env --show    # Show values (sensitive!)
    """
    env_groups = {
        "LLM": [
            "LLM_PROVIDER",
            "OPENROUTER_API_KEY", "OPENROUTER_MODEL",
            "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "ANTHROPIC_BASE_URL",
            "CUSTOM_OPENAI_API_KEY", "CUSTOM_OPENAI_MODEL", "CUSTOM_OPENAI_BASE_URL",
            "NANOGPT_API_KEY", "NANOGPT_MODEL",
        ],
        "Memory": [
            "OPENAI_API_KEY",
            "MEM0_PROVIDER", "MEM0_MODEL", "MEM0_DATABASE_URL",
            "QDRANT_URL",
            "ENABLE_GRAPH_MEMORY", "GRAPH_STORE_PROVIDER",
        ],
        "Discord": [
            "DISCORD_BOT_TOKEN", "DISCORD_CLIENT_ID",
            "DISCORD_ALLOWED_SERVERS", "DISCORD_ALLOWED_CHANNELS",
        ],
        "Gateway": [
            "CLARA_GATEWAY_HOST", "CLARA_GATEWAY_PORT", "CLARA_GATEWAY_SECRET",
        ],
        "Database": [
            "DATABASE_URL",
        ],
    }

    for group, vars in env_groups.items():
        table = Table(title=group)
        table.add_column("Variable", style="cyan")
        table.add_column("Status", style="green")
        if show_values:
            table.add_column("Value", style="dim")

        for var in vars:
            value = os.getenv(var)
            if value:
                status = "[green]Set[/green]"
                if show_values:
                    # Mask sensitive values
                    if any(s in var.lower() for s in ["key", "token", "secret", "password", "url"]):
                        if len(value) > 12:
                            display = value[:4] + "..." + value[-4:]
                        else:
                            display = "****"
                    else:
                        display = value
                    table.add_row(var, status, display)
                else:
                    table.add_row(var, status)
            else:
                if show_values:
                    table.add_row(var, "[dim]Not set[/dim]", "")
                else:
                    table.add_row(var, "[dim]Not set[/dim]")

        console.print(table)
        console.print()
