"""Channel management commands.

Provides commands for:
- Listing available channels
- Enabling/disabling channels
- Channel-specific configuration
- Channel status and health checks
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

channels_app = typer.Typer(
    name="channels",
    help="Channel plugin management",
    no_args_is_help=True,
)

console = Console()


@channels_app.command("list")
def list_channels(
    all_channels: bool = typer.Option(False, "--all", "-a", help="Show all channels including disabled"),
    category: str = typer.Option(None, "--category", "-c", help="Filter by category"),
) -> None:
    """List available channel plugins.

    Shows all registered channels with their status and capabilities.

    Examples:
        clara channels list             # Show enabled channels
        clara channels list --all       # Show all channels
        clara channels list -c messaging  # Filter by category
    """
    from clara_core.channels import get_channel_registry

    registry = get_channel_registry()
    channels = registry.get_all()

    if category:
        channels = [c for c in channels if c.meta.category == category]

    if not all_channels:
        channels = [c for c in channels if registry.is_running(c.id)]

    if not channels:
        console.print("[yellow]No channels found[/yellow]")
        if not all_channels:
            console.print("Use --all to see disabled channels")
        return

    table = Table(title="Channels")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Category", style="blue")
    table.add_column("Status", style="yellow")
    table.add_column("Capabilities", style="dim")

    for channel in channels:
        # Build capabilities string
        caps = []
        if channel.capabilities.streaming:
            caps.append("streaming")
        if channel.capabilities.threading:
            caps.append("threading")
        if channel.capabilities.embeds:
            caps.append("embeds")
        if channel.capabilities.attachments:
            caps.append("files")

        status = "Running" if registry.is_running(channel.id) else "Stopped"
        status_style = "green" if registry.is_running(channel.id) else "dim"

        table.add_row(
            str(channel.id.value) if hasattr(channel.id, "value") else str(channel.id),
            channel.meta.name,
            channel.meta.category,
            f"[{status_style}]{status}[/{status_style}]",
            ", ".join(caps) if caps else "basic",
        )

    console.print(table)


@channels_app.command("status")
def channel_status(
    channel_id: str = typer.Argument(..., help="Channel ID to check"),
) -> None:
    """Show detailed status for a channel.

    Examples:
        clara channels status discord
        clara channels status telegram
    """
    from clara_core.channels import get_channel_registry

    registry = get_channel_registry()
    channel = registry.get(channel_id)

    if not channel:
        console.print(f"[red]Channel not found: {channel_id}[/red]")
        raise typer.Exit(1)

    # Build status panel
    is_running = registry.is_running(channel.id)
    status_color = "green" if is_running else "red"
    status_text = "Running" if is_running else "Stopped"

    info = [
        f"[bold]Name:[/bold] {channel.meta.name}",
        f"[bold]Description:[/bold] {channel.meta.description}",
        f"[bold]Category:[/bold] {channel.meta.category}",
        f"[bold]Version:[/bold] {channel.meta.version}",
        f"[bold]Type:[/bold] {'Core' if channel.meta.is_core else 'Extension'}",
        f"[bold]Status:[/bold] [{status_color}]{status_text}[/{status_color}]",
    ]

    console.print(Panel(
        "\n".join(info),
        title=f"Channel: {channel_id}",
        border_style="blue",
    ))

    # Capabilities table
    caps_table = Table(title="Capabilities")
    caps_table.add_column("Feature", style="cyan")
    caps_table.add_column("Supported", style="green")

    caps = channel.capabilities
    caps_table.add_row("Streaming", "Yes" if caps.streaming else "No")
    caps_table.add_row("Threading", "Yes" if caps.threading else "No")
    caps_table.add_row("Reactions", "Yes" if caps.reactions else "No")
    caps_table.add_row("Attachments", "Yes" if caps.attachments else "No")
    caps_table.add_row("Images", "Yes" if caps.images else "No")
    caps_table.add_row("Embeds", "Yes" if caps.embeds else "No")
    caps_table.add_row("Components", "Yes" if caps.components else "No")
    caps_table.add_row("Slash Commands", "Yes" if caps.slash_commands else "No")
    caps_table.add_row("Typing Indicator", "Yes" if caps.typing_indicator else "No")
    caps_table.add_row("Edit Messages", "Yes" if caps.edit else "No")
    caps_table.add_row("Delete Messages", "Yes" if caps.delete else "No")

    if caps.max_message_length > 0:
        caps_table.add_row("Max Message Length", str(caps.max_message_length))

    console.print(caps_table)

    # Get live status if running
    if is_running and channel.status:
        import asyncio
        try:
            status = asyncio.run(channel.status.get_status())
            console.print("\n[bold]Live Status:[/bold]")
            console.print(f"  Connected: {status.is_connected}")
            console.print(f"  Healthy: {status.is_healthy}")
            if status.latency_ms:
                console.print(f"  Latency: {status.latency_ms}ms")
            if status.last_message_at:
                console.print(f"  Last Message: {status.last_message_at}")
            if status.error:
                console.print(f"  [red]Error: {status.error}[/red]")
        except Exception as e:
            console.print(f"[yellow]Could not get live status: {e}[/yellow]")


@channels_app.command("start")
def start_channel(
    channel_id: str = typer.Argument(..., help="Channel ID to start"),
) -> None:
    """Start a channel adapter.

    Connects the channel to the gateway and begins processing messages.

    Examples:
        clara channels start discord
    """
    import asyncio

    from clara_core.channels import get_channel_registry

    registry = get_channel_registry()
    channel = registry.get(channel_id)

    if not channel:
        console.print(f"[red]Channel not found: {channel_id}[/red]")
        raise typer.Exit(1)

    if registry.is_running(channel.id):
        console.print(f"[yellow]Channel {channel_id} is already running[/yellow]")
        return

    console.print(f"[blue]Starting channel {channel_id}...[/blue]")

    try:
        success = asyncio.run(registry.start_channel(channel_id))
        if success:
            console.print(f"[green]Channel {channel_id} started[/green]")
        else:
            console.print(f"[red]Failed to start channel {channel_id}[/red]")
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error starting channel: {e}[/red]")
        raise typer.Exit(1)


@channels_app.command("stop")
def stop_channel(
    channel_id: str = typer.Argument(..., help="Channel ID to stop"),
) -> None:
    """Stop a channel adapter.

    Disconnects the channel from the gateway.

    Examples:
        clara channels stop discord
    """
    import asyncio

    from clara_core.channels import get_channel_registry

    registry = get_channel_registry()
    channel = registry.get(channel_id)

    if not channel:
        console.print(f"[red]Channel not found: {channel_id}[/red]")
        raise typer.Exit(1)

    if not registry.is_running(channel.id):
        console.print(f"[yellow]Channel {channel_id} is not running[/yellow]")
        return

    console.print(f"[blue]Stopping channel {channel_id}...[/blue]")

    try:
        success = asyncio.run(registry.stop_channel(channel_id))
        if success:
            console.print(f"[green]Channel {channel_id} stopped[/green]")
        else:
            console.print(f"[yellow]Channel {channel_id} may not have stopped cleanly[/yellow]")
    except Exception as e:
        console.print(f"[red]Error stopping channel: {e}[/red]")


@channels_app.command("setup")
def setup_channel(
    channel_id: str = typer.Argument(..., help="Channel ID to set up"),
) -> None:
    """Run interactive setup for a channel.

    Guides you through the configuration process for the channel,
    including credential setup and connection testing.

    Examples:
        clara channels setup discord
        clara channels setup telegram
    """
    from clara_core.channels import get_channel_registry

    registry = get_channel_registry()
    channel = registry.get(channel_id)

    if not channel:
        console.print(f"[red]Channel not found: {channel_id}[/red]")
        console.print("\nAvailable channels:")
        for c in registry.get_all():
            cid = str(c.id.value) if hasattr(c.id, "value") else str(c.id)
            console.print(f"  - {cid}: {c.meta.name}")
        raise typer.Exit(1)

    if not channel.setup:
        console.print(f"[yellow]Channel {channel_id} does not have a setup wizard[/yellow]")
        console.print("Check the documentation for manual setup instructions.")
        return

    console.print(Panel(
        f"[bold]Setting up {channel.meta.name}[/bold]\n\n"
        f"{channel.meta.description}\n\n"
        "Follow the prompts to configure this channel.",
        title="Channel Setup",
        border_style="blue",
    ))

    import asyncio
    try:
        success = asyncio.run(channel.setup.run_setup())
        if success:
            console.print(f"[green]Setup complete for {channel_id}![/green]")
        else:
            console.print(f"[red]Setup failed for {channel_id}[/red]")
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Setup error: {e}[/red]")
        raise typer.Exit(1)


@channels_app.command("test")
def test_channel(
    channel_id: str = typer.Argument(..., help="Channel ID to test"),
) -> None:
    """Test channel connectivity and health.

    Runs a health check on the channel to verify it's working correctly.

    Examples:
        clara channels test discord
    """
    from clara_core.channels import get_channel_registry

    registry = get_channel_registry()
    channel = registry.get(channel_id)

    if not channel:
        console.print(f"[red]Channel not found: {channel_id}[/red]")
        raise typer.Exit(1)

    if not channel.status:
        console.print(f"[yellow]Channel {channel_id} does not support health checks[/yellow]")
        return

    console.print(f"[blue]Testing channel {channel_id}...[/blue]")

    import asyncio
    try:
        healthy, message = asyncio.run(channel.status.run_health_check())
        if healthy:
            console.print(f"[green]Channel is healthy: {message}[/green]")
        else:
            console.print(f"[red]Channel unhealthy: {message}[/red]")
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Health check failed: {e}[/red]")
        raise typer.Exit(1)
