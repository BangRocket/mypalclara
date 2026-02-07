"""Backup configuration models."""

from pydantic import BaseModel, Field


class S3Settings(BaseModel):
    bucket: str = ""
    endpoint_url: str = "https://s3.wasabisys.com"
    access_key: str = ""
    secret_key: str = ""
    region: str = "us-east-1"


class BackupSettings(BaseModel):
    storage: str = "local"
    local_dir: str = "./backups"
    s3: S3Settings = Field(default_factory=S3Settings)
    retention_days: int = 7
    compression_level: int = Field(default=9, ge=0, le=9)
    dump_timeout: int = 600
    respawn_protection_hours: int = 23
    force: bool = False
    config_paths: str = ""
    db_retry_attempts: int = 5
    db_retry_delay: int = 2
    health_port: int = 8080
    cron_schedule: str = "0 3 * * *"
