"""OAuth flow logic -- provider-agnostic."""

from __future__ import annotations

import os
from urllib.parse import urlencode

import httpx

from identity.config import PROVIDERS


def authorize_url(provider: str) -> str:
    """Build the OAuth authorize URL for a provider."""
    cfg = PROVIDERS[provider]
    params = {
        "client_id": os.environ.get(cfg["client_id_env"], ""),
        "redirect_uri": os.environ.get(cfg["redirect_uri_env"], ""),
        "response_type": "code",
        "scope": cfg["scope"],
    }
    return f"{cfg['authorize_url']}?{urlencode(params)}"


async def exchange_code(provider: str, code: str) -> dict:
    """Exchange authorization code for access token."""
    cfg = PROVIDERS[provider]
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            cfg["token_url"],
            data={
                "client_id": os.environ.get(cfg["client_id_env"], ""),
                "client_secret": os.environ.get(cfg["client_secret_env"], ""),
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": os.environ.get(cfg["redirect_uri_env"], ""),
            },
            headers={"Accept": "application/json"},
        )
        return resp.json()


async def fetch_user_profile(provider: str, access_token: str) -> dict:
    """Fetch user profile from OAuth provider."""
    cfg = PROVIDERS[provider]
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            cfg["user_url"],
            headers={"Authorization": f"Bearer {access_token}"},
        )
        return resp.json()


def normalize_profile(provider: str, raw: dict) -> dict:
    """Normalize provider-specific profile into a common format."""
    if provider == "discord":
        avatar_hash = raw.get("avatar")
        avatar_url = (
            f"https://cdn.discordapp.com/avatars/{raw['id']}/{avatar_hash}.png"
            if avatar_hash
            else None
        )
        return {
            "platform_user_id": str(raw["id"]),
            "display_name": raw.get("global_name") or raw.get("username") or "User",
            "email": raw.get("email"),
            "avatar_url": avatar_url,
        }
    elif provider == "google":
        return {
            "platform_user_id": str(raw["id"]),
            "display_name": raw.get("name") or "User",
            "email": raw.get("email"),
            "avatar_url": raw.get("picture"),
        }
    else:
        return {
            "platform_user_id": str(raw.get("id", "")),
            "display_name": raw.get("name") or raw.get("username") or "User",
            "email": raw.get("email"),
            "avatar_url": raw.get("avatar_url") or raw.get("picture"),
        }
