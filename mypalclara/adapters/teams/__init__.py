"""Microsoft Teams adapter for Clara Gateway.

This adapter enables Clara to communicate through Microsoft Teams
using the Bot Framework SDK.
"""

from adapters.teams.bot import TeamsBot
from adapters.teams.gateway_client import TeamsGatewayClient
from adapters.teams.message_builder import AdaptiveCardBuilder

__all__ = [
    "TeamsBot",
    "TeamsGatewayClient",
    "AdaptiveCardBuilder",
]
