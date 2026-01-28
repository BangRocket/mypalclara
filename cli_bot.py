#!/usr/bin/env python3
"""Clara CLI - Terminal interface for Clara AI assistant.

DEPRECATED: This file is a migration wrapper. Use the new gateway-based CLI:

    poetry run python -m adapters.cli
    poetry run clara-cli

The new CLI connects to the Clara Gateway for improved architecture and features.

Commands:
    Ctrl+C  - Cancel current input
    Ctrl+D  - Exit
    !high   - Use high-tier model for next message
    !mid    - Use mid-tier model (default)
    !low    - Use low-tier model
"""

from __future__ import annotations

from rich.console import Console

console = Console()

# Show deprecation notice
console.print()
console.print("[yellow]Note: cli_bot.py is deprecated.[/yellow]")
console.print("Use: [bold]poetry run python -m adapters.cli[/bold]")
console.print("Or:  [bold]poetry run clara-cli[/bold]")
console.print()

# Delegate to the new CLI
from adapters.cli.main import run

run()
