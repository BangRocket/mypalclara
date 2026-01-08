"""Tools for the Code Agent.

These tools execute code in a sandboxed environment.
"""

from __future__ import annotations

import asyncio
from typing import Any

from crewai.tools import tool


# Global user_id for sandbox context (set by agent before tool execution)
_current_user_id: str = "default"


def set_user_context(user_id: str) -> None:
    """Set the user context for sandbox operations."""
    global _current_user_id
    _current_user_id = user_id


def _run_async(coro):
    """Run async coroutine from sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're in an async context, use run_in_executor pattern
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def _get_sandbox():
    """Get the sandbox manager (lazy import to avoid circular deps)."""
    from sandbox.manager import get_sandbox_manager
    return get_sandbox_manager()


@tool("execute_python")
def execute_python(code: str) -> str:
    """Execute Python code in a secure sandbox environment.

    Use this tool to run Python code. The sandbox has common packages
    pre-installed (requests, pandas, numpy, etc.). You can install
    additional packages with install_package.

    Args:
        code: Python code to execute

    Returns:
        Output from the code execution (stdout/stderr)
    """
    async def _execute():
        sandbox = _get_sandbox()
        result = await sandbox.execute_code(
            user_id=_current_user_id,
            code=code,
            timeout=30,
        )
        if result.success:
            return result.output or "(No output)"
        else:
            return f"Error: {result.error}"

    return _run_async(_execute())


@tool("install_package")
def install_package(package: str) -> str:
    """Install a Python package in the sandbox using pip.

    Args:
        package: Package name (e.g., 'requests', 'pandas==2.0.0')

    Returns:
        Installation output or error message
    """
    async def _install():
        sandbox = _get_sandbox()
        result = await sandbox.install_package(
            user_id=_current_user_id,
            package=package,
            timeout=120,
        )
        if result.success:
            return f"Successfully installed {package}"
        else:
            return f"Failed to install {package}: {result.error}"

    return _run_async(_install())


@tool("run_shell")
def run_shell(command: str) -> str:
    """Run a shell command in the sandbox.

    Use for file operations, git commands, or other shell tasks.
    Be careful with destructive commands.

    Args:
        command: Shell command to execute

    Returns:
        Command output
    """
    async def _shell():
        sandbox = _get_sandbox()
        result = await sandbox.run_shell(
            user_id=_current_user_id,
            command=command,
            timeout=60,
        )
        if result.success:
            return result.output or "(No output)"
        else:
            return f"Error: {result.error}"

    return _run_async(_shell())


@tool("read_file")
def read_file(path: str) -> str:
    """Read a file from the sandbox workspace.

    Args:
        path: Path to the file (relative to /workspace or absolute)

    Returns:
        File contents
    """
    async def _read():
        sandbox = _get_sandbox()
        result = await sandbox.read_file(
            user_id=_current_user_id,
            path=path,
        )
        if result.success:
            return result.output
        else:
            return f"Error reading file: {result.error}"

    return _run_async(_read())


@tool("write_file")
def write_file(path: str, content: str) -> str:
    """Write content to a file in the sandbox workspace.

    Args:
        path: Path to the file (relative to /workspace or absolute)
        content: Content to write to the file

    Returns:
        Success message or error
    """
    async def _write():
        sandbox = _get_sandbox()
        result = await sandbox.write_file(
            user_id=_current_user_id,
            path=path,
            content=content,
        )
        if result.success:
            return f"Successfully wrote to {path}"
        else:
            return f"Error writing file: {result.error}"

    return _run_async(_write())


@tool("list_files")
def list_files(path: str = "/workspace") -> str:
    """List files in a sandbox directory.

    Args:
        path: Directory path (defaults to /workspace)

    Returns:
        List of files and directories
    """
    async def _list():
        sandbox = _get_sandbox()
        result = await sandbox.list_files(
            user_id=_current_user_id,
            path=path,
        )
        if result.success:
            return result.output or "(Empty directory)"
        else:
            return f"Error listing files: {result.error}"

    return _run_async(_list())


# Export all tools as a list for the agent
CODE_TOOLS = [
    execute_python,
    install_package,
    run_shell,
    read_file,
    write_file,
    list_files,
]
