"""Adapters package for Clara.

This package contains platform adapters that implement the PlatformAdapter interface
defined in clara_core.platform. Each adapter translates between platform-native
objects (e.g., Discord messages) and Clara's platform-agnostic abstractions.

Available adapters:
    - discord: Discord bot adapter (adapters.discord.DiscordAdapter)
    - cli: CLI adapter for terminal interaction (adapters.cli.CLIAdapter)

Gateway clients (for connecting to Clara Gateway):
    - base: Base GatewayClient class (adapters.base.GatewayClient)
    - discord: Discord gateway client (adapters.discord.DiscordGatewayClient)

As new platforms are added, their adapters will be registered here.
"""

from adapters.base import GatewayClient

__all__ = ["GatewayClient"]
