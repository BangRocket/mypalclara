"""Gateway API authentication — dual-path: Clerk JWT or X-Canonical-User-Id."""

from __future__ import annotations

import logging
import os

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from mypalclara.db.connection import SessionLocal
from mypalclara.db.models import CanonicalUser, PlatformLink
from mypalclara.gateway.api.clerk_auth import verify_clerk_jwt

logger = logging.getLogger("gateway.api.auth")


def get_db():
    """Yield a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def _resolve_user_from_clerk(claims: dict, db: DBSession) -> CanonicalUser:
    """Find or create a CanonicalUser from Clerk JWT claims.

    Looks up by the Clerk platform link. If no user exists yet,
    auto-creates one with status='active'.
    """
    clerk_user_id = claims.get("sub")
    if not clerk_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT missing sub claim",
        )

    # Look up existing platform link
    link = (
        db.query(PlatformLink)
        .filter(PlatformLink.platform == "clerk", PlatformLink.platform_user_id == clerk_user_id)
        .first()
    )

    if link:
        user = db.query(CanonicalUser).filter(CanonicalUser.id == link.canonical_user_id).first()
        if not user:
            # Orphaned link -- shouldn't happen but handle gracefully
            logger.warning("Orphaned PlatformLink for clerk user %s", clerk_user_id)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        # Sync display_name from Clerk if available and changed
        clerk_name = claims.get("name") or claims.get("first_name")
        if clerk_name and user.display_name != clerk_name:
            user.display_name = clerk_name
            db.commit()

        return user

    # First login via Clerk -- create user and link
    clerk_name = claims.get("name") or claims.get("first_name") or "Clerk User"
    clerk_email = claims.get("email")
    avatar_url = claims.get("image_url") or claims.get("profile_image_url")

    user = CanonicalUser(
        display_name=clerk_name,
        primary_email=clerk_email,
        avatar_url=avatar_url,
        status="active",
    )
    db.add(user)
    db.flush()  # Get the generated id

    link = PlatformLink(
        canonical_user_id=user.id,
        platform="clerk",
        platform_user_id=clerk_user_id,
        prefixed_user_id=f"clerk-{clerk_user_id}",
        display_name=clerk_name,
        linked_via="clerk_jwt",
    )
    db.add(link)
    db.commit()

    logger.info("Created new CanonicalUser %s from Clerk user %s", user.id, clerk_user_id)
    return user


async def get_current_user(
    authorization: str | None = Header(None),
    x_canonical_user_id: str | None = Header(None),
    x_gateway_secret: str | None = Header(None),
    db: DBSession = Depends(get_db),
) -> CanonicalUser:
    """Resolve the current user via one of two paths:

    1. Authorization: Bearer <clerk-jwt> — validates JWT, finds/creates user
    2. X-Canonical-User-Id — trusted internal header (Discord, adapters)
    """
    # Path 1: Clerk JWT
    if authorization and authorization.startswith("Bearer "):
        claims = await verify_clerk_jwt(authorization)
        return await _resolve_user_from_clerk(claims, db)

    # Path 2: Internal header (adapters)
    expected_secret = os.getenv("CLARA_GATEWAY_SECRET")
    if expected_secret and x_gateway_secret != expected_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing gateway secret",
        )

    if not x_canonical_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
        )

    user = db.query(CanonicalUser).filter(CanonicalUser.id == x_canonical_user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


def get_approved_user(
    user: CanonicalUser = Depends(get_current_user),
) -> CanonicalUser:
    """Require an approved (active) user. Raises 403 if pending/suspended."""
    user_status = getattr(user, "status", "active")
    if user_status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is {user_status}. Admin approval required.",
        )
    return user


def get_admin_user(
    user: CanonicalUser = Depends(get_approved_user),
) -> CanonicalUser:
    """Require an admin user."""
    if not getattr(user, "is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
