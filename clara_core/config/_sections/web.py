"""Web interface configuration models."""

from pydantic import BaseModel, Field


class GoogleOAuthSettings(BaseModel):
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = "http://localhost:5173/auth/callback/google"


class WebSettings(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    cors_origins: str = "http://localhost:5173"
    static_dir: str = ""
    frontend_url: str = "http://localhost:5173"
    cookie_domain: str = ""
    dev_mode: bool = False
    dev_user_name: str = "Dev User"
    reload: bool = False
    google_oauth: GoogleOAuthSettings = Field(default_factory=GoogleOAuthSettings)
