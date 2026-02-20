"""CLI-specific tools - file operations and shell commands.

Provides tools for the CLI adapter:
- cli_read_file: Read file contents (auto-approved)
- cli_write_file: Write content to file (requires approval with diff preview)
- cli_shell_command: Execute shell commands (tiered safety)

Platform: CLI only
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from adapters.cli.approval import get_write_approval, show_write_preview
from adapters.cli.shell_executor import (
    CommandSafety,
    classify_command,
    execute_shell,
)
from tools._base import ToolContext, ToolDef

MODULE_NAME = "cli_tools"
MODULE_VERSION = "0.2.0"

SYSTEM_PROMPT = """
## CLI File Operations & Shell Commands

You can read/write files and execute shell commands directly on the user's filesystem (CLI only).

**File Operations:**
- `cli_read_file` - Read file contents (auto-approved)
- `cli_write_file` - Write content to a file (requires user approval with diff preview)

**Shell Commands:**
- `cli_shell_command` - Execute shell commands with safety classification

**Shell Safety Levels:**
- **SAFE**: Auto-approved (ls, cat, pwd, echo, grep, find, etc.)
- **NORMAL**: Require 'y' confirmation (most commands)
- **DANGEROUS**: Require typing 'yes' (rm -rf, sudo, chmod 777, etc.)

**Working Directory:**
- Use 'cd <directory>' to change working directory (tracked in session)
- All commands execute in the current working directory
- Current directory persists across commands in the same session

