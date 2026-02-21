"""Database connection and models for the identity service."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.pool import QueuePool

from identity.config import DATABASE_URL

Base = declarative_base()


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def gen_uuid() -> str:
    return str(uuid.uuid4())


class CanonicalUser(Base):
    __tablename__ = "canonical_users"

    id = Column(String, primary_key=True, default=gen_uuid)
    display_name = Column(String, nullable=False)
    primary_email = Column(String, nullable=True, unique=True)
    avatar_url = Column(String, nullable=True)
    status = Column(String, default="active", server_default="active", nullable=False)
    is_admin = Column(Boolean, default=False, server_default="0", nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    platform_links = relationship("PlatformLink", back_populates="canonical_user")
    oauth_tokens = relationship("OAuthToken", back_populates="canonical_user")


class PlatformLink(Base):
    __tablename__ = "platform_links"

    id = Column(String, primary_key=True, default=gen_uuid)
    canonical_user_id = Column(String, ForeignKey("canonical_users.id"), nullable=False)
    platform = Column(String, nullable=False)
    platform_user_id = Column(String, nullable=False)
    prefixed_user_id = Column(String, nullable=False, unique=True)
    display_name = Column(String, nullable=True)
    linked_at = Column(DateTime, default=utcnow)
    linked_via = Column(String, nullable=True)

    __table_args__ = (Index("ix_platform_link_platform_user", "platform", "platform_user_id", unique=True),)

    canonical_user = relationship("CanonicalUser", back_populates="platform_links")


class OAuthToken(Base):
    __tablename__ = "oauth_tokens"

    id = Column(String, primary_key=True, default=gen_uuid)
    canonical_user_id = Column(String, ForeignKey("canonical_users.id"), nullable=False)
    provider = Column(String, nullable=False)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    scopes = Column(Text, nullable=True)
    provider_user_id = Column(String, nullable=True)
    provider_data = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    __table_args__ = (Index("ix_oauth_token_user_provider", "canonical_user_id", "provider", unique=True),)

    canonical_user = relationship("CanonicalUser", back_populates="oauth_tokens")


_db_url = DATABASE_URL
if _db_url and _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql://", 1)

if _db_url and _db_url.startswith("postgresql"):
    engine = create_engine(_db_url, poolclass=QueuePool, pool_size=5, max_overflow=10, pool_pre_ping=True)
else:
    engine = create_engine("sqlite:///identity.db", echo=False)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create tables if they don't exist (idempotent)."""
    Base.metadata.create_all(bind=engine)
