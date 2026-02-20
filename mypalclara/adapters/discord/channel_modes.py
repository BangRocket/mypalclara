"""Channel mode management for Discord.

Handles:
- Per-channel response modes (active, mention, off)
- Database persistence of channel settings
"""

from __future__ import annotations

from typing import Literal

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

    def get_mode(self, channel_id: str) -> ChannelMode:
        """Get the mode for a channel.

        Args:
            channel_id: Discord channel ID

        Returns:
            Channel mode: "active", "mention", or "off"
        """
        # Check cache first
        if channel_id in self._cache:
            return self._cache[channel_id]

        # Load from database
        mode = self._load_from_db(channel_id)
        self._cache[channel_id] = mode
        return mode

    def set_mode(self, channel_id: str, mode: ChannelMode) -> bool:
        """Set the mode for a channel.

        Args:
            channel_id: Discord channel ID
            mode: New mode to set

        Returns:
            True if successful, False otherwise
        """
        try:
            self._save_to_db(channel_id, mode)
            self._cache[channel_id] = mode
            logger.info(f"Channel {channel_id} mode set to {mode}")
            return True
        except Exception as e:
            logger.error(f"Failed to set channel mode: {e}")
            return False

    def clear_cache(self, channel_id: str | None = None) -> None:
        """Clear the cache for a specific channel or all channels.

        Args:
            channel_id: Channel to clear, or None for all
        """
        if channel_id:
            self._cache.pop(channel_id, None)
        else:
            self._cache.clear()

    def _load_from_db(self, channel_id: str) -> ChannelMode:
        """Load channel mode from database.

        Args:
            channel_id: Discord channel ID

        Returns:
            Channel mode from database or default
        """
        try:
            from mypalclara.db import SessionLocal
            from mypalclara.db.models import ChannelConfig

            db = SessionLocal()
            try:
                config = db.query(ChannelConfig).filter_by(channel_id=channel_id).first()
                if config and config.mode in ("active", "mention", "off"):
                    return config.mode
                return DEFAULT_CHANNEL_MODE
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"Failed to load channel mode from db: {e}")
            return DEFAULT_CHANNEL_MODE

    def _save_to_db(self, channel_id: str, mode: ChannelMode) -> None:
        """Save channel mode to database.

        Args:
            channel_id: Discord channel ID
            mode: Mode to save
        """
        from mypalclara.db import SessionLocal
        from mypalclara.db.models import ChannelConfig

        db = SessionLocal()
        try:
            config = db.query(ChannelConfig).filter_by(channel_id=channel_id).first()
            if config:
                config.mode = mode
            else:
                config = ChannelConfig(channel_id=channel_id, mode=mode)
                db.add(config)
            db.commit()
        finally:
            db.close()


# Global instance for convenience
_manager: ChannelModeManager | None = None


def get_channel_mode_manager() -> ChannelModeManager:
    """Get the global channel mode manager instance.

    Returns:
        The ChannelModeManager singleton
    """
    global _manager
    if _manager is None:
        _manager = ChannelModeManager()
    return _manager


def get_channel_mode(channel_id: str) -> ChannelMode:
    """Convenience function to get a channel's mode.

    Args:
        channel_id: Discord channel ID

    Returns:
        Channel mode
    """
    return get_channel_mode_manager().get_mode(channel_id)


def set_channel_mode(channel_id: str, mode: ChannelMode) -> bool:
    """Convenience function to set a channel's mode.

    Args:
        channel_id: Discord channel ID
        mode: New mode

    Returns:
        True if successful
    """
    return get_channel_mode_manager().set_mode(channel_id, mode)
