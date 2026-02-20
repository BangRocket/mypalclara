"""Microsoft Teams adapter for Clara Gateway.

This adapter enables Clara to communicate through Microsoft Teams
using the Bot Framework SDK.
"""

from mypalclara.adapters.teams.bot import TeamsBot
from mypalclara.adapters.teams.gateway_client import TeamsGatewayClient
from mypalclara.adapters.teams.message_builder import AdaptiveCardBuilder

__all__ = [
    "TeamsBot",
    "TeamsGatewayClient",
    "AdaptiveCardBuilder",
]
