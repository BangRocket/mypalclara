"""Approval helpers for CLI file operations.

Provides diff preview and approval prompts for safe file writing.
"""

from __future__ import annotations

import difflib
from pathlib import Path

from prompt_toolkit import PromptSession
from rich.console import Console
from rich.syntax import Syntax


def show_write_preview(
    console: Console,
    path: Path,
    new_content: str,
) -> None:
    """Show diff preview for a file write.

    Args:
        console: Rich console for formatted output
        path: Path to the file being written
        new_content: Content that will be written
    """
    if path.exists():
        # File exists - show unified diff
        try:
            old_content = path.read_text(errors="replace")
        except Exception:
            old_content = ""

        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{path.name}",
            tofile=f"b/{path.name}",
        )
        diff_text = "".join(diff)

        if diff_text:
            # Colorize diff output
            console.print(f"\n[bold]Changes to {path}:[/bold]")
            console.print(Syntax(diff_text, "diff", theme="monokai"))
        else:
            console.print(f"[dim]No changes to {path}[/dim]")
    else:
        # New file - show full content with line numbers
        console.print(f"\n[bold]New file: {path}[/bold]")
        console.print(Syntax(new_content, "text", theme="monokai", line_numbers=True))


async def get_write_approval(
    session: PromptSession,
    prompt: str = "Write this file? [y/n]: ",
) -> bool:
    """Get user approval for a file write operation.

    Args:
        session: Prompt toolkit session for async input
        prompt: The prompt message to display

    Returns:
        True if user approves with 'y', False otherwise
    """
    response = await session.prompt_async(prompt)
    return response.lower() == "y"
