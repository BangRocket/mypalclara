from __future__ import annotations

from datetime import datetime, timezone
import uuid


def utcnow():
    """Return current UTC time (naive, for SQLite compatibility)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


from sqlalchemy import (
    Column,
    String,
    DateTime,
    Text,
    ForeignKey,
    Integer,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=gen_uuid)
    owner_id = Column(String, nullable=False)
    name = Column(String, nullable=False)

    sessions = relationship("Session", back_populates="project")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=gen_uuid)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    user_id = Column(String, nullable=False)
    title = Column(String, nullable=True)  # Thread title for UI
    archived = Column(String, default="false", nullable=False)  # "true" or "false"
    started_at = Column(DateTime, default=utcnow, nullable=False)
    last_activity_at = Column(DateTime, default=utcnow, nullable=False)
    previous_session_id = Column(String, nullable=True)
    context_snapshot = Column(Text, nullable=True)
    session_summary = Column(Text, nullable=True)  # LLM-generated summary

    project = relationship("Project", back_populates="sessions")
    messages = relationship("Message", back_populates="session")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    user_id = Column(String, nullable=False)
    role = Column(String, nullable=False)  # 'user' | 'assistant'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    session = relationship("Session", back_populates="messages")


class ChannelSummary(Base):
    """Rolling summary of Discord channel conversations."""

    __tablename__ = "channel_summaries"

    id = Column(String, primary_key=True, default=gen_uuid)
    channel_id = Column(String, nullable=False, unique=True)  # discord-channel-{id}
    summary = Column(Text, default="")
    summary_cutoff_at = Column(DateTime, nullable=True)  # newest summarized msg ts
    last_updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class LogEntry(Base):
    """Persistent log entries stored in the database."""

    __tablename__ = "log_entries"

    id = Column(String, primary_key=True, default=gen_uuid)
    timestamp = Column(DateTime, default=utcnow, nullable=False, index=True)
    level = Column(String(10), nullable=False, index=True)  # INFO, WARNING, ERROR, CRITICAL
    logger_name = Column(String(100), nullable=False, index=True)  # e.g., "api", "discord"
    message = Column(Text, nullable=False)
    module = Column(String(100), nullable=True)
    function = Column(String(100), nullable=True)
    line_number = Column(Integer, nullable=True)
    exception = Column(Text, nullable=True)  # Traceback if error
    extra_data = Column(Text, nullable=True)  # JSON for additional context
    user_id = Column(String, nullable=True, index=True)
    session_id = Column(String, nullable=True, index=True)


class GoogleOAuthToken(Base):
    """OAuth 2.0 tokens for Google Workspace integration (per-user)."""

    __tablename__ = "google_oauth_tokens"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, nullable=False, unique=True, index=True)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    token_type = Column(String, default="Bearer")
    expires_at = Column(DateTime, nullable=True)
    scopes = Column(Text, nullable=True)  # JSON array of granted scopes
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


# =============================================================================
# Proactive Conversation Models
# =============================================================================


class ProactiveMessage(Base):
    """History of proactive messages sent by Clara."""

    __tablename__ = "proactive_messages"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, nullable=False, index=True)
    channel_id = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    priority = Column(String, nullable=False)  # low, normal, high, critical
    reason = Column(Text, nullable=True)  # Why Clara decided to reach out
    sent_at = Column(DateTime, default=utcnow, nullable=False)
    response_received = Column(String, default="false")  # "true" or "false"
    response_at = Column(DateTime, nullable=True)


class UserInteractionPattern(Base):
    """Learned interaction patterns per user for proactive timing."""

    __tablename__ = "user_interaction_patterns"

    user_id = Column(String, primary_key=True)
    last_interaction_at = Column(DateTime, nullable=True)
    last_interaction_channel = Column(String, nullable=True)
    last_interaction_summary = Column(Text, nullable=True)  # Brief summary of last convo
    last_interaction_energy = Column(String, nullable=True)  # high, medium, low
    typical_active_hours = Column(Text, nullable=True)  # JSON: {"weekday": [9,17], "weekend": [10,22]}
    avg_response_time_seconds = Column(Integer, nullable=True)
    explicit_signals = Column(Text, nullable=True)  # JSON: {"do_not_disturb": false, "busy_until": null}
    proactive_success_rate = Column(Integer, nullable=True)  # Percentage (0-100)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class ProactiveNote(Base):
    """Notes for Clara to surface later (pending items, reminders)."""

    __tablename__ = "proactive_notes"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, nullable=False, index=True)
    note = Column(Text, nullable=False)
    surface_at = Column(DateTime, nullable=True)  # When to potentially bring this up
    surfaced = Column(String, default="false")  # "true" or "false"
    created_at = Column(DateTime, default=utcnow)
    surfaced_at = Column(DateTime, nullable=True)
