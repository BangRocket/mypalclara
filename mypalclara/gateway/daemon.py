"""Daemon management for Clara Gateway.

Provides Unix-style daemonization with PID file management.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"

_PID_DIR = tempfile.gettempdir() if IS_WINDOWS else "/tmp"
DEFAULT_GATEWAY_PIDFILE = os.path.join(_PID_DIR, "clara-gateway.pid")
DEFAULT_ADAPTER_PIDFILE_PATTERN = os.path.join(_PID_DIR, "clara-adapter-{name}.pid")

# Set in the environment of the detached child spawned by daemonize() on Windows.
_DAEMON_CHILD_ENV = "CLARA_GATEWAY_DAEMON_CHILD"


def _pid_alive(pid: int) -> bool:
    """Return True if a process with this PID exists.

    On Windows, os.kill(pid, 0) *terminates* the process, so query it via the Win32 API instead.
    """
    if not IS_WINDOWS:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    import ctypes
    from ctypes import wintypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    try:
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return False
        return code.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def _daemonize_windows(pidfile: str, logfile: str | None) -> None:
    """Windows stand-in for the double fork: relaunch this command as a detached process.

    The parent spawns the child and exits; the child (marked via env var) writes the PID
    file and returns so the caller continues running the gateway.
    """
    if os.environ.get(_DAEMON_CHILD_ENV) == "1":
        with open(pidfile, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
        return

    env = os.environ.copy()
    env[_DAEMON_CHILD_ENV] = "1"
    env.setdefault("PYTHONUTF8", "1")  # log file output would otherwise be cp1252
    cmd = [sys.executable, "-m", "mypalclara.gateway", *sys.argv[1:]]

    if logfile:
        Path(logfile).parent.mkdir(parents=True, exist_ok=True)
        out = open(logfile, "a+", encoding="utf-8")
    else:
        out = subprocess.DEVNULL

    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(
        cmd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=out,
        stderr=subprocess.STDOUT if logfile else subprocess.DEVNULL,
        creationflags=flags,
        close_fds=True,
    )
    print(f"Gateway daemon started (PID file: {pidfile})")
    sys.exit(0)


def daemonize(pidfile: str, logfile: str | None = None) -> None:
    """Run the rest of this process as a background daemon.

    Unix: classic double fork to fully detach from the terminal.
    Windows: relaunch as a detached process; the original process exits.

    Args:
        pidfile: Path to write the daemon's PID
        logfile: Path to redirect stdout/stderr (None = /dev/null)
    """
    # Convert relative paths to absolute before changing directory
    pidfile = os.path.abspath(pidfile)
    if logfile:
        logfile = os.path.abspath(logfile)

    if IS_WINDOWS:
        _daemonize_windows(pidfile, logfile)
        return

    # First fork - parent exits, child continues
    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    except OSError as e:
        sys.stderr.write(f"First fork failed: {e}\n")
        sys.exit(1)

    # Decouple from parent environment
    os.chdir("/")
    os.setsid()
    os.umask(0)

    # Second fork - prevents daemon from acquiring terminal
    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    except OSError as e:
        sys.stderr.write(f"Second fork failed: {e}\n")
        sys.exit(1)

    # Redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()

    if logfile:
        # Ensure log directory exists
        log_path = Path(logfile)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        # Redirect to log file
        log_fd = open(logfile, "a+", encoding="utf-8")
        os.dup2(log_fd.fileno(), sys.stdout.fileno())
        os.dup2(log_fd.fileno(), sys.stderr.fileno())
    else:
        # Redirect to /dev/null
        devnull = open("/dev/null", "r+", encoding="utf-8")
        os.dup2(devnull.fileno(), sys.stdin.fileno())
        os.dup2(devnull.fileno(), sys.stdout.fileno())
        os.dup2(devnull.fileno(), sys.stderr.fileno())

    # Write PID file
    with open(pidfile, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))


def stop_daemon(pidfile: str, timeout: float = 5.0) -> bool:
    """Stop a running daemon using its PID file.

    Args:
        pidfile: Path to the PID file
        timeout: Seconds to wait before sending SIGKILL

    Returns:
        True if daemon was stopped, False otherwise
    """
    try:
        with open(pidfile, "r", encoding="utf-8") as f:
            pid = int(f.read().strip())
    except FileNotFoundError:
        print(f"PID file not found: {pidfile}")
        return False
    except ValueError:
        print(f"Invalid PID in {pidfile}")
        _cleanup_pidfile(pidfile)
        return False

    if IS_WINDOWS:
        return _stop_windows(pid, pidfile, timeout)

    try:
        # Send SIGTERM for graceful shutdown
        os.kill(pid, signal.SIGTERM)
        print(f"Sent SIGTERM to process {pid}")

        # Wait for process to terminate
        start = time.time()
        while time.time() - start < timeout:
            try:
                os.kill(pid, 0)  # Check if process exists
                time.sleep(0.1)
            except OSError:
                # Process terminated
                _cleanup_pidfile(pidfile)
                print("Daemon stopped")
                return True

        # Process still running, send SIGKILL
        print(f"Process {pid} still running after {timeout}s, sending SIGKILL...")
        os.kill(pid, signal.SIGKILL)
        time.sleep(0.5)

        _cleanup_pidfile(pidfile)
        print("Daemon killed")
        return True

    except OSError as e:
        print(f"Failed to stop daemon: {e}")
        _cleanup_pidfile(pidfile)
        return False


def _stop_windows(pid: int, pidfile: str, timeout: float) -> bool:
    """Stop a daemon on Windows by killing its process tree (gateway + spawned adapters).

    A detached process has no console, so there is no graceful SIGTERM/CTRL_BREAK path.
    """
    if not _pid_alive(pid):
        print(f"Process {pid} not running")
        _cleanup_pidfile(pidfile)
        return False

    result = subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        capture_output=True,
        text=True,
    )
    start = time.time()
    while _pid_alive(pid) and time.time() - start < timeout:
        time.sleep(0.1)

    _cleanup_pidfile(pidfile)
    if _pid_alive(pid):
        print(f"Failed to stop daemon: {result.stderr.strip() or result.stdout.strip()}")
        return False
    print("Daemon stopped")
    return True


def get_daemon_status(pidfile: str) -> tuple[bool, int | None]:
    """Check if a daemon is running.

    Args:
        pidfile: Path to the PID file

    Returns:
        Tuple of (is_running, pid or None)
    """
    try:
        with open(pidfile, "r", encoding="utf-8") as f:
            pid = int(f.read().strip())
    except FileNotFoundError:
        return False, None
    except ValueError:
        return False, None

    if _pid_alive(pid):
        return True, pid
    # Stale PID file
    return False, pid


def check_daemon_running(pidfile: str) -> bool:
    """Check if daemon is running, clean up stale PID file if needed.

    Args:
        pidfile: Path to the PID file

    Returns:
        True if daemon is running
    """
    running, pid = get_daemon_status(pidfile)
    if not running and pid is not None:
        # Stale PID file
        _cleanup_pidfile(pidfile)
    return running


def _cleanup_pidfile(pidfile: str) -> None:
    """Remove PID file if it exists."""
    try:
        if os.path.exists(pidfile):
            os.remove(pidfile)
    except OSError:
        pass


def get_adapter_pidfile(adapter_name: str) -> str:
    """Get the PID file path for an adapter.

    Args:
        adapter_name: Name of the adapter (e.g., 'discord', 'teams')

    Returns:
        Path to the adapter's PID file
    """
    return DEFAULT_ADAPTER_PIDFILE_PATTERN.format(name=adapter_name)
