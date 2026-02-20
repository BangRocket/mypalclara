"""JWT session management for the web interface."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import jwt

from mypalclara.web.config import get_web_config


def create_access_token(canonical_user_id: str, extra_claims: dict | None = None) -> str:
    """Create a JWT access token.

    Args:
        canonical_user_id: The canonical user ID to encode in the token.
        extra_claims: Additional claims to include.

    Returns:
        Encoded JWT string.
    """
    config = get_web_config()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": canonical_user_id,
        "iat": now,
        "exp": now + timedelta(minutes=config.jwt_expire_minutes),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, config.secret_key, algorithm=config.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    """Decode and validate a JWT access token.

    Args:
        token: The JWT string.

    Returns:
        Decoded payload dict, or None if invalid/expired.
    """
    config = get_web_config()
    try:
        return jwt.decode(token, config.secret_key, algorithms=[config.jwt_algorithm])
    except jwt.PyJWTError:
        return None


def create_game_redirect_token(
    canonical_user_id: str,
    display_name: str,
    avatar_url: str | None,
    audience: str = "games.mypalclara.com",
) -> str:
    """Create a short-lived JWT for game site auth redirect.

    This token is only valid for 5 minutes and scoped to the games site.
    """
    config = get_web_config()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": canonical_user_id,
        "name": display_name,
        "avatar": avatar_url,
        "aud": audience,
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    return jwt.encode(payload, config.secret_key, algorithm=config.jwt_algorithm)


def hash_token(token: str) -> str:
    """Hash a session token for DB storage."""
    return hashlib.sha256(token.encode()).hexdigest()
