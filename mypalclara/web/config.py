"""Configuration for the web interface."""

from __future__ import annotations

from dataclasses import dataclass, field

from clara_core.config import get_settings


@dataclass
class WebConfig:
    """Web interface configuration loaded from settings."""

    # JWT
    secret_key: str = field(default_factory=lambda: get_settings().web.secret_key)
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = field(default_factory=lambda: get_settings().web.jwt_expire_minutes)

    # OAuth2 — Discord
    discord_client_id: str = field(default_factory=lambda: get_settings().discord.oauth_client_id)
    discord_client_secret: str = field(default_factory=lambda: get_settings().discord.oauth_client_secret)
    discord_redirect_uri: str = field(default_factory=lambda: get_settings().discord.oauth_redirect_uri)

    # OAuth2 — Google
    google_client_id: str = field(default_factory=lambda: get_settings().web.google_oauth.client_id)
    google_client_secret: str = field(default_factory=lambda: get_settings().web.google_oauth.client_secret)
    google_redirect_uri: str = field(default_factory=lambda: get_settings().web.google_oauth.redirect_uri)

    # Dev mode — bypasses OAuth, auto-creates a dev user
    dev_mode: bool = field(default_factory=lambda: get_settings().web.dev_mode)
    dev_user_name: str = field(default_factory=lambda: get_settings().web.dev_user_name)

    # Server
    host: str = field(default_factory=lambda: get_settings().web.host)
    port: int = field(default_factory=lambda: get_settings().web.port)
    cors_origins: list[str] = field(default_factory=lambda: get_settings().web.cors_origins.split(","))

    # Frontend
    static_dir: str = field(default_factory=lambda: get_settings().web.static_dir)
    frontend_url: str = field(default_factory=lambda: get_settings().web.frontend_url)

    # Gateway
    gateway_url: str = field(default_factory=lambda: get_settings().gateway.url)


def get_web_config() -> WebConfig:
    """Get the web configuration singleton."""
    return WebConfig()
