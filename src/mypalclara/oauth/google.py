"""
Google OAuth token management.

Provides async access to Google OAuth tokens stored in the database.
Handles token refresh automatically when needed.

The tokens are stored by the API service (api_service/main.py) after
the user completes the OAuth flow. This module reads/refreshes them.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from sqlalchemy import Column, DateTime, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from mypalclara.config.settings import settings

logger = logging.getLogger(__name__)

# Google OAuth endpoints
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"

# Database setup
Base = declarative_base()


class GoogleOAuthToken(Base):
    """OAuth 2.0 tokens for Google Workspace integration (per-user).

    This model must match the one in api_service/main.py exactly.
    """

    __tablename__ = "google_oauth_tokens"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, unique=True, index=True)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    token_type = Column(String, default="Bearer")
    expires_at = Column(DateTime, nullable=True)
    scopes = Column(Text, nullable=True)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)


# Lazy database connection
_engine = None
_SessionLocal = None


def _get_session():
    """Get database session, creating connection if needed."""
    global _engine, _SessionLocal

    if _SessionLocal is None:
        db_url = settings.database_url or os.getenv("DATABASE_URL", "")

        if not db_url:
            logger.warning("[oauth] DATABASE_URL not set - Google OAuth unavailable")
            return None

        # Handle postgres:// vs postgresql://
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)

        _engine = create_engine(db_url, echo=False, future=True)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
        logger.info("[oauth] Database connected")

    return _SessionLocal()


async def is_connected(user_id: str) -> bool:
    """Check if user has a connected Google account."""
    session = _get_session()
    if not session:
        return False

    try:
        token = session.query(GoogleOAuthToken).filter(
            GoogleOAuthToken.user_id == user_id
        ).first()
        return token is not None
    finally:
        session.close()


async def get_valid_token(user_id: str) -> Optional[str]:
    """Get a valid access token for a user, refreshing if needed.

    Returns:
        Access token string if valid, None if not connected or refresh fails.
    """
    session = _get_session()
    if not session:
        return None

    try:
        token = session.query(GoogleOAuthToken).filter(
            GoogleOAuthToken.user_id == user_id
        ).first()

        if not token:
            logger.debug(f"[oauth] No token found for user {user_id}")
            return None

        # Check if token is expired or will expire in next 5 minutes
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if token.expires_at and token.expires_at <= now + timedelta(minutes=5):
            logger.info(f"[oauth] Token expired for {user_id}, refreshing...")

            if not token.refresh_token:
                logger.warning(f"[oauth] No refresh token for {user_id}")
                return None

            # Refresh the token
            new_token = await _refresh_token(token.refresh_token)
            if not new_token:
                logger.error(f"[oauth] Token refresh failed for {user_id}")
                return None

            # Update in database
            token.access_token = new_token["access_token"]
            token.expires_at = now + timedelta(seconds=new_token.get("expires_in", 3600))
            token.updated_at = now
            session.commit()
            logger.info(f"[oauth] Token refreshed for {user_id}")

        return token.access_token

    except Exception as e:
        logger.exception(f"[oauth] Error getting token: {e}")
        return None
    finally:
        session.close()


async def get_refresh_token(user_id: str) -> Optional[str]:
    """Get the refresh token for a user."""
    session = _get_session()
    if not session:
        return None

    try:
        token = session.query(GoogleOAuthToken).filter(
            GoogleOAuthToken.user_id == user_id
        ).first()

        return token.refresh_token if token else None
    finally:
        session.close()


async def revoke_token(user_id: str) -> bool:
    """Revoke a user's Google OAuth tokens.

    Returns:
        True if tokens were revoked/deleted, False on error.
    """
    session = _get_session()
    if not session:
        return False

    try:
        token = session.query(GoogleOAuthToken).filter(
            GoogleOAuthToken.user_id == user_id
        ).first()

        if not token:
            return True  # Nothing to revoke

        # Try to revoke the token with Google (optional, may fail)
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    GOOGLE_REVOKE_URL,
                    params={"token": token.access_token},
                    timeout=10.0,
                )
        except Exception as e:
            logger.debug(f"[oauth] Revoke request failed (continuing anyway): {e}")

        # Delete from database
        session.delete(token)
        session.commit()
        logger.info(f"[oauth] Token revoked for {user_id}")
        return True

    except Exception as e:
        logger.exception(f"[oauth] Error revoking token: {e}")
        return False
    finally:
        session.close()


async def _refresh_token(refresh_token: str) -> Optional[dict]:
    """Refresh an access token using the refresh token.

    Returns:
        Token response dict with access_token and expires_in, or None on failure.
    """
    client_id = settings.google_client_id or os.getenv("GOOGLE_CLIENT_ID", "")
    client_secret = settings.google_client_secret or os.getenv("GOOGLE_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        logger.error("[oauth] GOOGLE_CLIENT_ID/SECRET not configured for refresh")
        return None

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                logger.error(f"[oauth] Refresh failed: {response.status_code} {response.text}")
                return None

            return response.json()

    except Exception as e:
        logger.exception(f"[oauth] Refresh request error: {e}")
        return None
