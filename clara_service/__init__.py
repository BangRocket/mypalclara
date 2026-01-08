"""CrewAI Service - Clara's mind implemented as a CrewAI Flow.

Architecture:
  Discord Bot (thin client)
         ↓
  Discord Crew (translates Discord ↔ Flow contract)
         ↓
  Clara Flow (mind - thinks, remembers, responds)
         ↓
  Discord Crew (formats response for Discord)
         ↓
  Discord Bot (delivers)
"""

from clara_service.contracts.messages import InboundMessage, OutboundMessage
from clara_service.crews.base import BaseCrew
from clara_service.flow.clara.flow import ClaraFlow, run_clara_flow

__all__ = [
    "ClaraFlow",
    "run_clara_flow",
    "InboundMessage",
    "OutboundMessage",
    "BaseCrew",
]
