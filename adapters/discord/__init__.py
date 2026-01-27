"""Discord adapter package.

Provides the DiscordAdapter class that implements the PlatformAdapter interface
for Discord integration, and DiscordGatewayClient for connecting to the gateway.
"""

from adapters.discord.adapter import DiscordAdapter
from adapters.discord.gateway_client import DiscordGatewayClient

__all__ = ["DiscordAdapter", "DiscordGatewayClient"]
