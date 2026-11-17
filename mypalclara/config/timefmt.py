"""Portable datetime formatting.

``%-I`` / ``%-d`` (no zero padding) are glibc/BSD extensions; Windows' C runtime rejects
them with ``ValueError: Invalid format string``. ``strftime`` here accepts them everywhere.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time

_UNPADDED = re.compile(r"%-([a-zA-Z])")


def strftime(dt: datetime | date | time, fmt: str) -> str:
    """``dt.strftime(fmt)`` with support for ``%-X`` (unpadded) directives on all platforms."""

    def _unpad(m: re.Match[str]) -> str:
        value = dt.strftime("%" + m.group(1)).lstrip("0") or "0"
        return value.replace("%", "%%")

    return dt.strftime(_UNPADDED.sub(_unpad, fmt))
