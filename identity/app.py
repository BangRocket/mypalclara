"""FastAPI application for the identity service."""

from __future__ import annotations

import json
import logging
import os

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from identity import jwt_service, oauth
from identity.config import PROVIDERS, SERVICE_SECRET, available_providers
from identity.db import (
    CanonicalUser,
    OAuthToken,
    PlatformLink,
    gen_uuid,
    get_db,
    utcnow,
)

logger = logging.getLogger("identity")


class AuthorizeRequest(BaseModel):
    provider: str


class CallbackRequest(BaseModel):
    provider: str
    code: str


class RefreshRequest(BaseModel):
    token: str


class EnsureLinkRequest(BaseModel):
    provider: str
    platform_user_id: str
    display_name: str = "User"


class UserResponse(BaseModel):
    id: str
    display_name: str
    avatar_url: str | None = None
    email: str | None = None


class LinkResponse(BaseModel):
    platform: str
    platform_user_id: str
    display_name: str | None = None
    linked_at: str | None = None


def require_service_secret(x_service_secret: str | None = Header(None)):
    if not SERVICE_SECRET:
        return
    if x_service_secret != SERVICE_SECRET:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid service secret")


def get_current_user_from_jwt(
    authorization: str | None = Header(None),
    db: DBSession = Depends(get_db),
) -> CanonicalUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid token")

    payload = jwt_service.decode(authorization.removeprefix("Bearer ").strip())
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = db.query(CanonicalUser).filter(CanonicalUser.id == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def find_or_create_user(
    provider: str,
    profile: dict,
    token_data: dict,
    db: DBSession,
) -> CanonicalUser:
    normalized = oauth.normalize_profile(provider, profile)
    platform_user_id = normalized["platform_user_id"]
    prefixed = f"{provider}-{platform_user_id}"

    link = (
        db.query(PlatformLink)
        .filter(
            PlatformLink.platform == provider,
            PlatformLink.platform_user_id == platform_user_id,
        )
        .first()
    )

    if link:
        user = link.canonical_user
        if normalized["display_name"] and normalized["display_name"] != user.display_name:
            user.display_name = normalized["display_name"]
        if normalized["avatar_url"] and normalized["avatar_url"] != user.avatar_url:
            user.avatar_url = normalized["avatar_url"]
        if normalized["email"] and not user.primary_email:
            user.primary_email = normalized["email"]
        user.updated_at = utcnow()
    else:
        user = CanonicalUser(
            id=gen_uuid(),
            display_name=normalized["display_name"],
            primary_email=normalized["email"],
            avatar_url=normalized["avatar_url"],
        )
        db.add(user)
        db.flush()

        link = PlatformLink(
            id=gen_uuid(),
            canonical_user_id=user.id,
            platform=provider,
            platform_user_id=platform_user_id,
            prefixed_user_id=prefixed,
            display_name=normalized["display_name"],
            linked_via="oauth",
        )
        db.add(link)

    existing_token = (
        db.query(OAuthToken)
        .filter(
            OAuthToken.canonical_user_id == user.id,
            OAuthToken.provider == provider,
        )
        .first()
    )

    if existing_token:
        existing_token.access_token = token_data.get("access_token", "")
        existing_token.refresh_token = token_data.get("refresh_token")
        existing_token.provider_user_id = platform_user_id
        existing_token.provider_data = json.dumps(profile)
        existing_token.updated_at = utcnow()
    else:
        oauth_token = OAuthToken(
            id=gen_uuid(),
            canonical_user_id=user.id,
            provider=provider,
            access_token=token_data.get("access_token", ""),
            refresh_token=token_data.get("refresh_token"),
            provider_user_id=platform_user_id,
            provider_data=json.dumps(profile),
        )
        db.add(oauth_token)

    db.commit()
    db.refresh(user)
    return user


def create_app() -> FastAPI:
    app = FastAPI(
        title="Clara Identity Service",
        description="OAuth and user identity management",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    cors_origins = os.getenv("IDENTITY_CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in cors_origins],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "clara-identity"}

    @app.post("/oauth/authorize")
    async def oauth_authorize(body: AuthorizeRequest):
        if body.provider not in PROVIDERS:
            raise HTTPException(status_code=400, detail=f"Unknown provider: {body.provider}")
        if body.provider not in available_providers():
            raise HTTPException(status_code=400, detail=f"Provider not configured: {body.provider}")
        url = oauth.authorize_url(body.provider)
        return {"url": url}

    @app.post("/oauth/callback")
    async def oauth_callback(body: CallbackRequest, db: DBSession = Depends(get_db)):
        if body.provider not in PROVIDERS:
            raise HTTPException(status_code=400, detail=f"Unknown provider: {body.provider}")

        token_data = await oauth.exchange_code(body.provider, body.code)
        if "access_token" not in token_data:
            logger.error(f"Token exchange failed for {body.provider}: {token_data}")
            raise HTTPException(status_code=422, detail="OAuth token exchange failed")

        profile = await oauth.fetch_user_profile(body.provider, token_data["access_token"])
        user = find_or_create_user(body.provider, profile, token_data, db)
        token = jwt_service.encode(user.id, name=user.display_name)

        return {
            "token": token,
            "user": {
                "id": user.id,
                "display_name": user.display_name,
                "avatar_url": user.avatar_url,
                "email": user.primary_email,
            },
        }

    @app.post("/oauth/refresh")
    async def oauth_refresh(body: RefreshRequest):
        payload = jwt_service.decode(body.token)
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        new_token = jwt_service.encode(payload["sub"], name=payload.get("name", ""))
        return {"token": new_token}

    @app.get("/users/me")
    async def get_me(
        user: CanonicalUser = Depends(get_current_user_from_jwt),
        db: DBSession = Depends(get_db),
    ):
        links = db.query(PlatformLink).filter(PlatformLink.canonical_user_id == user.id).all()
        return {
            "id": user.id,
            "display_name": user.display_name,
            "avatar_url": user.avatar_url,
            "email": user.primary_email,
            "status": user.status,
            "is_admin": user.is_admin,
            "links": [
                {
                    "platform": link.platform,
                    "platform_user_id": link.platform_user_id,
                    "display_name": link.display_name,
                    "linked_at": link.linked_at.isoformat() if link.linked_at else None,
                }
                for link in links
            ],
        }

    @app.get("/users/by-platform/{provider}/{platform_user_id}")
    async def get_user_by_platform(
        provider: str,
        platform_user_id: str,
        db: DBSession = Depends(get_db),
        _=Depends(require_service_secret),
    ):
        link = (
            db.query(PlatformLink)
            .filter(
                PlatformLink.platform == provider,
                PlatformLink.platform_user_id == platform_user_id,
            )
            .first()
        )
        if not link:
            raise HTTPException(status_code=404, detail="User not found")
        user = link.canonical_user
        return {
            "id": user.id,
            "display_name": user.display_name,
            "avatar_url": user.avatar_url,
            "email": user.primary_email,
        }

    @app.post("/users/ensure-link")
    async def ensure_link(
        body: EnsureLinkRequest,
        db: DBSession = Depends(get_db),
        _=Depends(require_service_secret),
    ):
        prefixed = f"{body.provider}-{body.platform_user_id}"

        link = (
            db.query(PlatformLink)
            .filter(
                PlatformLink.platform == body.provider,
                PlatformLink.platform_user_id == body.platform_user_id,
            )
            .first()
        )

        if link:
            return {"canonical_user_id": link.canonical_user_id}

        user = CanonicalUser(
            id=gen_uuid(),
            display_name=body.display_name,
        )
        db.add(user)
        db.flush()

        link = PlatformLink(
            id=gen_uuid(),
            canonical_user_id=user.id,
            platform=body.provider,
            platform_user_id=body.platform_user_id,
            prefixed_user_id=prefixed,
            display_name=body.display_name,
            linked_via="auto",
        )
        db.add(link)
        db.commit()

        return {"canonical_user_id": user.id}

    @app.get("/auth/config")
    async def auth_config():
        providers = available_providers()
        return {
            "dev_mode": os.environ.get("WEB_DEV_MODE") == "true",
            "providers": {p: p in providers for p in PROVIDERS},
        }

    return app
