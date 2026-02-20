"""OAuth2 authentication flows for the web interface."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session as DBSession

from mypalclara.db.models import CanonicalUser, OAuthToken, PlatformLink, WebSession, utcnow
from mypalclara.web.auth.dependencies import DEV_USER_ID, _get_or_create_dev_user, get_current_user, get_db
from mypalclara.web.auth.session import create_access_token, hash_token
from mypalclara.web.config import get_web_config

logger = logging.getLogger("web.auth")
router = APIRouter()

# Discord OAuth2 endpoints
DISCORD_AUTH_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_USER_URL = "https://discord.com/api/v10/users/@me"

# Google OAuth2 endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USER_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


def _set_auth_cookie(response: Response, jwt_token: str, config) -> None:
    """Set the httpOnly auth cookie on a response."""
    kwargs = {
        "key": "access_token",
        "value": jwt_token,
        "httponly": True,
        "secure": config.frontend_url.startswith("https"),
        "samesite": "lax",
        "max_age": config.jwt_expire_minutes * 60,
    }
    if config.cookie_domain:
        kwargs["domain"] = config.cookie_domain
    response.set_cookie(**kwargs)


@router.get("/config")
async def auth_config():
    """Return auth configuration so the frontend knows what's available."""
    config = get_web_config()
    return {
        "dev_mode": config.dev_mode,
        "providers": {
            "discord": bool(config.discord_client_id),
            "google": bool(config.google_client_id),
        },
    }


@router.post("/dev-login")
async def dev_login(response: Response, db: DBSession = Depends(get_db)):
    """Log in as the dev user. Only available when WEB_DEV_MODE=true."""
    config = get_web_config()
    if not config.dev_mode:
        raise HTTPException(status_code=404, detail="Not found")

    user = _get_or_create_dev_user(db)
    jwt_token = create_access_token(user.id)

    web_session = WebSession(
        id=str(uuid.uuid4()),
        canonical_user_id=user.id,
        session_token_hash=hash_token(jwt_token),
    )
    db.add(web_session)
    db.commit()

    _set_auth_cookie(response, jwt_token, config)
    return {
        "user": {
            "id": user.id,
            "display_name": user.display_name,
            "email": user.primary_email,
            "avatar_url": user.avatar_url,
        },
        "token": jwt_token,
    }


@router.get("/login/{provider}")
async def login(provider: str, request: Request):
    """Redirect to OAuth provider for authentication."""
    config = get_web_config()

    if provider == "discord":
        if not config.discord_client_id:
            raise HTTPException(status_code=501, detail="Discord OAuth not configured")
        params = {
            "client_id": config.discord_client_id,
            "redirect_uri": config.discord_redirect_uri,
            "response_type": "code",
            "scope": "identify email",
        }
        return {"url": f"{DISCORD_AUTH_URL}?{urlencode(params)}"}

    elif provider == "google":
        if not config.google_client_id:
            raise HTTPException(status_code=501, detail="Google OAuth not configured")
        params = {
            "client_id": config.google_client_id,
            "redirect_uri": config.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "prompt": "consent",
        }
        return {"url": f"{GOOGLE_AUTH_URL}?{urlencode(params)}"}

    raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")


