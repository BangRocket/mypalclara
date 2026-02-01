"""Clara CLI - Command-line interface for managing Clara.

Provides commands for:
- Gateway management (start, stop, status)
- Channel management (list, enable, disable, status)
- Plugin management (install, uninstall, list)
- Configuration (show, edit, validate)
- Status and diagnostics (doctor, status)
- Interactive chat (chat, agent)

Usage:
    clara --help
    clara gateway start
    clara channels list
    clara chat
"""

from clara_core.cli.main import app, run

__all__ = ["app", "run"]
