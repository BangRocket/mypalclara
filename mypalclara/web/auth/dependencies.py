"""FastAPI authentication dependencies."""

from __future__ import annotations

from fastapi import Cookie, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session as DBSession

from db.connection import SessionLocal
from db.models import CanonicalUser
from mypalclara.web.auth.session import decode_access_token


def get_db():
    """Yield a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    access_token: str | None = Cookie(None),
    token: str | None = Query(None, description="Token for WebSocket auth"),
    db: DBSession = Depends(get_db),
) -> CanonicalUser:
    """Extract the current authenticated user from JWT cookie or query param.

    Raises HTTPException 401 if not authenticated.
    """
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
    if not access_token:
        return None
    payload = decode_access_token(access_token)
    if not payload or "sub" not in payload:
        return None
    return db.query(CanonicalUser).filter(CanonicalUser.id == payload["sub"]).first()
