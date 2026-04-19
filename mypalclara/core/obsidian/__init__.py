"""Obsidian Local REST API integration.

Provides a thin async HTTP client against the obsidian-local-rest-api
plugin (https://github.com/coddingtonbear/obsidian-local-rest-api) and
a repository for per-user ObsidianAccount configs.
"""

from mypalclara.core.obsidian.account import (
    ObsidianAccountConfig,
    delete_account,
    get_account,
    has_account,
    save_account,
    set_last_error,
    set_verified,
)
from mypalclara.core.obsidian.client import ObsidianClient, ObsidianError

__all__ = [
    "ObsidianAccountConfig",
    "ObsidianClient",
    "ObsidianError",
    "delete_account",
    "get_account",
    "has_account",
    "save_account",
    "set_last_error",
    "set_verified",
]
