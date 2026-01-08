"""Base Crew interface.

All Crews (Discord, Email, Slack, API, etc.) implement this interface.
This abstraction allows the Flow to remain agnostic about the source/destination
of messages.
"""

from abc import ABC, abstractmethod
from typing import Any

from ..contracts.messages import InboundMessage, OutboundMessage


class BaseCrew(ABC):
    """Interface all Crews must implement.

    A Crew is responsible for:
    1. Receiving input from its source and translating to InboundMessage
    2. Delivering OutboundMessage responses back to its source

    The Crew does NOT:
    - Make decisions about how to respond (that's the Flow's job)
    - Access memory directly (that's the Flow's job)
    - Know about other Crews
    """

    @abstractmethod
    async def receive(self, raw_input: Any) -> InboundMessage:
        """Transform source-specific input into Flow contract.

        Args:
            raw_input: Source-specific input (e.g., discord.Message)

        Returns:
            Normalized InboundMessage for the Flow
        """
        pass

    @abstractmethod
    async def deliver(self, response: OutboundMessage, context: Any) -> None:
        """Transform Flow response back to source-specific output.

        Args:
            response: Normalized OutboundMessage from the Flow
            context: Source-specific context for delivery (e.g., channel to send to)
        """
        pass
