"""Channel registry for discovering and managing channel plugins.

Provides centralized registration and lookup of channel plugins.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from config.logging import get_logger

if TYPE_CHECKING:
    from clara_core.channels.types import ChannelId, ChannelPlugin

logger = get_logger("channels.registry")


class ChannelRegistry:
    """Registry for channel plugins.

    Provides:
    - Channel registration and discovery
    - Lookup by channel ID
    - Channel lifecycle management
    """

    _instance: ClassVar["ChannelRegistry | None"] = None

    def __init__(self) -> None:
        """Initialize the channel registry."""
        self._channels: dict[str, "ChannelPlugin[Any]"] = {}
        self._started: set[str] = set()

    @classmethod
    def get_instance(cls) -> "ChannelRegistry":
        """Get the singleton registry instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (for testing)."""
        cls._instance = None

    def register(self, plugin: "ChannelPlugin[Any]") -> None:
        """Register a channel plugin.

        Args:
            plugin: The channel plugin to register

        Raises:
            ValueError: If a channel with this ID is already registered
        """
        channel_id = str(plugin.id.value) if hasattr(plugin.id, "value") else str(plugin.id)

        if channel_id in self._channels:
            raise ValueError(f"Channel '{channel_id}' is already registered")

        self._channels[channel_id] = plugin
        logger.info(f"Registered channel: {plugin.meta.name} ({channel_id})")

    def unregister(self, channel_id: str | "ChannelId") -> bool:
        """Unregister a channel plugin.

        Args:
            channel_id: The channel ID to unregister

        Returns:
            True if unregistered, False if not found
        """
        cid = str(channel_id.value) if hasattr(channel_id, "value") else str(channel_id)

        if cid in self._channels:
            del self._channels[cid]
            self._started.discard(cid)
            logger.info(f"Unregistered channel: {cid}")
            return True
        return False

    def get(self, channel_id: str | "ChannelId") -> "ChannelPlugin[Any] | None":
        """Get a channel plugin by ID.

        Args:
            channel_id: The channel ID to look up

        Returns:
            The channel plugin or None if not found
        """
        cid = str(channel_id.value) if hasattr(channel_id, "value") else str(channel_id)
        return self._channels.get(cid)

    def get_all(self) -> list["ChannelPlugin[Any]"]:
        """Get all registered channel plugins.

        Returns:
            List of all registered plugins
        """
        return list(self._channels.values())

    def get_by_category(self, category: str) -> list["ChannelPlugin[Any]"]:
        """Get channels by category.

        Args:
            category: The category to filter by

        Returns:
            List of channels in the category
        """
        return [p for p in self._channels.values() if p.meta.category == category]

    def get_core_channels(self) -> list["ChannelPlugin[Any]"]:
        """Get all core (built-in) channels.

        Returns:
            List of core channel plugins
        """
        return [p for p in self._channels.values() if p.meta.is_core]

    def get_extension_channels(self) -> list["ChannelPlugin[Any]"]:
        """Get all extension (third-party) channels.

        Returns:
            List of extension channel plugins
        """
        return [p for p in self._channels.values() if not p.meta.is_core]

    async def start_channel(self, channel_id: str | "ChannelId") -> bool:
        """Start a channel's gateway connection.

        Args:
            channel_id: The channel to start

        Returns:
            True if started successfully
        """
        cid = str(channel_id.value) if hasattr(channel_id, "value") else str(channel_id)

        plugin = self._channels.get(cid)
        if not plugin:
            logger.error(f"Channel not found: {cid}")
            return False

        if cid in self._started:
            logger.warning(f"Channel already started: {cid}")
            return True

        # Connect via gateway adapter if available
        if plugin.gateway:
            try:
                # Gateway URL from environment or default
                import os
                gateway_url = os.getenv("CLARA_GATEWAY_URL", "ws://127.0.0.1:18789")
                success = await plugin.gateway.connect(gateway_url)
                if success:
                    self._started.add(cid)
                    logger.info(f"Started channel: {cid}")
                    return True
                else:
                    logger.error(f"Failed to connect channel {cid} to gateway")
                    return False
            except Exception as e:
                logger.exception(f"Error starting channel {cid}: {e}")
                return False
        else:
            # No gateway adapter - mark as started anyway
            self._started.add(cid)
            logger.info(f"Started channel (no gateway): {cid}")
            return True

    async def stop_channel(self, channel_id: str | "ChannelId") -> bool:
        """Stop a channel's gateway connection.

        Args:
            channel_id: The channel to stop

        Returns:
            True if stopped successfully
        """
        cid = str(channel_id.value) if hasattr(channel_id, "value") else str(channel_id)

        plugin = self._channels.get(cid)
        if not plugin:
            return False

        if cid not in self._started:
            return True

        if plugin.gateway:
            try:
                await plugin.gateway.disconnect()
            except Exception as e:
                logger.exception(f"Error stopping channel {cid}: {e}")

        self._started.discard(cid)
        logger.info(f"Stopped channel: {cid}")
        return True

    async def start_all(self) -> dict[str, bool]:
        """Start all registered channels.

        Returns:
            Dict mapping channel ID to success status
        """
        results = {}
        for cid in self._channels:
            results[cid] = await self.start_channel(cid)
        return results

    async def stop_all(self) -> None:
        """Stop all running channels."""
        for cid in list(self._started):
            await self.stop_channel(cid)

    def is_running(self, channel_id: str | "ChannelId") -> bool:
        """Check if a channel is running.

        Args:
            channel_id: The channel to check

        Returns:
            True if the channel is running
        """
        cid = str(channel_id.value) if hasattr(channel_id, "value") else str(channel_id)
        return cid in self._started

    def get_status(self) -> dict[str, dict[str, Any]]:
        """Get status of all channels.

        Returns:
            Dict mapping channel ID to status info
        """
        status = {}
        for cid, plugin in self._channels.items():
            status[cid] = {
                "name": plugin.meta.name,
                "category": plugin.meta.category,
                "is_core": plugin.meta.is_core,
                "is_running": cid in self._started,
                "capabilities": {
                    "streaming": plugin.capabilities.streaming,
                    "threading": plugin.capabilities.threading,
                    "attachments": plugin.capabilities.attachments,
                    "embeds": plugin.capabilities.embeds,
                },
            }
        return status


def get_channel_registry() -> ChannelRegistry:
    """Get the global channel registry instance."""
    return ChannelRegistry.get_instance()
