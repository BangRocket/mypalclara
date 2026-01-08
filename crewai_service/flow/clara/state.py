"""Pydantic state models for ClaraFlow."""

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from crewai_service.contracts.messages import InboundMessage, OutboundMessage


def _utc_now() -> datetime:
    """Get current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


def _default_inbound() -> InboundMessage:
    """Create default inbound message for state initialization."""
    return InboundMessage(
        source="discord",
        user_id="unset",
        user_name="unset",
        content="",
        timestamp=datetime.now(timezone.utc),
    )


def _default_outbound() -> OutboundMessage:
    """Create default outbound message for state initialization."""
    return OutboundMessage(content="")


class ConversationContext(BaseModel):
    """Context for a single conversation turn.

    Built from InboundMessage metadata for internal Flow use.
    """

    # User identity (default needed for CrewAI Flow state initialization)
    user_id: str = "unset"
    platform: str = "discord"

    # Location
    channel_id: Optional[str] = None
    guild_id: Optional[str] = None
    thread_id: Optional[str] = None
    is_dm: bool = False

    # Display info
    user_display_name: str = ""
    guild_name: Optional[str] = None
    channel_name: Optional[str] = None

    # Participants in channel (for memory context)
    participants: list[dict[str, Any]] = Field(default_factory=list)

    @classmethod
    def from_inbound(cls, inbound: InboundMessage) -> "ConversationContext":
        """Create ConversationContext from InboundMessage.

        Args:
            inbound: Normalized inbound message from Crew

        Returns:
            ConversationContext populated from message metadata
        """
        meta = inbound.metadata
        return cls(
            user_id=inbound.user_id,
            platform=inbound.source,
            channel_id=meta.get("channel_id"),
            guild_id=meta.get("guild_id"),
            thread_id=meta.get("thread_id"),
            is_dm=meta.get("is_dm", False),
            user_display_name=inbound.user_name,
            guild_name=meta.get("guild_name"),
            channel_name=meta.get("channel_name"),
            participants=meta.get("participants", []),
        )


class ClaraState(BaseModel):
    """State for Clara Flow - persists across conversation steps."""

    # Contract messages (Crew ↔ Flow interface)
    inbound: InboundMessage = Field(default_factory=_default_inbound)
    outbound: OutboundMessage = Field(default_factory=_default_outbound)

    # Conversation context (built from inbound)
    context: ConversationContext = Field(
        default_factory=lambda: ConversationContext(user_id="unset")
    )

    # Input (extracted from inbound for convenience)
    user_message: str = ""
    attachments: list[str] = Field(default_factory=list)

    # Memory retrieval
    user_memories: list[str] = Field(default_factory=list)
    project_memories: list[str] = Field(default_factory=list)
    thread_summary: Optional[str] = None
    recent_messages: list[dict[str, str]] = Field(default_factory=list)

    # Prompt building
    system_prompt: str = ""
    context_block: str = ""
    full_messages: list[dict[str, str]] = Field(default_factory=list)

    # Generation
    response: str = ""
    tier: str = "mid"

    # Metadata
    started_at: datetime = Field(default_factory=_utc_now)
    completed_at: Optional[datetime] = None
