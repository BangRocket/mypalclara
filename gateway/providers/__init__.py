"""Gateway providers package - Platform provider infrastructure.

This module provides the ProviderManager singleton for managing
gateway-embedded platform providers (Discord, Email, CLI).

Usage:
    from gateway.providers import Provider, ProviderManager, get_provider_manager

    # Get the singleton manager
    manager = get_provider_manager()

    # Register a provider
    manager.register(DiscordProvider())

    # Start all providers
    await manager.start_all()

    # Get a specific provider
    discord = manager.get("discord")

    # Stop all providers
    await manager.stop_all()
"""

from __future__ import annotations

import asyncio
import logging
from typing import ClassVar

from gateway.providers.base import PlatformMessage, Provider

logger = logging.getLogger(__name__)


class ProviderManager:
    """Singleton manager for all gateway-embedded providers.

    Handles registration, lifecycle (start/stop), and lookup of providers.
    Thread-safe for concurrent start/stop operations.

    Usage:
        manager = ProviderManager.get_instance()
        manager.register(DiscordProvider())
        await manager.start_all()
        # ... application runs ...
        await manager.stop_all()
    """

    _instance: ClassVar[ProviderManager | None] = None

    def __init__(self) -> None:
        """Initialize the manager. Use get_instance() instead for singleton."""
        self._providers: dict[str, Provider] = {}
        self._lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> ProviderManager:
        """Get or create the singleton manager instance.

        Returns:
            The singleton ProviderManager instance
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance.

        Primarily useful for testing. Does NOT stop providers.
        Call stop_all() first if providers are running.
        """
        cls._instance = None

    @property
    def providers(self) -> dict[str, Provider]:
        """Get all registered providers.

        Returns:
            Dict mapping provider names to Provider instances
        """
        return self._providers.copy()

    def register(self, provider: Provider) -> None:
        """Register a provider with the manager.

        Args:
            provider: The Provider instance to register

        Raises:
            ValueError: If a provider with the same name is already registered
        """
        name = provider.name
        if name in self._providers:
            raise ValueError(
                f"Provider '{name}' is already registered. "
                f"Unregister it first with unregister('{name}')"
            )
        self._providers[name] = provider
        logger.info(f"[ProviderManager] Registered provider: {name}")

    def unregister(self, name: str) -> Provider | None:
        """Unregister a provider by name.

        Note: This does NOT stop the provider. Call stop() on the provider
        or use stop_all() before unregistering if it's running.

        Args:
            name: The provider name to unregister

        Returns:
            The unregistered Provider, or None if not found
        """
        provider = self._providers.pop(name, None)
        if provider:
            logger.info(f"[ProviderManager] Unregistered provider: {name}")
        else:
            logger.warning(f"[ProviderManager] Provider '{name}' not found for unregister")
        return provider

    def get(self, name: str) -> Provider | None:
        """Get a provider by name.

        Args:
            name: The provider name to look up

        Returns:
            The Provider instance, or None if not found
        """
        return self._providers.get(name)

    async def start_all(self) -> dict[str, bool]:
        """Start all registered providers.

        Starts providers concurrently using asyncio.gather.
        Providers that fail to start are logged but don't block others.

        Returns:
            Dict mapping provider names to success status (True/False)
        """
        async with self._lock:
            if not self._providers:
                logger.warning("[ProviderManager] No providers registered to start")
                return {}

            results: dict[str, bool] = {}

            async def start_one(name: str, provider: Provider) -> tuple[str, bool]:
                try:
                    if provider.running:
                        logger.debug(f"[ProviderManager] Provider '{name}' already running")
                        return (name, True)

                    logger.info(f"[ProviderManager] Starting provider: {name}")
                    await provider.start()
                    provider._running = True
                    logger.info(f"[ProviderManager] Provider '{name}' started successfully")
                    return (name, True)
                except Exception as e:
                    logger.error(f"[ProviderManager] Failed to start provider '{name}': {e}")
                    return (name, False)

            # Start all providers concurrently
            tasks = [start_one(name, provider) for name, provider in self._providers.items()]
            completed = await asyncio.gather(*tasks)

            for name, success in completed:
                results[name] = success

            started = sum(1 for v in results.values() if v)
            logger.info(
                f"[ProviderManager] Started {started}/{len(results)} providers"
            )
            return results

    async def stop_all(self) -> dict[str, bool]:
        """Stop all registered providers.

        Stops providers concurrently. Providers that fail to stop
        are logged but don't block others.

        Returns:
            Dict mapping provider names to success status (True/False)
        """
        async with self._lock:
            if not self._providers:
                return {}

            results: dict[str, bool] = {}

            async def stop_one(name: str, provider: Provider) -> tuple[str, bool]:
                try:
                    if not provider.running:
                        logger.debug(f"[ProviderManager] Provider '{name}' not running")
                        return (name, True)

                    logger.info(f"[ProviderManager] Stopping provider: {name}")
                    await provider.stop()
                    provider._running = False
                    logger.info(f"[ProviderManager] Provider '{name}' stopped successfully")
                    return (name, True)
                except Exception as e:
                    logger.error(f"[ProviderManager] Failed to stop provider '{name}': {e}")
                    # Mark as stopped anyway to prevent stuck state
                    provider._running = False
                    return (name, False)

            # Stop all providers concurrently
            tasks = [stop_one(name, provider) for name, provider in self._providers.items()]
            completed = await asyncio.gather(*tasks)

            for name, success in completed:
                results[name] = success

            stopped = sum(1 for v in results.values() if v)
            logger.info(
                f"[ProviderManager] Stopped {stopped}/{len(results)} providers"
            )
            return results

    async def start(self, name: str) -> bool:
        """Start a specific provider by name.

        Args:
            name: The provider name to start

        Returns:
            True if started successfully, False otherwise
        """
        async with self._lock:
            provider = self._providers.get(name)
            if not provider:
                logger.error(f"[ProviderManager] Provider '{name}' not found")
                return False

            if provider.running:
                logger.debug(f"[ProviderManager] Provider '{name}' already running")
                return True

            try:
                logger.info(f"[ProviderManager] Starting provider: {name}")
                await provider.start()
                provider._running = True
                logger.info(f"[ProviderManager] Provider '{name}' started successfully")
                return True
            except Exception as e:
                logger.error(f"[ProviderManager] Failed to start provider '{name}': {e}")
                return False

    async def stop(self, name: str) -> bool:
        """Stop a specific provider by name.

        Args:
            name: The provider name to stop

        Returns:
            True if stopped successfully, False otherwise
        """
        async with self._lock:
            provider = self._providers.get(name)
            if not provider:
                logger.error(f"[ProviderManager] Provider '{name}' not found")
                return False

            if not provider.running:
                logger.debug(f"[ProviderManager] Provider '{name}' not running")
                return True

            try:
                logger.info(f"[ProviderManager] Stopping provider: {name}")
                await provider.stop()
                provider._running = False
                logger.info(f"[ProviderManager] Provider '{name}' stopped successfully")
                return True
            except Exception as e:
                logger.error(f"[ProviderManager] Failed to stop provider '{name}': {e}")
                provider._running = False
                return False

    def __len__(self) -> int:
        """Return the number of registered providers."""
        return len(self._providers)

    def __contains__(self, name: str) -> bool:
        """Check if a provider is registered."""
        return name in self._providers

    def __repr__(self) -> str:
        """Return string representation of the manager."""
        providers = list(self._providers.keys())
        running = [n for n, p in self._providers.items() if p.running]
        return f"<ProviderManager(providers={providers}, running={running})>"


def get_provider_manager() -> ProviderManager:
    """Get the singleton ProviderManager instance.

    Convenience function for accessing the manager without importing the class.

    Returns:
        The singleton ProviderManager instance
    """
    return ProviderManager.get_instance()


__all__ = [
    "PlatformMessage",
    "Provider",
    "ProviderManager",
    "get_provider_manager",
]
