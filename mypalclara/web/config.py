"""Configuration for the web interface."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _bool(val: str) -> bool:
    return val.strip().lower() in ("true", "1", "yes")


@dataclass
class WebConfig:
    """Web interface configuration loaded from environment variables."""

    # JWT
    secret_key: str = field(default_factory=lambda: os.getenv("WEB_SECRET_KEY", "change-me-in-production"))
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = field(default_factory=lambda: int(os.getenv("WEB_JWT_EXPIRE_MINUTES", "1440")))

    # OAuth2 — Discord
    discord_client_id: str = field(default_factory=lambda: os.getenv("DISCORD_OAUTH_CLIENT_ID", ""))
    discord_client_secret: str = field(default_factory=lambda: os.getenv("DISCORD_OAUTH_CLIENT_SECRET", ""))
    discord_redirect_uri: str = field(
        default_factory=lambda: os.getenv("DISCORD_OAUTH_REDIRECT_URI", "http://localhost:5173/auth/callback/discord")
    )

    # OAuth2 — Google
    google_client_id: str = field(default_factory=lambda: os.getenv("GOOGLE_OAUTH_CLIENT_ID", ""))
    google_client_secret: str = field(default_factory=lambda: os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", ""))
    google_redirect_uri: str = field(
        default_factory=lambda: os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:5173/auth/callback/google")
    )

    # Dev mode — bypasses OAuth, auto-creates a dev user
    dev_mode: bool = field(default_factory=lambda: _bool(os.getenv("WEB_DEV_MODE", "false")))
    dev_user_name: str = field(default_factory=lambda: os.getenv("WEB_DEV_USER_NAME", "Dev User"))

    # Server
    host: str = field(default_factory=lambda: os.getenv("WEB_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("WEB_PORT", "8000")))
    cors_origins: list[str] = field(
        default_factory=lambda: os.getenv("WEB_CORS_ORIGINS", "http://localhost:5173").split(",")
    )

    # Frontend
    static_dir: str = field(default_factory=lambda: os.getenv("WEB_STATIC_DIR", "web-ui/dist"))
    frontend_url: str = field(default_factory=lambda: os.getenv("WEB_FRONTEND_URL", "http://localhost:5173"))
    cookie_domain: str = field(default_factory=lambda: os.getenv("WEB_COOKIE_DOMAIN", ""))

    # Gateway
    gateway_url: str = field(default_factory=lambda: os.getenv("CLARA_GATEWAY_URL", "ws://127.0.0.1:18789/ws"))


def get_web_config() -> WebConfig:
    """Get the web configuration singleton."""
    return WebConfig()