@router.get("/callback/{provider}")
async def callback(provider: str, code: str, request: Request, response: Response, db: DBSession = Depends(get_db)):
    """Handle OAuth callback, create/find user, issue JWT."""
    config = get_web_config()

    if provider == "discord":
        user_info = await _exchange_discord(code, config)
    elif provider == "google":
        user_info = await _exchange_google(code, config)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    # user_info: {"id": str, "email": str|None, "name": str, "display_name": str, "avatar_url": str|None}
    platform_prefix = f"{provider}-{user_info['id']}"

    # Check for existing platform link
    link = db.query(PlatformLink).filter(PlatformLink.prefixed_user_id == platform_prefix).first()

    if link:
        # Existing user — log in
        canonical_user = db.query(CanonicalUser).filter(CanonicalUser.id == link.canonical_user_id).first()
    else:
        # New user — create CanonicalUser + PlatformLink
        canonical_user = CanonicalUser(
            id=str(uuid.uuid4()),
            display_name=user_info.get("display_name") or user_info["name"],
            primary_email=user_info.get("email"),
            avatar_url=user_info.get("avatar_url"),
            status="pending",
        )
        db.add(canonical_user)
        db.flush()

        link = PlatformLink(
            id=str(uuid.uuid4()),
            canonical_user_id=canonical_user.id,
            platform=provider,
            platform_user_id=user_info["id"],
            prefixed_user_id=platform_prefix,
            display_name=user_info.get("display_name") or user_info["name"],
            linked_via="oauth",
        )
        db.add(link)

    # Store/update OAuth tokens
    existing_token = (
        db.query(OAuthToken)
        .filter(OAuthToken.canonical_user_id == canonical_user.id, OAuthToken.provider == provider)
        .first()
    )
    if existing_token:
        existing_token.access_token = user_info.get("access_token", "")
        existing_token.refresh_token = user_info.get("refresh_token")
        existing_token.expires_at = user_info.get("expires_at")
        existing_token.provider_user_id = user_info["id"]
        existing_token.updated_at = utcnow()
    else:
        oauth_token = OAuthToken(
            id=str(uuid.uuid4()),
            canonical_user_id=canonical_user.id,
            provider=provider,
            access_token=user_info.get("access_token", ""),
            refresh_token=user_info.get("refresh_token"),
            expires_at=user_info.get("expires_at"),
            provider_user_id=user_info["id"],
        )
        db.add(oauth_token)

    # Create JWT
    jwt_token = create_access_token(canonical_user.id)

    # Store web session
    web_session = WebSession(
        id=str(uuid.uuid4()),
        canonical_user_id=canonical_user.id,
        session_token_hash=hash_token(jwt_token),
    )
    db.add(web_session)
    db.commit()

    # Detect direct browser redirect from OAuth provider vs. frontend JS API call
    is_browser_redirect = "application/json" not in request.headers.get("content-type", "")

    if is_browser_redirect:
        # Direct browser redirect from OAuth provider — set cookie and redirect to frontend
        redirect = RedirectResponse(url=config.frontend_url, status_code=302)
        _set_auth_cookie(redirect, jwt_token, config)
        return redirect

    # API call from frontend JS — return JSON
    _set_auth_cookie(response, jwt_token, config)

    return {
        "user": {
            "id": canonical_user.id,
            "display_name": canonical_user.display_name,
            "email": canonical_user.primary_email,
            "avatar_url": canonical_user.avatar_url,
        },
        "token": jwt_token,
    }


@router.post("/logout")
async def logout(response: Response):
    """Clear the auth cookie."""
    config = get_web_config()
    kwargs = {"key": "access_token"}
    if config.cookie_domain:
        kwargs["domain"] = config.cookie_domain
    response.delete_cookie(**kwargs)
    return {"ok": True}


@router.get("/me")
async def me(user: CanonicalUser = Depends(get_current_user), db: DBSession = Depends(get_db)):
    """Get current authenticated user info with linked platforms."""
    links = db.query(PlatformLink).filter(PlatformLink.canonical_user_id == user.id).all()
    return {
        "id": user.id,
        "display_name": user.display_name,
        "email": user.primary_email,
        "avatar_url": user.avatar_url,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "status": getattr(user, "status", "active"),
        "is_admin": getattr(user, "is_admin", False),
        "platforms": [
            {
                "platform": l.platform,
                "platform_user_id": l.platform_user_id,
                "display_name": l.display_name,
                "linked_at": l.linked_at.isoformat() if l.linked_at else None,
            }
            for l in links
        ],
    }


