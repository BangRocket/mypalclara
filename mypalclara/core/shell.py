"""Cross-platform helpers for running shell commands on the host.

``asyncio.create_subprocess_shell`` uses ``/bin/sh`` on Unix but ``cmd.exe`` on Windows, and
cmd writes output in the console's OEM code page rather than UTF-8. This module centralises:

- describing the host shell (so the LLM writes commands for the right shell),
- the dangerous-command blocklist (Unix *and* Windows forms),
- decoding command output,
- killing a shell together with the processes it started.
"""

from __future__ import annotations

import asyncio
import ctypes
import platform
import re
import subprocess
import sys

IS_WINDOWS = sys.platform == "win32"


def shell_description() -> str:
    """Human/LLM-readable description of the shell that host commands run in."""
    if IS_WINDOWS:
        return (
            f"Windows ({platform.release()}) cmd.exe — use cmd syntax (dir, type, copy, del, set VAR=x, "
            '&& and ||, %VAR%), not bash. For PowerShell, prefix with: powershell -NoProfile -Command "..."'
        )
    if sys.platform == "darwin":
        return "macOS /bin/sh (POSIX shell)"
    return f"{platform.system()} /bin/sh (POSIX shell)"


# =============================================================================
# Dangerous command detection
# =============================================================================

_UNIX_PATTERNS = [
    r"rm\s+(-[rfRv]+\s+)*(/|/\*|\*/)",  # rm -rf / or rm -rf /*
    r"rm\s+(-[rfRv]+\s+)+\.\.",  # rm -rf ..
    r"mkfs(\.\w+)?\s",  # mkfs / mkfs.ext4 etc.
    r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:",  # Fork bomb
    r"dd\s+.*of=/dev/(sd|hd|nvme)",  # dd to raw disk
    r">\s*/dev/(sd|hd|nvme)",  # Redirect to raw disk
    r"chmod\s+(-R\s+)?777\s+/",  # chmod 777 /
    r"chown\s+(-R\s+)?.*\s+/\s*$",  # chown /
]

# A drive root (C:\, C:\*, C:\*.*, "D:") or the Windows / Users system directories.
_WIN_TARGET = (
    r"(?:^|[\s\"'])(?:[a-z]:\\*(?:\*(?:\.\*)?)?|[a-z]:\\+(?:windows|users|program files(?: \(x86\))?)\\*(?:\*(?:\.\*)?)?"
    r"|%systemroot%|%windir%|%systemdrive%\\*|\$env:systemroot|\$env:windir)(?:[\s\"']|$)"
)
_WIN_PATTERNS = [
    # Recursive deletes aimed at a drive root / system dir (cmd and PowerShell forms, any flag order)
    rf"\b(?:rd|rmdir)\b(?=[^&|;\n]*\s/s\b)[^&|;\n]*?{_WIN_TARGET}",
    rf"\b(?:del|erase)\b(?=[^&|;\n]*\s/s\b)[^&|;\n]*?{_WIN_TARGET}",
    rf"\b(?:remove-item|ri|rm|rmdir|del|rd)\b(?=[^&|;\n]*\s-r(?:ecurse)?\b)[^&|;\n]*?{_WIN_TARGET}",
    r"\bformat(?:\.com)?\s+[a-z]:",  # format C:
    r"\b(?:format-volume|clear-disk|initialize-disk|remove-partition)\b",  # PowerShell disk wipes
    r"\bdiskpart\b",
    r"\bbcdedit\b",  # boot configuration
    r"\bvssadmin(?:\.exe)?\s+delete\s+shadows\b",
    r"\bwmic\b.*\bshadowcopy\b.*\bdelete\b",
    r"\bcipher(?:\.exe)?\s+/w\b",  # wipe free space
    r"\breg(?:\.exe)?\s+delete\s+(?:hklm|hkey_local_machine)\b",
    r"%0\s*\|\s*%0",  # cmd fork bomb
]

DANGEROUS_PATTERNS = _UNIX_PATTERNS + _WIN_PATTERNS
_DANGEROUS_COMPILED = [re.compile(p, re.IGNORECASE) for p in DANGEROUS_PATTERNS]


def is_dangerous_command(command: str) -> tuple[bool, str]:
    """Check a command against the blocklist. Returns (is_dangerous, reason).

    All patterns are checked on every platform: commands can be pasted or relayed across hosts,
    and none of the Windows patterns match ordinary POSIX commands (or vice versa).
    """
    for pattern in _DANGEROUS_COMPILED:
        if pattern.search(command):
            return True, f"Command matches dangerous pattern: {pattern.pattern}"
    return False, ""


# =============================================================================
# Output decoding
# =============================================================================


def _console_encoding() -> str | None:
    if not IS_WINDOWS:
        return None
    try:
        return f"cp{ctypes.windll.kernel32.GetOEMCP()}"
    except Exception:
        return None


_FALLBACK_ENCODING = _console_encoding()


def decode_output(data: bytes) -> str:
    """Decode command output: UTF-8 first, then (Windows) the console OEM code page."""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        if _FALLBACK_ENCODING:
            try:
                return data.decode(_FALLBACK_ENCODING)
            except (UnicodeDecodeError, LookupError):
                pass
        return data.decode("utf-8", errors="replace")


# =============================================================================
# Process termination
# =============================================================================


def _taskkill_tree(pid: int) -> None:
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)


async def kill_process_tree(proc: asyncio.subprocess.Process | subprocess.Popen) -> None:
    """Forcefully stop a shell process *and* the commands it started.

    On Windows, killing the cmd.exe wrapper leaves its children running, so the whole tree is
    killed with taskkill. On Unix this is ``proc.kill()`` (unchanged behaviour).
    """
    if proc.returncode is not None:
        return
    if IS_WINDOWS:
        await asyncio.to_thread(_taskkill_tree, proc.pid)
        if proc.returncode is None:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
    else:
        try:
            proc.kill()
        except ProcessLookupError:
            pass


async def terminate_process_tree(proc: asyncio.subprocess.Process) -> None:
    """Ask a shell process to stop. Windows has no SIGTERM for console children, so this
    kills the tree there; on Unix it sends SIGTERM to the process (unchanged behaviour)."""
    if proc.returncode is not None:
        return
    if IS_WINDOWS:
        await kill_process_tree(proc)
    else:
        try:
            proc.terminate()
        except ProcessLookupError:
            pass


__all__ = [
    "DANGEROUS_PATTERNS",
    "IS_WINDOWS",
    "decode_output",
    "is_dangerous_command",
    "kill_process_tree",
    "shell_description",
    "terminate_process_tree",
]
