"""CLI adapter for Clara."""

from adapters.cli.adapter import CLIAdapter
from adapters.cli.approval import get_write_approval, show_write_preview
from adapters.cli.gateway_client import CLIGatewayClient
from adapters.cli.logging import configure_cli_logging
from adapters.cli.shell_executor import (
    CommandSafety,
    ShellResult,
    classify_command,
    execute_shell,
)

__all__ = [
    "CLIAdapter",
    "CLIGatewayClient",
    "configure_cli_logging",
    "get_write_approval",
    "show_write_preview",
    "CommandSafety",
    "classify_command",
    "execute_shell",
    "ShellResult",
]
