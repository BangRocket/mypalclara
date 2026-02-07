"""Discord configuration models."""

from pydantic import BaseModel


class DiscordSettings(BaseModel):
    bot_token: str = ""
    client_id: str = ""
    allowed_servers: str = ""
    allowed_channels: str = ""
    allowed_roles: str = ""
    max_messages: int = 25
    summary_age_minutes: int = 30
    channel_history_limit: int = 50
    monitor_port: int = 8001
    monitor_enabled: bool = True
    stop_phrases: str = "clara stop,stop clara,nevermind,never mind"
    admin_role: str = "Clara-Admin"
    api_url: str = ""
    max_image_dimension: int = 1568
    max_image_size: int = 4194304
    max_images_per_request: int = 1
    max_text_file_size: int = 102400
    oauth_client_id: str = ""
    oauth_client_secret: str = ""
    oauth_redirect_uri: str = "http://localhost:5173/auth/callback/discord"