**Note:** These tools only work in CLI mode, not Discord.
""".strip()


# =============================================================================
# File Operations
# =============================================================================


async def cli_read_file(args: dict[str, Any], ctx: ToolContext) -> str:
    """Read contents of a file - automatically approved for CLI."""
    path_str = args.get("path", "")
    if not path_str:
        return "Error: No path provided"

    # Expand ~ and resolve to absolute path
    try:
        file_path = Path(path_str).expanduser().resolve()
    except Exception as e:
        return f"Error: Invalid path '{path_str}': {e}"

    # Check if file exists
    if not file_path.exists():
        return f"Error: File not found: {path_str}"

    if file_path.is_dir():
        return f"Error: Path is a directory, not a file: {path_str}"

    # Try to read as text
    try:
        content = file_path.read_text(encoding="utf-8")
        return content
    except UnicodeDecodeError:
        # Binary file - return info instead of content
        size = file_path.stat().st_size
        return f"[Binary file: {size} bytes - use appropriate tool to view]"
    except Exception as e:
        return f"Error reading file: {e}"


async def cli_write_file(args: dict[str, Any], ctx: ToolContext) -> str:
    """Write content to a file - requires user approval with diff preview."""
    path_str = args.get("path", "")
    content = args.get("content", "")

    if not path_str:
        return "Error: No path provided"

    if content is None:
        return "Error: No content provided"

    # Get console and session from context extra
    # These are passed during CLI initialization
    console = ctx.extra.get("console")
    session = ctx.extra.get("session")

    if not console or not session:
        return "Error: CLI file write tool requires console and session context (only works in interactive CLI)"

    # Expand ~ and resolve to absolute path
    try:
        file_path = Path(path_str).expanduser().resolve()
    except Exception as e:
        return f"Error: Invalid path '{path_str}': {e}"

    # Show diff preview
    try:
        show_write_preview(console, file_path, content)
    except Exception as e:
        return f"Error showing preview: {e}"

    # Get user approval
    try:
        approved = await get_write_approval(session)
    except Exception as e:
        return f"Error getting approval: {e}"

    if not approved:
        return "Write cancelled by user."

    # Create parent directories if needed
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return f"Error creating parent directories: {e}"

    # Write the file
    try:
        file_path.write_text(content, encoding="utf-8")
        byte_count = len(content.encode("utf-8"))
        return f"Wrote {byte_count} bytes to {file_path}"
    except Exception as e:
        return f"Error writing file: {e}"


# =============================================================================
# Shell Commands
# =============================================================================


async def cli_shell_command(args: dict[str, Any], ctx: ToolContext) -> str:
    """Execute a shell command with safety classification and timeout."""
    command = args.get("command", "")
    timeout = args.get("timeout", 60)

    if not command:
        return "Error: No command provided"

    # Get console and session from context extra
    console = ctx.extra.get("console")
    session = ctx.extra.get("session")

    if not console or not session:
        return "Error: CLI shell tool requires console and session context (only works in interactive CLI)"

    # Get or initialize working directory
    cwd = ctx.extra.get("shell_cwd", os.getcwd())

    # Get or initialize environment variables
    env = ctx.extra.get("shell_env", {})

    # Handle 'cd' command specially - don't execute, just update cwd
    if command.strip().startswith("cd "):
        # Parse target directory
        target = command.strip()[3:].strip()
        if not target:
            target = os.path.expanduser("~")
        else:
            target = os.path.expanduser(target)

        # Make absolute path relative to current cwd
        if not os.path.isabs(target):
            target = os.path.join(cwd, target)

        # Resolve the path
        try:
            target = os.path.realpath(target)
        except Exception as e:
            return f"Error resolving path: {e}"

        # Check if directory exists
        if not os.path.isdir(target):
            return f"Error: Not a directory: {target}"

        # Update cwd in context
        ctx.extra["shell_cwd"] = target
        return f"Changed to: {target}"

    # Classify command safety
    safety = classify_command(command)

    # Handle approval based on safety level
    approved = False

    if safety == CommandSafety.SAFE:
        # Auto-approve safe commands
        approved = True
    elif safety == CommandSafety.NORMAL:
        # Show command and prompt for 'y'
        console.print(f"\n[yellow]Execute:[/yellow] {command}")
        console.print(f"[dim]Working directory: {cwd}[/dim]")
        prompt_text = "Execute? [y/n]: "
        try:
            response = await session.prompt_async(prompt_text)
            approved = response.strip().lower() == "y"
        except (KeyboardInterrupt, EOFError):
            return "Command cancelled."
    elif safety == CommandSafety.DANGEROUS:
        # Show warning and require typing 'yes'
        console.print("\n[red bold]⚠ Dangerous command![/red bold]")
        console.print(f"[yellow]Command:[/yellow] {command}")
        console.print(f"[dim]Working directory: {cwd}[/dim]")
        prompt_text = "Type 'yes' to confirm: "
        try:
            response = await session.prompt_async(prompt_text)
            approved = response.strip() == "yes"
        except (KeyboardInterrupt, EOFError):
            return "Command cancelled."

    if not approved:
        return "Command cancelled."

    # Execute the command
    result = await execute_shell(
        command,
        cwd=cwd,
        env={**os.environ, **env},
        timeout=timeout,
    )

    # Format the result
    output_parts = []

    if result.stdout:
        output_parts.append(result.stdout)

    if result.stderr:
        output_parts.append(f"[stderr]\n{result.stderr}")

    if result.timed_out:
        output_parts.append(f"\n⚠ Command timed out after {timeout} seconds")

    if result.exit_code != 0:
        output_parts.append(f"\n[Exit code: {result.exit_code}]")

    if not output_parts:
        return "[No output]"

    return "\n".join(output_parts)


# =============================================================================
# Tool Definitions
# =============================================================================

TOOLS = [
    ToolDef(
        name="cli_read_file",
        description=(
            "Read the contents of a file from the filesystem. "
            "Automatically approved for CLI. Use this to read configuration files, "
            "code, documents, or any text file the user references. "
            "Binary files are detected and not read."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative file path (supports ~ expansion)",
                },
            },
            "required": ["path"],
        },
        handler=cli_read_file,
        platforms=["cli"],
    ),
    ToolDef(
        name="cli_write_file",
        description=(
            "Write content to a file on the filesystem. "
            "Shows a diff preview and requires user approval with 'y' confirmation. "
            "Use this to create new files or modify existing ones. "
            "Parent directories are created automatically if needed."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative file path (supports ~ expansion)",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file",
                },
            },
            "required": ["path", "content"],
        },
        handler=cli_write_file,
        platforms=["cli"],
    ),
    ToolDef(
        name="cli_shell_command",
        description=(
            "Execute a shell command on the user's system. "
            "Safe commands (ls, cat, pwd) are auto-approved. "
            "Normal commands require 'y' confirmation. "
            "Dangerous commands (rm -rf, sudo) require typing 'yes'. "
            "Use 'cd <directory>' to change working directory (persists in session). "
            "Commands timeout after 60 seconds by default."
        ),
        parameters={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute (e.g., 'ls -la', 'cd /tmp', 'python script.py')",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default: 60)",
                },
            },
            "required": ["command"],
        },
        handler=cli_shell_command,
        platforms=["cli"],
    ),
]


# =============================================================================
# Lifecycle Hooks
# =============================================================================


async def initialize() -> None:
    """Initialize CLI tools module."""
    pass  # No special initialization needed


async def cleanup() -> None:
    """Cleanup on module unload."""
    pass
