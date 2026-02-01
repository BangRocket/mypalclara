"""Gateway management commands.

Provides commands for:
- Starting/stopping the gateway server
- Checking gateway status
- Managing connected adapters
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

gateway_app = typer.Typer(
    name="gateway",
    help="Gateway server management",
    no_args_is_help=True,
)

console = Console()

# PID file for daemon mode
PID_FILE = Path.home() / ".clara" / "gateway.pid"


def _get_pid() -> int | None:
    """Get the gateway PID if running."""
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            # Check if process exists
            os.kill(pid, 0)
            return pid
        except (ValueError, ProcessLookupError, PermissionError):
            PID_FILE.unlink(missing_ok=True)
    return None


def _save_pid(pid: int) -> None:
    """Save the gateway PID."""
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(pid))


def _remove_pid() -> None:
    """Remove the PID file."""
    PID_FILE.unlink(missing_ok=True)


@gateway_app.command("start")
def start_gateway(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Bind address"),
    port: int = typer.Option(18789, "--port", "-p", help="Port number"),
    detach: bool = typer.Option(False, "--detach", "-d", help="Run in background"),
) -> None:
    """Start the Clara gateway server.

    The gateway is the central hub that:
    - Accepts WebSocket connections from channel adapters
    - Processes messages through the LLM
    - Executes tools and manages plugins
    - Coordinates response streaming

    Examples:
        clara gateway start                 # Start on localhost:18789
        clara gateway start -p 8080         # Start on port 8080
        clara gateway start --detach        # Run as daemon
    """
    # Check if already running
    existing_pid = _get_pid()
    if existing_pid:
        console.print(f"[yellow]Gateway already running (PID {existing_pid})[/yellow]")
        console.print("Use 'clara gateway stop' to stop it first.")
        raise typer.Exit(1)

    if detach:
        # Fork and run in background
        console.print(f"[blue]Starting gateway in background on {host}:{port}...[/blue]")

        pid = os.fork()
        if pid > 0:
            # Parent process
            _save_pid(pid)
            console.print(f"[green]Gateway started (PID {pid})[/green]")
            console.print(f"Listening on ws://{host}:{port}")
            return

        # Child process - become daemon
        os.setsid()
        sys.stdin.close()

        # Redirect stdout/stderr to log file
        log_file = Path.home() / ".clara" / "gateway.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        sys.stdout = open(log_file, "a")
        sys.stderr = sys.stdout

    else:
        console.print(Panel(
            f"[bold blue]Clara Gateway[/bold blue]\n\n"
            f"Listening on [green]ws://{host}:{port}[/green]\n"
            f"Press [bold]Ctrl+C[/bold] to stop",
            title="Starting Gateway",
            border_style="blue",
        ))

    # Run the gateway
    try:
        from gateway.server import GatewayServer

        server = GatewayServer(host=host, port=port)

        async def run():
            await server.start()
            await server.serve_forever()

        asyncio.run(run())

    except KeyboardInterrupt:
        console.print("\n[yellow]Gateway stopped[/yellow]")
    finally:
        _remove_pid()


@gateway_app.command("stop")
def stop_gateway(
    force: bool = typer.Option(False, "--force", "-f", help="Force kill"),
) -> None:
    """Stop the Clara gateway server.

    Examples:
        clara gateway stop          # Graceful shutdown
        clara gateway stop --force  # Force kill
    """
    pid = _get_pid()
    if not pid:
        console.print("[yellow]Gateway is not running[/yellow]")
        return

    console.print(f"[blue]Stopping gateway (PID {pid})...[/blue]")

    try:
        sig = signal.SIGKILL if force else signal.SIGTERM
        os.kill(pid, sig)
        console.print("[green]Gateway stopped[/green]")
    except ProcessLookupError:
        console.print("[yellow]Gateway process not found[/yellow]")
    finally:
        _remove_pid()


@gateway_app.command("status")
def gateway_status() -> None:
    """Show gateway server status.

    Displays:
    - Running state
    - Connected adapters
    - Queue statistics
    - Uptime
    """
    pid = _get_pid()

    if not pid:
        console.print(Panel(
            "[red]Gateway is not running[/red]\n\n"
            "Start with: [bold]clara gateway start[/bold]",
            title="Gateway Status",
            border_style="red",
        ))
        return

    # Try to connect and get status
    gateway_url = os.getenv("CLARA_GATEWAY_URL", "ws://127.0.0.1:18789")

    table = Table(title="Gateway Status")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Status", "Running")
    table.add_row("PID", str(pid))
    table.add_row("URL", gateway_url)

    # Try to get live stats
    try:
        import websockets.sync.client as ws_client

        with ws_client.connect(gateway_url, close_timeout=2) as websocket:
            import json
            websocket.send(json.dumps({"type": "status"}))
            response = json.loads(websocket.recv())

            if response.get("type") == "status":
                table.add_row("Active Requests", str(response.get("active_requests", 0)))
                table.add_row("Queue Length", str(response.get("queue_length", 0)))
                uptime = response.get("uptime_seconds")
                if uptime:
                    hours, remainder = divmod(uptime, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    table.add_row("Uptime", f"{int(hours)}h {int(minutes)}m {int(seconds)}s")

    except Exception as e:
        table.add_row("Stats", f"[yellow]Unable to fetch ({e})[/yellow]")

    console.print(table)


@gateway_app.command("logs")
def gateway_logs(
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    lines: int = typer.Option(50, "--lines", "-n", help="Number of lines to show"),
) -> None:
    """Show gateway logs.

    Examples:
        clara gateway logs              # Show last 50 lines
        clara gateway logs -n 100       # Show last 100 lines
        clara gateway logs --follow     # Follow live logs
    """
    log_file = Path.home() / ".clara" / "gateway.log"

    if not log_file.exists():
        console.print("[yellow]No log file found[/yellow]")
        console.print(f"Expected at: {log_file}")
        return

    if follow:
        console.print(f"[blue]Following {log_file}...[/blue]")
        console.print("[dim]Press Ctrl+C to stop[/dim]\n")

        import subprocess
        try:
            subprocess.run(["tail", "-f", str(log_file)])
        except KeyboardInterrupt:
            pass
    else:
        # Read last N lines
        with open(log_file) as f:
            all_lines = f.readlines()
            for line in all_lines[-lines:]:
                console.print(line.rstrip())


@gateway_app.command("adapters")
def list_adapters() -> None:
    """List connected channel adapters.

    Shows all adapters currently connected to the gateway.
    """
    gateway_url = os.getenv("CLARA_GATEWAY_URL", "ws://127.0.0.1:18789")

    table = Table(title="Connected Adapters")
    table.add_column("Node ID", style="cyan")
    table.add_column("Platform", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Connected", style="dim")

    try:
        import json

        import websockets.sync.client as ws_client

        with ws_client.connect(gateway_url, close_timeout=2) as websocket:
            websocket.send(json.dumps({"type": "status"}))
            response = json.loads(websocket.recv())

            adapters = response.get("adapters", [])
            if not adapters:
                console.print("[yellow]No adapters connected[/yellow]")
                return

            for adapter in adapters:
                table.add_row(
                    adapter.get("node_id", "unknown"),
                    adapter.get("platform", "unknown"),
                    adapter.get("status", "unknown"),
                    adapter.get("connected_at", "unknown"),
                )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Failed to connect to gateway: {e}[/red]")
        console.print("Make sure the gateway is running.")
