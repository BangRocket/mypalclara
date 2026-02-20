"""Command parser and dispatch for CLI !commands.

Handles all !-prefixed commands before they reach the gateway.
Tier prefixes (!high, !mid, !low, etc.) are passed through.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from mypalclara.config.logging import get_logger

if TYPE_CHECKING:
    from prompt_toolkit import PromptSession

    from mypalclara.adapters.cli.gateway_client import CLIGatewayClient

logger = get_logger("adapters.cli.commands")

# Tier prefixes that should pass through to the gateway
TIER_PREFIXES = {"!high", "!opus", "!mid", "!sonnet", "!low", "!haiku", "!fast"}


@dataclass
class CommandResult:
    """Result of command dispatch."""

    handled: bool = False
    output: Any | None = None
    error: str | None = None


class CommandDispatcher:
    """Dispatches !commands to their handlers.

    Commands are parsed with shlex.split:
        !group subcommand arg1 arg2
    """

    def __init__(
        self,
        client: CLIGatewayClient,
        console: Console,
        session: PromptSession[str],
    ) -> None:
        self.client = client
        self.console = console
        self.session = session
        self._voice_manager: Any | None = None

    @property
    def voice_manager(self) -> Any | None:
        return self._voice_manager

    @voice_manager.setter
    def voice_manager(self, value: Any) -> None:
        self._voice_manager = value

    async def dispatch(self, raw_input: str) -> CommandResult:
        """Parse and dispatch a command.

        Args:
            raw_input: Raw user input string

        Returns:
            CommandResult indicating whether the command was handled
        """
        stripped = raw_input.strip()
        if not stripped.startswith("!"):
            return CommandResult(handled=False)

        # Tier prefixes pass through to gateway
        first_word = stripped.split()[0].lower()
        if first_word in TIER_PREFIXES:
            return CommandResult(handled=False)

        # Parse command
        try:
            parts = shlex.split(stripped)
        except ValueError as e:
            return CommandResult(handled=True, error=f"Parse error: {e}")

        if not parts:
            return CommandResult(handled=False)

        command = parts[0].lower()
        args = parts[1:]

        try:
            if command == "!help":
                return await self._cmd_help(args)
            elif command == "!clear":
                return await self._cmd_clear(args)
            elif command == "!status":
                return await self._cmd_status(args)
            elif command == "!mcp":
                return await self._cmd_mcp(args)
            elif command == "!link":
                return await self._cmd_link(args)
            elif command == "!unlink":
                return await self._cmd_unlink(args)
            elif command == "!voice":
                return await self._cmd_voice(args)
            else:
                return CommandResult(
                    handled=True, error=f"Unknown command: {command}. Type !help for available commands."
                )
        except Exception as e:
            logger.exception(f"Command failed: {command}")
            return CommandResult(handled=True, error=f"Command failed: {e}")

    # =========================================================================
    # Built-in Commands
    # =========================================================================

    async def _cmd_help(self, args: list[str]) -> CommandResult:
        """Show available commands."""
        table = Table(title="CLI Commands", show_header=True, header_style="bold cyan")
        table.add_column("Command", style="green", min_width=28)
        table.add_column("Description")

        # Built-in
        table.add_row("!help", "Show this help message")
        table.add_row("!status", "Show gateway health & user info")
        table.add_row("!clear", "Reset session (disconnect/reconnect)")
        table.add_section()

        # MCP
        table.add_row("!mcp list", "List all MCP servers")
        table.add_row("!mcp status [name]", "Show MCP server status")
        table.add_row("!mcp tools [name]", "List tools for a server")
        table.add_row("!mcp search <query>", "Search Smithery registry")
        table.add_row("!mcp install <src> [name]", "Install an MCP server")
        table.add_row("!mcp uninstall <name>", "Uninstall an MCP server")
        table.add_row("!mcp enable <name>", "Enable an MCP server")
        table.add_row("!mcp disable <name>", "Disable an MCP server")
        table.add_row("!mcp restart <name>", "Restart an MCP server")
        table.add_section()

        # Identity
        table.add_row("!link <platform> <id>", "Link CLI to a platform identity")
        table.add_row("!link status", "Show linked identities")
        table.add_row("!unlink <platform>", "Unlink a platform identity")
        table.add_section()

        # Voice
        table.add_row("!voice start", "Start voice chat (mic + speaker)")
        table.add_row("!voice stop", "Stop voice chat")
        table.add_row("!voice status", "Show voice chat status")
        table.add_section()

        # Tier prefixes
        table.add_row("!high / !opus <msg>", "Send with high-tier model")
        table.add_row("!mid / !sonnet <msg>", "Send with mid-tier model")
        table.add_row("!low / !haiku <msg>", "Send with low-tier model")

        return CommandResult(handled=True, output=table)

    async def _cmd_clear(self, args: list[str]) -> CommandResult:
        """Reset session by disconnecting and reconnecting."""
        self.console.print("[yellow]Resetting session...[/yellow]")
        await self.client.disconnect()
        if await self.client.connect():
            return CommandResult(handled=True, output=Text("Session reset. Reconnected.", style="green"))
        return CommandResult(handled=True, error="Failed to reconnect to gateway")

    async def _cmd_status(self, args: list[str]) -> CommandResult:
        """Show gateway health and user info."""
        table = Table(title="Status", show_header=False, border_style="blue")
        table.add_column("Key", style="cyan")
        table.add_column("Value")

        # Gateway connection
        connected = self.client._ws is not None
        table.add_row("Gateway", "[green]Connected[/green]" if connected else "[red]Disconnected[/red]")
        table.add_row("User ID", f"cli-{self.client.user_id}")

        # Voice status
        if self._voice_manager:
            table.add_row("Voice", "[green]Active[/green]" if self._voice_manager.is_active else "[dim]Inactive[/dim]")
        else:
            table.add_row("Voice", "[dim]Not available[/dim]")

        # Identity linking
        try:
            links = self._get_identity_links()
            if links:
                table.add_row("Linked identities", ", ".join(links))
            else:
                table.add_row("Linked identities", "[dim]None[/dim]")
        except Exception:
            table.add_row("Linked identities", "[dim]DB unavailable[/dim]")

        return CommandResult(handled=True, output=table)

    def _get_identity_links(self) -> list[str]:
        """Query linked identities for status display."""
        from mypalclara.db import SessionLocal
        from mypalclara.db.models import PlatformLink

        cli_prefixed = f"cli-{self.client.user_id}"
        with SessionLocal() as db:
            link = db.query(PlatformLink).filter(PlatformLink.prefixed_user_id == cli_prefixed).first()
            if not link:
                return []
            all_links = (
                db.query(PlatformLink)
                .filter(
                    PlatformLink.canonical_user_id == link.canonical_user_id,
                    PlatformLink.prefixed_user_id != cli_prefixed,
                )
                .all()
            )
            return [f"{l.platform}:{l.platform_user_id}" for l in all_links]

    # =========================================================================
    # MCP Commands
    # =========================================================================

    async def _cmd_mcp(self, args: list[str]) -> CommandResult:
        """Handle !mcp subcommands."""
        if not args:
            return CommandResult(
                handled=True, error="Usage: !mcp <list|status|tools|search|install|uninstall|enable|disable|restart>"
            )

        sub = args[0].lower()
        sub_args = args[1:]

        if sub == "list":
            return await self._mcp_list()
        elif sub == "status":
            return await self._mcp_status(sub_args)
        elif sub == "tools":
            return await self._mcp_tools(sub_args)
        elif sub == "search":
            return await self._mcp_search(sub_args)
        elif sub == "install":
            return await self._mcp_install(sub_args)
        elif sub == "uninstall":
            return await self._mcp_uninstall(sub_args)
        elif sub == "enable":
            return await self._mcp_enable(sub_args)
        elif sub == "disable":
            return await self._mcp_disable(sub_args)
        elif sub == "restart":
            return await self._mcp_restart(sub_args)
        else:
            return CommandResult(handled=True, error=f"Unknown MCP command: {sub}. Type !help for available commands.")

    async def _mcp_list(self) -> CommandResult:
        """List all MCP servers."""
        response = await self.client.mcp_list()

        if not response.success:
            return CommandResult(handled=True, error=f"Failed to list MCP servers: {response.error}")

        if not response.servers:
            return CommandResult(handled=True, output=Text("No MCP servers configured.", style="dim"))

        table = Table(title="MCP Servers", show_header=True, header_style="bold cyan")
        table.add_column("Name", style="green")
        table.add_column("Status")
        table.add_column("Type")
        table.add_column("Tools", justify="right")

        for server in response.servers:
            status_style = "green" if server.status == "running" else "red"
            table.add_row(
                server.name,
                f"[{status_style}]{server.status}[/{status_style}]",
                server.source_type,
                str(server.tool_count),
            )

        return CommandResult(handled=True, output=table)

    async def _mcp_status(self, args: list[str]) -> CommandResult:
        """Show MCP server status."""
        name = args[0] if args else None
        response = await self.client.mcp_status(server_name=name)

        if not response.success:
            return CommandResult(handled=True, error=f"Failed to get status: {response.error}")

        if response.server:
            # Specific server status
            s = response.server
            info = {
                "Name": s.name,
                "Status": s.status,
                "Enabled": str(s.enabled),
                "Connected": str(s.connected),
                "Tools": str(s.tool_count),
                "Source": s.source_type,
            }
            if s.transport:
                info["Transport"] = s.transport
            if s.last_error:
                info["Last Error"] = s.last_error
        else:
            # Overall status
            info = {
                "Total servers": str(response.total_servers),
                "Connected": str(response.connected_servers),
                "Enabled": str(response.enabled_servers),
            }

        panel_content = "\n".join(f"[cyan]{k}[/cyan]: {v}" for k, v in info.items())
        panel = Panel(panel_content, title=f"MCP Status: {name or 'All'}", border_style="blue")
        return CommandResult(handled=True, output=panel)

    async def _mcp_tools(self, args: list[str]) -> CommandResult:
        """List tools for an MCP server."""
        if not args:
            return CommandResult(handled=True, error="Usage: !mcp tools <server-name>")

        name = args[0]
        try:
            from mypalclara.core.mcp import get_mcp_manager

            manager = get_mcp_manager()

            # Try local server first, then remote
            server = manager._local.get_server(name)
            if not server:
                server = manager._remote.get_connection(name)
            if not server:
                return CommandResult(handled=True, error=f"Server not found: {name}")

            tools = server.get_tools()
            if not tools:
                return CommandResult(handled=True, output=Text(f"No tools registered for {name}.", style="dim"))

            table = Table(title=f"Tools: {name}", show_header=True, header_style="bold cyan")
            table.add_column("Name", style="green")
            table.add_column("Description")

            for tool in tools:
                tool_name = tool.name if hasattr(tool, "name") else str(tool)
                tool_desc = tool.description if hasattr(tool, "description") else ""
                table.add_row(tool_name, tool_desc[:80])

            return CommandResult(handled=True, output=table)

        except ImportError:
            return CommandResult(handled=True, error="MCP manager not available in this environment")
        except Exception as e:
            return CommandResult(handled=True, error=f"Failed to list tools: {e}")

    async def _mcp_search(self, args: list[str]) -> CommandResult:
        """Search Smithery registry."""
        if not args:
            return CommandResult(handled=True, error="Usage: !mcp search <query>")

        query = " ".join(args)
        try:
            from mypalclara.core.mcp import SmitheryClient

            client = SmitheryClient()
            result = await client.search(query)

            if result.error:
                return CommandResult(handled=True, error=f"Search failed: {result.error}")

            if not result.servers:
                return CommandResult(handled=True, output=Text(f"No results for '{query}'.", style="dim"))

            table = Table(title=f"Smithery: {query}", show_header=True, header_style="bold cyan")
            table.add_column("Name", style="green")
            table.add_column("Description")
            table.add_column("Source", style="dim")

            for s in result.servers[:10]:
                table.add_row(
                    s.display_name,
                    (s.description or "")[:60],
                    s.qualified_name,
                )

            return CommandResult(handled=True, output=table)

        except ImportError:
            return CommandResult(handled=True, error="Smithery client not available in this environment")

    async def _mcp_install(self, args: list[str]) -> CommandResult:
        """Install an MCP server with confirmation."""
        if not args:
            return CommandResult(handled=True, error="Usage: !mcp install <source> [name]")

        source = args[0]
        name = args[1] if len(args) > 1 else None

        # Confirm
        import asyncio

        confirm = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.session.prompt(f"Install '{source}'{f' as {name}' if name else ''}? [y/n]: "),
        )
        if confirm.lower().strip() not in ("y", "yes"):
            return CommandResult(handled=True, output=Text("Cancelled.", style="yellow"))

        self.console.print("[yellow]Installing...[/yellow]")
        response = await self.client.mcp_install(
            source=source,
            name=name,
            requested_by=f"cli-{self.client.user_id}",
        )

        if response.success:
            return CommandResult(handled=True, output=Text(f"Installed: {response.server_name}", style="green"))
        return CommandResult(handled=True, error=f"Install failed: {response.error}")

    async def _mcp_uninstall(self, args: list[str]) -> CommandResult:
        """Uninstall an MCP server with confirmation."""
        if not args:
            return CommandResult(handled=True, error="Usage: !mcp uninstall <name>")

        name = args[0]

        import asyncio

        confirm = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.session.prompt(f"Uninstall '{name}'? [y/n]: "),
        )
        if confirm.lower().strip() not in ("y", "yes"):
            return CommandResult(handled=True, output=Text("Cancelled.", style="yellow"))

        response = await self.client.mcp_uninstall(server_name=name)

        if response.success:
            return CommandResult(handled=True, output=Text(f"Uninstalled: {name}", style="green"))
        return CommandResult(handled=True, error=f"Uninstall failed: {response.error}")

    async def _mcp_enable(self, args: list[str]) -> CommandResult:
        """Enable an MCP server."""
        if not args:
            return CommandResult(handled=True, error="Usage: !mcp enable <name>")

        response = await self.client.mcp_enable(server_name=args[0], enabled=True)
        if response.success:
            return CommandResult(handled=True, output=Text(f"Enabled: {args[0]}", style="green"))
        return CommandResult(handled=True, error=f"Enable failed: {response.error}")

    async def _mcp_disable(self, args: list[str]) -> CommandResult:
        """Disable an MCP server."""
        if not args:
            return CommandResult(handled=True, error="Usage: !mcp disable <name>")

        response = await self.client.mcp_enable(server_name=args[0], enabled=False)
        if response.success:
            return CommandResult(handled=True, output=Text(f"Disabled: {args[0]}", style="yellow"))
        return CommandResult(handled=True, error=f"Disable failed: {response.error}")

    async def _mcp_restart(self, args: list[str]) -> CommandResult:
        """Restart an MCP server."""
        if not args:
            return CommandResult(handled=True, error="Usage: !mcp restart <name>")

        self.console.print(f"[yellow]Restarting {args[0]}...[/yellow]")
        response = await self.client.mcp_restart(server_name=args[0])
        if response.success:
            return CommandResult(handled=True, output=Text(f"Restarted: {args[0]}", style="green"))
        return CommandResult(handled=True, error=f"Restart failed: {response.error}")

    # =========================================================================
    # Identity Linking Commands
    # =========================================================================

    async def _cmd_link(self, args: list[str]) -> CommandResult:
        """Handle !link subcommands."""
        if not args:
            return CommandResult(handled=True, error="Usage: !link <platform> <id>  or  !link status")

        if args[0].lower() == "status":
            return await self._link_status()

        if len(args) < 2:
            return CommandResult(handled=True, error="Usage: !link <platform> <id>")

        platform = args[0].lower()
        platform_id = args[1]
        return await self._link_create(platform, platform_id)

    async def _link_create(self, platform: str, platform_id: str) -> CommandResult:
        """Link CLI user to another platform identity."""
        from mypalclara.db import SessionLocal
        from mypalclara.db.models import CanonicalUser, PlatformLink

        cli_prefixed = f"cli-{self.client.user_id}"
        target_prefixed = f"{platform}-{platform_id}"

        try:
            with SessionLocal() as db:
                # Find or create canonical user for target
                target_link = db.query(PlatformLink).filter(PlatformLink.prefixed_user_id == target_prefixed).first()

                if target_link:
                    canonical_user_id = target_link.canonical_user_id
                else:
                    # Create new canonical user and link for target
                    from mypalclara.db.models import gen_uuid

                    canonical_user_id = gen_uuid()
                    canonical_user = CanonicalUser(
                        id=canonical_user_id,
                        display_name=f"{platform}:{platform_id}",
                    )
                    db.add(canonical_user)

                    target_link = PlatformLink(
                        canonical_user_id=canonical_user_id,
                        platform=platform,
                        platform_user_id=platform_id,
                        prefixed_user_id=target_prefixed,
                        display_name=f"{platform}:{platform_id}",
                        linked_via="cli-command",
                    )
                    db.add(target_link)

                # Check if CLI user is already linked
                cli_link = db.query(PlatformLink).filter(PlatformLink.prefixed_user_id == cli_prefixed).first()

                if cli_link:
                    if cli_link.canonical_user_id == canonical_user_id:
                        return CommandResult(
                            handled=True, output=Text("Already linked to this identity.", style="yellow")
                        )

                    # Different canonical user — confirm re-link
                    import asyncio

                    confirm = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: self.session.prompt("CLI is linked to a different identity. Re-link? [y/n]: "),
                    )
                    if confirm.lower().strip() not in ("y", "yes"):
                        return CommandResult(handled=True, output=Text("Cancelled.", style="yellow"))

                    cli_link.canonical_user_id = canonical_user_id
                else:
                    cli_link = PlatformLink(
                        canonical_user_id=canonical_user_id,
                        platform="cli",
                        platform_user_id=self.client.user_id,
                        prefixed_user_id=cli_prefixed,
                        display_name=f"cli:{self.client.user_id}",
                        linked_via="cli-command",
                    )
                    db.add(cli_link)

                db.commit()

            return CommandResult(
                handled=True,
                output=Text(f"Linked cli:{self.client.user_id} to {platform}:{platform_id}", style="green"),
            )

        except Exception as e:
            return CommandResult(handled=True, error=f"Link failed: {e}")

    async def _link_status(self) -> CommandResult:
        """Show linked identities."""
        from mypalclara.db import SessionLocal
        from mypalclara.db.models import CanonicalUser, PlatformLink

        cli_prefixed = f"cli-{self.client.user_id}"

        try:
            with SessionLocal() as db:
                cli_link = db.query(PlatformLink).filter(PlatformLink.prefixed_user_id == cli_prefixed).first()

                if not cli_link:
                    return CommandResult(
                        handled=True,
                        output=Text("No identity linked. Use !link <platform> <id> to link.", style="dim"),
                    )

                canonical = db.query(CanonicalUser).filter(CanonicalUser.id == cli_link.canonical_user_id).first()
                all_links = (
                    db.query(PlatformLink).filter(PlatformLink.canonical_user_id == cli_link.canonical_user_id).all()
                )

                table = Table(
                    title=f"Identity: {canonical.display_name if canonical else '?'}",
                    show_header=True,
                    header_style="bold cyan",
                )
                table.add_column("Platform", style="green")
                table.add_column("User ID")
                table.add_column("Linked Via", style="dim")

                for link in all_links:
                    table.add_row(link.platform, link.platform_user_id, link.linked_via or "—")

                return CommandResult(handled=True, output=table)

        except Exception as e:
            return CommandResult(handled=True, error=f"Failed to query links: {e}")

    async def _cmd_unlink(self, args: list[str]) -> CommandResult:
        """Unlink CLI from a platform identity."""
        if not args:
            return CommandResult(handled=True, error="Usage: !unlink <platform>  (removes CLI's link)")

        from mypalclara.db import SessionLocal
        from mypalclara.db.models import PlatformLink

        cli_prefixed = f"cli-{self.client.user_id}"

        try:
            import asyncio

            confirm = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.session.prompt("Unlink CLI from identity? [y/n]: "),
            )
            if confirm.lower().strip() not in ("y", "yes"):
                return CommandResult(handled=True, output=Text("Cancelled.", style="yellow"))

            with SessionLocal() as db:
                cli_link = db.query(PlatformLink).filter(PlatformLink.prefixed_user_id == cli_prefixed).first()

                if not cli_link:
                    return CommandResult(handled=True, output=Text("CLI is not linked to any identity.", style="dim"))

                db.delete(cli_link)
                db.commit()

            return CommandResult(handled=True, output=Text("Unlinked CLI identity.", style="green"))

        except Exception as e:
            return CommandResult(handled=True, error=f"Unlink failed: {e}")

    # =========================================================================
    # Voice Commands
    # =========================================================================

    async def _cmd_voice(self, args: list[str]) -> CommandResult:
        """Handle !voice subcommands."""
        if not args:
            return CommandResult(handled=True, error="Usage: !voice <start|stop|status>")

        sub = args[0].lower()

        if sub == "start":
            return await self._voice_start()
        elif sub == "stop":
            return await self._voice_stop()
        elif sub == "status":
            return await self._voice_status()
        else:
            return CommandResult(handled=True, error=f"Unknown voice command: {sub}")

    async def _voice_start(self) -> CommandResult:
        """Start voice chat."""
        if self._voice_manager and self._voice_manager.is_active:
            return CommandResult(handled=True, output=Text("Voice is already active.", style="yellow"))

        try:
            from mypalclara.adapters.cli.voice import CLIVoiceManager

            if not self._voice_manager:
                self._voice_manager = CLIVoiceManager(
                    client=self.client,
                    console=self.console,
                )

            await self._voice_manager.start()
            return CommandResult(handled=True, output=Text("Voice mode active. Listening...", style="green"))

        except ImportError as e:
            return CommandResult(
                handled=True,
                error=f"Voice dependencies not available: {e}\nInstall: pip install sounddevice && brew install portaudio",
            )
        except Exception as e:
            return CommandResult(handled=True, error=f"Failed to start voice: {e}")

    async def _voice_stop(self) -> CommandResult:
        """Stop voice chat."""
        if not self._voice_manager or not self._voice_manager.is_active:
            return CommandResult(handled=True, output=Text("Voice is not active.", style="dim"))

        await self._voice_manager.stop()
        return CommandResult(handled=True, output=Text("Voice mode stopped.", style="yellow"))

    async def _voice_status(self) -> CommandResult:
        """Show voice chat status."""
        if not self._voice_manager:
            return CommandResult(handled=True, output=Text("Voice: not initialized", style="dim"))

        active = self._voice_manager.is_active
        table = Table(show_header=False, border_style="blue")
        table.add_column("Key", style="cyan")
        table.add_column("Value")
        table.add_row("Voice", "[green]Active[/green]" if active else "[dim]Inactive[/dim]")

        if active:
            from mypalclara.adapters.discord.voice.config import (
                VOICE_STT_PROVIDER,
                VOICE_TTS_SPEAKER,
                VOICE_VAD_AGGRESSIVENESS,
            )

            table.add_row("STT Provider", VOICE_STT_PROVIDER)
            table.add_row("TTS Speaker", VOICE_TTS_SPEAKER)
            table.add_row("VAD Aggressiveness", str(VOICE_VAD_AGGRESSIVENESS))

        return CommandResult(handled=True, output=table)
