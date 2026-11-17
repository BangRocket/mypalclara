"""Cross-platform shutdown signal handling for asyncio entry points."""

from __future__ import annotations

import asyncio
import signal
from collections.abc import Callable


def install_shutdown_handler(loop: asyncio.AbstractEventLoop, callback: Callable[[], None]) -> None:
    """Call ``callback`` on the event loop when SIGINT/SIGTERM arrives.

    Uses ``loop.add_signal_handler`` where supported (Unix). On Windows that raises
    NotImplementedError, so fall back to ``signal.signal`` and hop onto the loop thread.
    Windows only delivers SIGINT (Ctrl+C) / SIGBREAK to Python; a hard kill
    (``taskkill /F``) bypasses handlers entirely.
    """
    sigs = [signal.SIGINT, signal.SIGTERM]
    if hasattr(signal, "SIGBREAK"):
        sigs.append(signal.SIGBREAK)

    for sig in sigs:
        try:
            loop.add_signal_handler(sig, callback)
        except NotImplementedError:
            signal.signal(sig, lambda _signum, _frame: loop.call_soon_threadsafe(callback))
