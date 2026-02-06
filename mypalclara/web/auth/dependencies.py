"""FastAPI authentication dependencies."""

from __future__ import annotations

import uuid

from fastapi import Cookie, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session as DBSession

from db.connection import SessionLocal
from db.models import CanonicalUser, PlatformLink
from mypalclara.web.auth.session import decode_access_token
from mypalclara.web.config import get_web_config

# Stable UUID for the dev user so it persists across restarts
DEV_USER_ID = "00000000-0000-0000-0000-000000000dev"


def get_db():
    """Yield a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _get_or_create_dev_user(db: DBSession) -> CanonicalUser:
    """Return the dev user, creating it if it doesn't exist."""
    config = get_web_config()
    user = db.query(CanonicalUser).filter(CanonicalUser.id == DEV_USER_ID).first()
    if not user:
        user = CanonicalUser(
            id=DEV_USER_ID,
            display_name=config.dev_user_name,
        )
        db.add(user)

        # Create a web platform link so memory queries work
        link = PlatformLink(
            id=str(uuid.uuid4()),
            canonical_user_id=DEV_USER_ID,
            platform="web",
            platform_user_id="dev",
            prefixed_user_id=f"web-{DEV_USER_ID}",
            display_name=config.dev_user_name,
            linked_via="dev",
        )
        db.add(link)
        db.commit()
    return user


def get_current_user(
    access_token: str | None = Cookie(None),
    token: str | None = Query(None, description="Token for WebSocket auth"),
    db: DBSession = Depends(get_db),
) -> CanonicalUser:
    """Extract the current authenticated user from JWT cookie or query param.

    In dev mode, returns a dev user without requiring authentication.
    Raises HTTPException 401 if not authenticated.
    """
    config = get_web_config()
    if config.dev_mode:
        return _get_or_create_dev_user(db)

    jwt_token = access_token or token
    if not jwt_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_access_token(jwt_token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = db.query(CanonicalUser).filter(CanonicalUser.id == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


def get_optional_user(
    access_token: str | None = Cookie(None),
    db: DBSession = Depends(get_db),
) -> CanonicalUser | None:
    """Extract the current user if authenticated, else None."""
    config = get_web_config()
    if config.dev_mode:
        return _get_or_create_dev_user(db)

    if not access_token:
        return None
    payload = decode_access_token(access_token)
    if not payload or "sub" not in payload:
        return None
    return db.query(CanonicalUser).filter(CanonicalUser.id == payload["sub"]).first()
