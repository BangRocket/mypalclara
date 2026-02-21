"""Configuration for the identity service."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

# JWT
JWT_SECRET = os.environ.get("IDENTITY_JWT_SECRET", "change-me-in-production")
JWT_EXPIRE_MINUTES = int(os.environ.get("IDENTITY_JWT_EXPIRE_MINUTES", "1440"))
JWT_ALGORITHM = "HS256"

# Service-to-service auth
SERVICE_SECRET = os.environ.get("IDENTITY_SERVICE_SECRET", "")

# Database
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Server
HOST = os.environ.get("IDENTITY_HOST", "0.0.0.0")
PORT = int(os.environ.get("IDENTITY_PORT", "18791"))

# OAuth providers
PROVIDERS: dict[str, dict] = {
    "discord": {
        "authorize_url": "https://discord.com/api/oauth2/authorize",
        "token_url": "https://discord.com/api/oauth2/token",
        "user_url": "https://discord.com/api/users/@me",
        "scope": "identify email",
        "client_id_env": "DISCORD_OAUTH_CLIENT_ID",
        "client_secret_env": "DISCORD_OAUTH_CLIENT_SECRET",
        "redirect_uri_env": "DISCORD_OAUTH_REDIRECT_URI",
    },
    "google": {
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "user_url": "https://www.googleapis.com/oauth2/v2/userinfo",
        "scope": "openid email profile",
        "client_id_env": "GOOGLE_OAUTH_CLIENT_ID",
        "client_secret_env": "GOOGLE_OAUTH_CLIENT_SECRET",
        "redirect_uri_env": "GOOGLE_OAUTH_REDIRECT_URI",
    },
}


def available_providers() -> list[str]:
    """Return providers that have a client_id configured."""
    return [name for name, cfg in PROVIDERS.items() if os.environ.get(cfg["client_id_env"])]
