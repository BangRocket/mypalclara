"""CLI adapter for Clara."""

from adapters.cli.adapter import CLIAdapter
from adapters.cli.approval import get_write_approval, show_write_preview
from adapters.cli.logging import configure_cli_logging

__all__ = [
    "CLIAdapter",
    "configure_cli_logging",
    "get_write_approval",
    "show_write_preview",
]
