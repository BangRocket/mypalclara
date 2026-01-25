"""Shell execution with safety classification.

Provides safe command execution for CLI mode with tiered safety controls:
- SAFE: Auto-approve (ls, cat, pwd, etc.)
- NORMAL: Require 'y' confirmation (most commands)
- DANGEROUS: Require typing 'yes' (rm -rf, sudo, etc.)

All commands timeout after ~60 seconds to prevent hangs.
"""

from __future__ import annotations

import asyncio
import os
import re
import shlex
from dataclasses import dataclass
from enum import Enum
from typing import Any

# Timeout for command execution
DEFAULT_TIMEOUT = 60  # seconds


class CommandSafety(Enum):
    """Safety classification for shell commands."""

    SAFE = "safe"  # Auto-approve
    NORMAL = "normal"  # Require 'y'
    DANGEROUS = "dangerous"  # Require 'yes'


# Commands that are safe to execute without confirmation
SAFE_COMMANDS = {
    "ls",
    "cat",
    "echo",
    "pwd",
    "whoami",
    "date",
    "cal",
    "head",
    "tail",
    "wc",
    "sort",
    "uniq",
    "diff",
    "grep",
    "find",
    "which",
    "file",
    "stat",
    "du",
    "df",
    "env",
    "printenv",
    "hostname",
    "uname",
    "tree",
    "less",
    "more",
}

# Patterns that indicate dangerous commands requiring explicit "yes" confirmation
DANGEROUS_PATTERNS = [
    r"rm\s+(-rf?|--recursive|-r\s+-f|-f\s+-r)",  # rm -rf
    r"sudo\s+",  # sudo anything
    r">\s*/dev/",  # Write to device
    r"mkfs",  # Format filesystem
    r"dd\s+",  # Disk write
    r":\(\)\s*\{\s*:\|",  # Fork bomb - exact pattern only
    r"chmod\s+777",  # Overly permissive
    r"chown\s+-R",  # Recursive ownership change
]


@dataclass
class ShellResult:
    """Result from shell command execution.

    Attributes:
        success: Whether the command completed successfully (exit code 0)
        stdout: Standard output from the command
        stderr: Standard error from the command
        exit_code: Process exit code
        timed_out: Whether the command exceeded the timeout
    """

    success: bool
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool = False


def classify_command(command: str) -> CommandSafety:
    """Classify a command's safety level.

    Args:
        command: The shell command to classify

    Returns:
        CommandSafety indicating the safety level
    """
    # Check for dangerous patterns first
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, command):
            return CommandSafety.DANGEROUS

    # Parse the base command (first word)
    try:
        parts = shlex.split(command)
        if not parts:
            return CommandSafety.NORMAL

        # Extract base command (strip path if present)
        base_command = os.path.basename(parts[0])

        # Check if it's in the safe list
        if base_command in SAFE_COMMANDS:
            return CommandSafety.SAFE
    except ValueError:
        # If shlex.split fails (e.g., unclosed quotes), treat as normal
        pass

    # Default to requiring confirmation
    return CommandSafety.NORMAL


async def execute_shell(
    command: str,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> ShellResult:
    """Execute a shell command with timeout.

    Args:
        command: The shell command to execute
        cwd: Working directory for the command (defaults to current)
        env: Environment variables to set (merged with os.environ)
        timeout: Timeout in seconds (default: 60)

    Returns:
        ShellResult with output and status
    """
    # Merge environment variables
    merged_env = {**os.environ}
    if env:
        merged_env.update(env)

    # Create subprocess
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=merged_env,
        )

        # Wait for completion with timeout
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )

            # Decode output
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            exit_code = process.returncode or 0

            return ShellResult(
                success=(exit_code == 0),
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                timed_out=False,
            )

        except asyncio.TimeoutError:
            # Kill the process on timeout
            process.terminate()

            # Give it 5 seconds to terminate gracefully
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                # Force kill if it doesn't respond
                process.kill()
                await process.wait()

            return ShellResult(
                success=False,
                stdout="",
                stderr=f"Command timed out after {timeout} seconds",
                exit_code=-1,
                timed_out=True,
            )

    except Exception as e:
        return ShellResult(
            success=False,
            stdout="",
            stderr=f"Error executing command: {e}",
            exit_code=-1,
            timed_out=False,
        )
