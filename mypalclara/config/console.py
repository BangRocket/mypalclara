"""Console stream setup.

On Windows, when stdout/stderr are a pipe or a file (adapter subprocesses, ``> log.txt``,
``| tee``), Python encodes them with the ANSI code page (cp1252), so printing emoji or
box-drawing characters raises ``UnicodeEncodeError``. Interactive consoles are unaffected.
"""

from __future__ import annotations

import sys


def ensure_utf8_stdio() -> None:
    """Switch stdout/stderr to UTF-8 if they are using another encoding. Safe to call repeatedly."""
    for stream in (sys.stdout, sys.stderr):
        encoding = (getattr(stream, "encoding", None) or "").lower().replace("-", "")
        if encoding == "utf8" or not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except (ValueError, OSError):
            pass
