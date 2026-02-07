"""CLI adapter for Clara."""

from adapters.cli.adapter import CLIAdapter
from adapters.cli.approval import get_write_approval, show_write_preview
from adapters.cli.commands import CommandDispatcher, CommandResult
from adapters.cli.gateway_client import CLIGatewayClient
from adapters.cli.logging import configure_cli_logging
from adapters.cli.shell_executor import (
    CommandSafety,
    ShellResult,
    classify_command,
    execute_shell,
)
from adapters.cli.tools import TOOLS as CLI_TOOLS

__all__ = [
    "CLI_TOOLS",
    "CLIAdapter",
    "CLIGatewayClient",
    "CommandDispatcher",
    "CommandResult",
    "CommandSafety",
    "ShellResult",
    "classify_command",
    "configure_cli_logging",
    "execute_shell",
    "get_write_approval",
    "show_write_preview",
]