@router.post("/link/{provider}")
async def link_account(
    provider: str,
    code: str,
    user: CanonicalUser = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Link an additional platform account to the current user."""
    config = get_web_config()

    if provider == "discord":
        user_info = await _exchange_discord(code, config)
    elif provider == "google":
        user_info = await _exchange_google(code, config)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    platform_prefix = f"{provider}-{user_info['id']}"

    # Check if already linked to someone else
    existing = db.query(PlatformLink).filter(PlatformLink.prefixed_user_id == platform_prefix).first()
    if existing:
        if existing.canonical_user_id == user.id:
            return {"ok": True, "message": "Already linked"}
        raise HTTPException(status_code=409, detail="This account is already linked to another user")

    link = PlatformLink(
        id=str(uuid.uuid4()),
        canonical_user_id=user.id,
        platform=provider,
        platform_user_id=user_info["id"],
        prefixed_user_id=platform_prefix,
        display_name=user_info.get("display_name") or user_info["name"],
        linked_via="manual",
    )
    db.add(link)

    # Store OAuth token
    oauth_token = OAuthToken(
        id=str(uuid.uuid4()),
        canonical_user_id=user.id,
        provider=provider,
        access_token=user_info.get("access_token", ""),
        refresh_token=user_info.get("refresh_token"),
        expires_at=user_info.get("expires_at"),
        provider_user_id=user_info["id"],
    )
    db.add(oauth_token)
    db.commit()

    return {"ok": True, "platform": provider, "platform_user_id": user_info["id"]}


@router.delete("/link/{provider}")
async def unlink_account(
    provider: str,
    user: CanonicalUser = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Unlink a platform account."""
    # Ensure user keeps at least one link
    links = db.query(PlatformLink).filter(PlatformLink.canonical_user_id == user.id).all()
    if len(links) <= 1:
        raise HTTPException(status_code=400, detail="Cannot unlink your only account")

    link = (
        db.query(PlatformLink)
        .filter(
            PlatformLink.canonical_user_id == user.id,
            PlatformLink.platform == provider,
        )
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")

    db.delete(link)

    # Also remove OAuth token
    token = (
        db.query(OAuthToken)
        .filter(
            OAuthToken.canonical_user_id == user.id,
            OAuthToken.provider == provider,
        )
        .first()
    )
    if token:
        db.delete(token)

    db.commit()
    return {"ok": True}


# ─── OAuth Exchange Helpers ────────────────────────────────────────────────


async def _exchange_discord(code: str, config) -> dict:
    """Exchange Discord auth code for tokens and user info."""
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            DISCORD_TOKEN_URL,
            data={
                "client_id": config.discord_client_id,
                "client_secret": config.discord_client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": config.discord_redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if token_resp.status_code != 200:
            logger.error(f"Discord token exchange failed: {token_resp.text}")
            raise HTTPException(status_code=502, detail="Discord token exchange failed")
        tokens = token_resp.json()

        user_resp = await client.get(
            DISCORD_USER_URL,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        if user_resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to fetch Discord user info")
        user_data = user_resp.json()

    avatar_url = None
    if user_data.get("avatar"):
        avatar_url = f"https://cdn.discordapp.com/avatars/{user_data['id']}/{user_data['avatar']}.png"

    expires_at = None
    if tokens.get("expires_in"):
        from datetime import timedelta

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens["expires_in"])
        expires_at = expires_at.replace(tzinfo=None)  # Naive for SQLite compat

    return {
        "id": user_data["id"],
        "email": user_data.get("email"),
        "name": user_data.get("username", ""),
        "display_name": user_data.get("global_name") or user_data.get("username", ""),
        "avatar_url": avatar_url,
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token"),
        "expires_at": expires_at,
    }


async def _exchange_google(code: str, config) -> dict:
    """Exchange Google auth code for tokens and user info."""
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": config.google_client_id,
                "client_secret": config.google_client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": config.google_redirect_uri,
            },
        )
        if token_resp.status_code != 200:
            logger.error(f"Google token exchange failed: {token_resp.text}")
            raise HTTPException(status_code=502, detail="Google token exchange failed")
        tokens = token_resp.json()

        user_resp = await client.get(
            GOOGLE_USER_URL,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        if user_resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to fetch Google user info")
        user_data = user_resp.json()

    expires_at = None
    if tokens.get("expires_in"):
        from datetime import timedelta

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens["expires_in"])
        expires_at = expires_at.replace(tzinfo=None)

    return {
        "id": user_data["id"],
        "email": user_data.get("email"),
        "name": user_data.get("name", ""),
        "display_name": user_data.get("name", ""),
        "avatar_url": user_data.get("picture"),
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token"),
        "expires_at": expires_at,
    }
