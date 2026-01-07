"""Pydantic state models for ClaraFlow."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ConversationContext(BaseModel):
    """Context for a single conversation turn."""

    # User identity
    user_id: str
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
    participants: list[dict] = Field(default_factory=list)


class ClaraState(BaseModel):
    """State for Clara Flow - persists across conversation steps."""

    # Conversation context
    context: ConversationContext

    # Input
    user_message: str = ""
    attachments: list[dict] = Field(default_factory=list)

    # Memory retrieval
    user_memories: list[str] = Field(default_factory=list)
    project_memories: list[str] = Field(default_factory=list)
    thread_summary: Optional[str] = None
    recent_messages: list[dict] = Field(default_factory=list)

    # Prompt building
    system_prompt: str = ""
    context_block: str = ""
    full_messages: list[dict] = Field(default_factory=list)

    # Generation
    response: str = ""
    tier: str = "mid"

    # Metadata
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
