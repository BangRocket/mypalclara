"""
Event models for Clara's input processing.

Events are normalized representations of messages from any source
(Discord, Email, Slack, API, etc.)
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Types of events Clara can receive."""

    MESSAGE = "message"
    TIMED = "timed"
    REACTION = "reaction"  # Future
    JOIN = "join"  # Future


class ChannelMode(str, Enum):
    """How Clara should behave in this channel."""

    ASSISTANT = "assistant"  # Respond when mentioned or DM'd
    CONVERSATIONAL = "conversational"  # More natural back-and-forth
    QUIET = "quiet"  # Only respond when directly addressed
    OFF = "off"  # Ignore this channel


class Attachment(BaseModel):
    """File attachment on a message."""

    id: str
    filename: str
    url: str
    content_type: Optional[str] = None
    size: Optional[int] = None


class HistoricalMessage(BaseModel):
    """A message from conversation history."""

    author: str
    content: str
    is_clara: bool = False
    timestamp: Optional[datetime] = None


class Event(BaseModel):
    """
    Normalized event from any source (Discord, scheduled, etc.).

    This is Clara's view of what happened - platform-agnostic
    and containing all context needed for processing.
    """

    id: str
    type: EventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Who/where
    user_id: str
    user_name: str
    channel_id: str
    guild_id: Optional[str] = None

    # Content
    content: Optional[str] = None
    attachments: list[Attachment] = Field(default_factory=list)

    # Context
    is_dm: bool = False
    mentioned: bool = False
    reply_to_clara: bool = False
    channel_mode: ChannelMode = ChannelMode.ASSISTANT

    # Conversation history (recent messages for context)
    conversation_history: list[HistoricalMessage] = Field(default_factory=list)

    # Continuation control
    can_spawn: bool = True  # If False, this event cannot trigger a continuation
    is_continuation: bool = False  # True if this is a spawned continuation event
    continuation_context: Optional[str] = None  # What Clara said she'd do

    # Raw data for debugging
    metadata: dict = Field(default_factory=dict)
