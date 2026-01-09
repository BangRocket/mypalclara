"""Message contracts for Crew ↔ Flow communication.

These contracts define the interface between Crews and the Flow.
All Crews translate their source-specific formats to/from these contracts.
"""

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    """Get current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


class InboundMessage(BaseModel):
    """What Crews send TO the Flow.

    This is the normalized input format that all Crews produce.
    The Flow doesn't need to know whether the message came from
    Discord, Email, Slack, or any other source.
    """

    # Source identification
    source: Literal["discord", "email", "slack", "api"]
    user_id: str
    user_name: str

    # Message content
    content: str
    attachments: list[str] = Field(default_factory=list)  # URLs or file paths

    # Source-specific metadata (channel_id, thread_id, guild_id, etc.)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Conversation history (pre-fetched by Crew)
    recent_messages: list[dict[str, str]] = Field(default_factory=list)

    # Timing
    timestamp: datetime = Field(default_factory=_utc_now)


class OutboundMessage(BaseModel):
    """What the Flow sends BACK to Crews.

    This is the normalized output format that the Flow produces.
    Each Crew translates this to its platform-specific format.
    """

    # Response content
    content: str
    attachments: list[str] = Field(default_factory=list)  # File paths to attach

    # Routing hints for the crew (optional)
    metadata: dict[str, Any] = Field(default_factory=dict)
