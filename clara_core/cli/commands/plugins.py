"""Plugin management commands.

Provides commands for:
- Listing installed plugins
- Installing/uninstalling plugins
- Enabling/disabling plugins
- Plugin information and status
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

plugins_app = typer.Typer(
    name="plugins",
    help="Extension plugin management",
    no_args_is_help=True,
)

console = Console()


@plugins_app.command("list")
def list_plugins(
    all_plugins: bool = typer.Option(False, "--all", "-a", help="Show all plugins including disabled"),
    category: str = typer.Option(None, "--category", "-c", help="Filter by category"),
) -> None:
    """List installed plugins.

    Shows all registered plugins with their status and hooks.

    Examples:
        clara plugins list             # Show enabled plugins
        clara plugins list --all       # Show all plugins
        clara plugins list -c tools    # Filter by category
    """
    from clara_core.plugins import get_plugin_manager

    manager = get_plugin_manager()
    plugins = manager.get_all()

    if category:
        plugins = [p for p in plugins if p.meta.category == category]

    if not all_plugins:
        plugins = [p for p in plugins if p.enabled]

    if not plugins:
        console.print("[yellow]No plugins found[/yellow]")
        if not all_plugins:
            console.print("Use --all to see disabled plugins")
        return

    table = Table(title="Plugins")
    table.add_column("Name", style="cyan")
    table.add_column("Version", style="green")
    table.add_column("Category", style="blue")
    table.add_column("Status", style="yellow")
    table.add_column("Hooks", style="dim")

    for plugin in plugins:
        status = "Enabled" if plugin.enabled else "Disabled"
        status_style = "green" if plugin.enabled else "dim"

        # Count registered hooks
        hook_count = len(plugin.hooks) if hasattr(plugin, "hooks") else 0

        table.add_row(
            plugin.meta.name,
            plugin.meta.version,
            plugin.meta.category or "general",
            f"[{status_style}]{status}[/{status_style}]",
            str(hook_count),
        )

    console.print(table)


@plugins_app.command("info")
def plugin_info(
    plugin_name: str = typer.Argument(..., help="Plugin name to inspect"),
) -> None:
    """Show detailed information about a plugin.

    Examples:
        clara plugins info memory-tools
        clara plugins info mcp-bridge
    """
    from clara_core.plugins import get_plugin_manager

    manager = get_plugin_manager()
    plugin = manager.get(plugin_name)

    if not plugin:
        console.print(f"[red]Plugin not found: {plugin_name}[/red]")
        raise typer.Exit(1)

    # Build info panel
    status_color = "green" if plugin.enabled else "red"
    status_text = "Enabled" if plugin.enabled else "Disabled"

    info = [
        f"[bold]Name:[/bold] {plugin.meta.name}",
        f"[bold]Description:[/bold] {plugin.meta.description}",
        f"[bold]Version:[/bold] {plugin.meta.version}",
        f"[bold]Author:[/bold] {plugin.meta.author or 'Unknown'}",
        f"[bold]Category:[/bold] {plugin.meta.category or 'general'}",
        f"[bold]Status:[/bold] [{status_color}]{status_text}[/{status_color}]",
    ]

    if plugin.meta.homepage:
        info.append(f"[bold]Homepage:[/bold] {plugin.meta.homepage}")

    console.print(Panel(
        "\n".join(info),
        title=f"Plugin: {plugin_name}",
        border_style="blue",
    ))

    # Show registered hooks
    if hasattr(plugin, "hooks") and plugin.hooks:
        hooks_table = Table(title="Registered Hooks")
        hooks_table.add_column("Hook", style="cyan")
        hooks_table.add_column("Priority", style="green")

        for hook_name, handlers in plugin.hooks.items():
            for handler in handlers:
                priority = getattr(handler, "priority", 0)
                hooks_table.add_row(hook_name, str(priority))

        console.print(hooks_table)

    # Show registered tools
    if hasattr(plugin, "tools") and plugin.tools:
        tools_table = Table(title="Registered Tools")
        tools_table.add_column("Tool", style="cyan")
        tools_table.add_column("Description", style="dim")

        for tool in plugin.tools:
            tools_table.add_row(
                tool.name,
                tool.description[:60] + "..." if len(tool.description) > 60 else tool.description,
            )

        console.print(tools_table)


@plugins_app.command("enable")
def enable_plugin(
    plugin_name: str = typer.Argument(..., help="Plugin name to enable"),
) -> None:
    """Enable a disabled plugin.

    Examples:
        clara plugins enable memory-tools
    """
    from clara_core.plugins import get_plugin_manager

    manager = get_plugin_manager()
    plugin = manager.get(plugin_name)

    if not plugin:
        console.print(f"[red]Plugin not found: {plugin_name}[/red]")
        raise typer.Exit(1)

    if plugin.enabled:
        console.print(f"[yellow]Plugin {plugin_name} is already enabled[/yellow]")
        return

    try:
        manager.enable(plugin_name)
        console.print(f"[green]Plugin {plugin_name} enabled[/green]")
    except Exception as e:
        console.print(f"[red]Failed to enable plugin: {e}[/red]")
        raise typer.Exit(1)


@plugins_app.command("disable")
def disable_plugin(
    plugin_name: str = typer.Argument(..., help="Plugin name to disable"),
) -> None:
    """Disable an enabled plugin.

    Examples:
        clara plugins disable memory-tools
    """
    from clara_core.plugins import get_plugin_manager

    manager = get_plugin_manager()
    plugin = manager.get(plugin_name)

    if not plugin:
        console.print(f"[red]Plugin not found: {plugin_name}[/red]")
        raise typer.Exit(1)

    if not plugin.enabled:
        console.print(f"[yellow]Plugin {plugin_name} is already disabled[/yellow]")
        return

    try:
        manager.disable(plugin_name)
        console.print(f"[green]Plugin {plugin_name} disabled[/green]")
    except Exception as e:
        console.print(f"[red]Failed to disable plugin: {e}[/red]")
        raise typer.Exit(1)


@plugins_app.command("install")
def install_plugin(
    source: str = typer.Argument(..., help="Plugin source (path, git URL, or package name)"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Override plugin name"),
) -> None:
    """Install a plugin from a source.

    Sources can be:
    - Local path: /path/to/plugin
    - Git URL: https://github.com/user/clara-plugin
    - Package name: clara-plugin-memory

    Examples:
        clara plugins install /path/to/my-plugin
        clara plugins install https://github.com/user/clara-plugin
        clara plugins install clara-plugin-memory
    """
    from clara_core.plugins import get_plugin_manager

    manager = get_plugin_manager()

    console.print(f"[blue]Installing plugin from {source}...[/blue]")

    try:
        plugin = manager.install(source, name=name)
        console.print(f"[green]Plugin {plugin.meta.name} installed successfully[/green]")
        console.print(f"Version: {plugin.meta.version}")
        if plugin.meta.description:
            console.print(f"Description: {plugin.meta.description}")
    except Exception as e:
        console.print(f"[red]Failed to install plugin: {e}[/red]")
        raise typer.Exit(1)


@plugins_app.command("uninstall")
def uninstall_plugin(
    plugin_name: str = typer.Argument(..., help="Plugin name to uninstall"),
    force: bool = typer.Option(False, "--force", "-f", help="Force uninstall without confirmation"),
) -> None:
    """Uninstall a plugin.

    Examples:
        clara plugins uninstall memory-tools
        clara plugins uninstall memory-tools --force
    """
    from clara_core.plugins import get_plugin_manager

    manager = get_plugin_manager()
    plugin = manager.get(plugin_name)

    if not plugin:
        console.print(f"[red]Plugin not found: {plugin_name}[/red]")
        raise typer.Exit(1)

    if plugin.meta.is_core:
        console.print(f"[red]Cannot uninstall core plugin: {plugin_name}[/red]")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(f"Are you sure you want to uninstall {plugin_name}?")
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            return

    try:
        manager.uninstall(plugin_name)
        console.print(f"[green]Plugin {plugin_name} uninstalled[/green]")
    except Exception as e:
        console.print(f"[red]Failed to uninstall plugin: {e}[/red]")
        raise typer.Exit(1)


@plugins_app.command("reload")
def reload_plugin(
    plugin_name: str = typer.Argument(..., help="Plugin name to reload"),
) -> None:
    """Reload a plugin.

    Useful after making changes to plugin code.

    Examples:
        clara plugins reload memory-tools
    """
    from clara_core.plugins import get_plugin_manager

    manager = get_plugin_manager()
    plugin = manager.get(plugin_name)

    if not plugin:
        console.print(f"[red]Plugin not found: {plugin_name}[/red]")
        raise typer.Exit(1)

    console.print(f"[blue]Reloading plugin {plugin_name}...[/blue]")

    try:
        manager.reload(plugin_name)
        console.print(f"[green]Plugin {plugin_name} reloaded[/green]")
    except Exception as e:
        console.print(f"[red]Failed to reload plugin: {e}[/red]")
        raise typer.Exit(1)


@plugins_app.command("search")
def search_plugins(
    query: str = typer.Argument(..., help="Search query"),
) -> None:
    """Search for available plugins.

    Searches the Clara plugin registry for available plugins.

    Examples:
        clara plugins search memory
        clara plugins search mcp
    """
    console.print(f"[blue]Searching for plugins matching '{query}'...[/blue]")

    # TODO: Implement plugin registry search
    console.print("[yellow]Plugin registry search not yet implemented[/yellow]")
    console.print("For now, install plugins directly from:")
    console.print("  - Local paths")
    console.print("  - Git URLs")
    console.print("  - Package names")
