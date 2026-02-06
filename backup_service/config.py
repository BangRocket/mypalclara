"""Backup service configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BackupConfig:
    """Configuration for the backup service, loaded from environment variables."""

    # Databases
    clara_db_url: str = ""
    rook_db_url: str = ""

    # Storage
    storage_type: str = "local"  # "local" or "s3"
    local_backup_dir: Path = field(default_factory=lambda: Path("./backups"))

    # S3 settings (only when storage_type=s3)
    s3_bucket: str = ""
    s3_endpoint_url: str = "https://s3.wasabisys.com"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_region: str = "us-east-1"

    # Behavior
    retention_days: int = 7
    compression_level: int = 9
    dump_timeout: int = 600
    respawn_hours: int = 23
    force: bool = False

    # FalkorDB (optional graph memory backup)
    falkordb_host: str = ""
    falkordb_port: int = 6379
    falkordb_password: str = ""

    # Config file backup (optional)
    config_paths: list[str] = field(default_factory=list)

    # DB retry
    db_retry_attempts: int = 5
    db_retry_delay: int = 2

    # Health / cron
    health_port: int = 8080
    cron_schedule: str = "0 3 * * *"

    @classmethod
    def from_env(cls) -> BackupConfig:
        """Load configuration from environment variables."""
        return cls(
            # Databases
            clara_db_url=os.getenv("DATABASE_URL", ""),
            rook_db_url=os.getenv("ROOK_DATABASE_URL", os.getenv("MEM0_DATABASE_URL", "")),
            # Storage
            storage_type=os.getenv("BACKUP_STORAGE", "local"),
            local_backup_dir=Path(os.getenv("BACKUP_LOCAL_DIR", "./backups")),
            # S3
            s3_bucket=os.getenv("S3_BUCKET", ""),
            s3_endpoint_url=os.getenv("S3_ENDPOINT_URL", "https://s3.wasabisys.com"),
            s3_access_key=os.getenv("S3_ACCESS_KEY", ""),
            s3_secret_key=os.getenv("S3_SECRET_KEY", ""),
            s3_region=os.getenv("S3_REGION", "us-east-1"),
            # Behavior
            retention_days=int(os.getenv("BACKUP_RETENTION_DAYS", "7")),
            compression_level=int(os.getenv("BACKUP_COMPRESSION_LEVEL", "9")),
            dump_timeout=int(os.getenv("BACKUP_DUMP_TIMEOUT", "600")),
            respawn_hours=int(os.getenv("RESPAWN_PROTECTION_HOURS", "23")),
            force=os.getenv("FORCE_BACKUP", "").lower() == "true",
            # FalkorDB
            falkordb_host=os.getenv("FALKORDB_HOST", ""),
            falkordb_port=int(os.getenv("FALKORDB_PORT", "6379")),
            falkordb_password=os.getenv("FALKORDB_PASSWORD", ""),
            # Config file backup
            config_paths=[p.strip() for p in os.getenv("BACKUP_CONFIG_PATHS", "").split(",") if p.strip()],
            # DB retry
            db_retry_attempts=int(os.getenv("DB_RETRY_ATTEMPTS", "5")),
            db_retry_delay=int(os.getenv("DB_RETRY_DELAY", "2")),
            # Health / cron
            health_port=int(os.getenv("HEALTH_PORT", os.getenv("PORT", "8080"))),
            cron_schedule=os.getenv("BACKUP_CRON_SCHEDULE", "0 3 * * *"),
        )

    @property
    def falkordb_enabled(self) -> bool:
        """True when FalkorDB host is configured."""
        return bool(self.falkordb_host)

    @property
    def config_backup_enabled(self) -> bool:
        """True when config file paths are configured."""
        return bool(self.config_paths)

    @property
    def databases(self) -> dict[str, str]:
        """Return configured database URLs keyed by name."""
        dbs = {}
        if self.clara_db_url:
            dbs["clara"] = self.clara_db_url
        if self.rook_db_url:
            dbs["rook"] = self.rook_db_url
        return dbs
