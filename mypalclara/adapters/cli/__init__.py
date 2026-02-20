"""CLI adapter for Clara."""

from mypalclara.adapters.cli.adapter import CLIAdapter
from mypalclara.adapters.cli.approval import get_write_approval, show_write_preview
from mypalclara.adapters.cli.gateway_client import CLIGatewayClient
from mypalclara.adapters.cli.logging import configure_cli_logging
from mypalclara.adapters.cli.shell_executor import (
    CommandSafety,
    ShellResult,
    classify_command,
    execute_shell,
)
from mypalclara.adapters.cli.tools import TOOLS as CLI_TOOLS

__all__ = [
    "CLI_TOOLS",
    "CLIAdapter",
    "CLIGatewayClient",
    "CommandSafety",
    "ShellResult",
    "classify_command",
    "configure_cli_logging",
    "execute_shell",
    "get_write_approval",
    "show_write_preview",
]
