"""Backup service configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from clara_core.config import get_settings


@dataclass
class BackupConfig:
    """Configuration for the backup service, loaded from settings."""

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
        """Load configuration from settings."""
        s = get_settings()
        backup = s.backup
        return cls(
            # Databases
            clara_db_url=s.database.url,
            rook_db_url=s.memory.vector_store.database_url,
            # Storage
            storage_type=backup.storage,
            local_backup_dir=Path(backup.local_dir),
            # S3
            s3_bucket=backup.s3.bucket,
            s3_endpoint_url=backup.s3.endpoint_url,
            s3_access_key=backup.s3.access_key,
            s3_secret_key=backup.s3.secret_key,
            s3_region=backup.s3.region,
            # Behavior
            retention_days=backup.retention_days,
            compression_level=backup.compression_level,
            dump_timeout=backup.dump_timeout,
            respawn_hours=backup.respawn_protection_hours,
            force=backup.force,
            # FalkorDB
            falkordb_host=s.memory.graph_store.falkordb_host,
            falkordb_port=s.memory.graph_store.falkordb_port,
            falkordb_password=s.memory.graph_store.falkordb_password,
            # Config file backup
            config_paths=[p.strip() for p in backup.config_paths.split(",") if p.strip()],
            # DB retry
            db_retry_attempts=backup.db_retry_attempts,
            db_retry_delay=backup.db_retry_delay,
            # Health / cron
            health_port=backup.health_port,
            cron_schedule=backup.cron_schedule,
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
