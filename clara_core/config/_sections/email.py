"""Email configuration models."""

from pydantic import BaseModel


class EmailSettings(BaseModel):
    address: str = ""
    password: str = ""
    imap_server: str = "imap.titan.email"
    imap_port: int = 993
    smtp_server: str = "smtp.titan.email"
    smtp_port: int = 465
    smtp_timeout: int = 10
    notify_user: str = ""
    notify_enabled: bool = False
    check_interval: int = 60
    monitoring_enabled: bool = False
    default_poll_interval: int = 5
    error_backoff_max: int = 60
    encryption_key: str = ""
