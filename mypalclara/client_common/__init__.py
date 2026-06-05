"""Client-side shared utilities, vendored out of engine packages.

These were relocated from `mypalclara.core` / `mypalclara.tools` / `mypalclara.db`
so the client no longer imports engine internals (engine owns the DB and runtime;
clients talk to it over the API). Keep this package engine-import-free.
"""

from mypalclara.client_common.ids import gen_uuid
from mypalclara.client_common.platform import (
    PlatformAdapter,
    PlatformContext,
    PlatformMessage,
)
from mypalclara.client_common.toolspec import ToolContext, ToolDef, ToolHandler

__all__ = [
    "gen_uuid",
    "PlatformAdapter",
    "PlatformContext",
    "PlatformMessage",
    "ToolContext",
    "ToolDef",
    "ToolHandler",
]
