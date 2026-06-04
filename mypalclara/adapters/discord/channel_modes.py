"""Channel mode management for Discord.

Reads/writes per-channel response modes via the engine API (engine-import-free).
An in-memory cache keeps the per-message read path fast (one API call per channel,
then served from cache until cleared).
"""

from __future__ import annotations

from typing import Literal

from mypalclara.client_common.engine_client import EngineApiClient
from mypalclara.config.logging import get_logger

logger = get_logger("adapters.discord.channel_modes")

# Valid channel modes
ChannelMode = Literal["active", "mention", "off"]
DEFAULT_CHANNEL_MODE: ChannelMode = "mention"


class ChannelModeManager:
    """Manages channel mode settings with caching.

    Channel modes determine when Clara responds:
    - "active": Clara responds to all messages in the channel
    - "mention": Clara only responds when mentioned (default)
    - "off": Clara doesn't respond even when mentioned
    """

    def __init__(self) -> None:
        """Initialize the channel mode manager."""
        self._cache: dict[str, ChannelMode] = {}

    async def get_mode(self, channel_id: str) -> ChannelMode:
        """Get the mode for a channel (cached; engine API on miss)."""
        if channel_id in self._cache:
            return self._cache[channel_id]

        mode = await self._load_from_engine(channel_id)
        self._cache[channel_id] = mode
        return mode

    async def set_mode(
        self,
        channel_id: str,
        mode: ChannelMode,
        guild_id: str,
        configured_by: str | None = None,
    ) -> bool:
        """Set the mode for a channel via the engine API, updating the cache."""
        try:
            await EngineApiClient().set_channel_mode(channel_id, guild_id, mode, configured_by)
            self._cache[channel_id] = mode
            logger.info(f"Channel {channel_id} mode set to {mode}")
            return True
        except Exception as e:
            logger.error(f"Failed to set channel mode: {e}")
            return False

    def clear_cache(self, channel_id: str | None = None) -> None:
        """Clear the cache for a specific channel or all channels."""
        if channel_id:
            self._cache.pop(channel_id, None)
        else:
            self._cache.clear()

    async def _load_from_engine(self, channel_id: str) -> ChannelMode:
        """Fetch a channel's mode from the engine, defaulting on any error."""
        try:
            data = await EngineApiClient().get_channel_mode(channel_id)
            mode = data.get("mode")
            if mode in ("active", "mention", "off"):
                return mode
            return DEFAULT_CHANNEL_MODE
        except Exception as e:
            logger.debug(f"Failed to load channel mode from engine: {e}")
            return DEFAULT_CHANNEL_MODE


# Global instance for convenience
_manager: ChannelModeManager | None = None


def get_channel_mode_manager() -> ChannelModeManager:
    """Get the global channel mode manager instance."""
    global _manager
    if _manager is None:
        _manager = ChannelModeManager()
    return _manager


async def get_channel_mode(channel_id: str) -> ChannelMode:
    """Convenience function to get a channel's mode."""
    return await get_channel_mode_manager().get_mode(channel_id)


async def set_channel_mode(
    channel_id: str,
    mode: ChannelMode,
    guild_id: str,
    configured_by: str | None = None,
) -> bool:
    """Convenience function to set a channel's mode."""
    return await get_channel_mode_manager().set_mode(channel_id, mode, guild_id, configured_by)
