# Backup Service

Automated database backup service with local and S3 storage, Rich CLI, and Docker Compose sidecar mode.

## Overview

The backup service provides:
- Automated PostgreSQL backups (Clara main DB + Rook vectors DB)
- Local filesystem or S3-compatible storage (Wasabi, AWS S3, MinIO)
- Gzip compression with configurable level
- Rich CLI with progress indicators and colored output
- Interactive restore from backup
- Built-in cron scheduler for Docker sidecar mode
- Respawn protection (prevents duplicate backups)
- Health check endpoints for container orchestration
- Configurable retention policy

## Package Structure

```
backup_service/
├── __init__.py          # Package marker
├── __main__.py          # python -m backup_service entry point
├── cli.py               # Typer CLI: run, list, restore, status, serve
├── config.py            # BackupConfig dataclass, env var loading
├── database.py          # pg_dump, psql restore, connection checks
├── health.py            # Health check HTTP server
├── cron.py              # Simple cron scheduler for serve mode
├── storage/
│   ├── __init__.py      # StorageBackend protocol + factory
│   ├── local.py         # Local filesystem backend
│   └── s3.py            # S3/Wasabi backend
└── Dockerfile           # Container image
```

## Installation

The backup CLI is included in the main project:

```bash
poetry install
```

## CLI Commands

All commands available via `poetry run backup <command>` or `python -m backup_service <command>`.

### `backup run`

Run database backups.

```bash
poetry run backup run                  # Backup both databases
poetry run backup run --force          # Bypass respawn protection
poetry run backup run --db clara       # Only Clara DB
poetry run backup run --db rook        # Only Rook vectors DB
```

### `backup list`

List available backups in a Rich table.

```bash
poetry run backup list                 # All backups
poetry run backup list --db clara      # Filter by database
```

### `backup restore`

Restore a database from backup.

```bash
poetry run backup restore              # Interactive: pick from list
poetry run backup restore --file X     # From local .sql.gz file
poetry run backup restore --target URL # Restore to different DB
poetry run backup restore --yes        # Skip confirmation
```

The restore command:
1. Lists available backups in a numbered table
2. Downloads from storage with progress indicator
3. Shows backup details and target database (password masked)
4. Asks for confirmation before proceeding
5. For rook DB: automatically prepends `CREATE EXTENSION IF NOT EXISTS vector;`
6. Pipes decompressed SQL to `psql`

### `backup status`

Show backup service configuration and status.

```bash
poetry run backup status
```

### `backup serve`

Run as long-lived daemon with built-in cron scheduler and health server.

```bash
poetry run backup serve                        # Use default schedule
poetry run backup serve --schedule "0 3 * * *" # Custom schedule
```

## Configuration

### Environment Variables

```bash
# Database connections
DATABASE_URL=postgresql://user:pass@host:5432/clara_main
ROOK_DATABASE_URL=postgresql://user:pass@host:5432/clara_vectors
# Fallback: MEM0_DATABASE_URL (backward compatibility)

# Storage backend
BACKUP_STORAGE=local                  # "local" (default) or "s3"
BACKUP_LOCAL_DIR=./backups            # Local backup directory

# S3 settings (when BACKUP_STORAGE=s3)
S3_BUCKET=clara-backups
S3_ENDPOINT_URL=https://s3.wasabisys.com
S3_ACCESS_KEY=your-access-key
S3_SECRET_KEY=your-secret-key
S3_REGION=us-east-1

# Backup behavior
BACKUP_RETENTION_DAYS=7              # Days to keep backups
BACKUP_COMPRESSION_LEVEL=9          # Gzip level (1-9)
BACKUP_DUMP_TIMEOUT=600             # pg_dump timeout in seconds
RESPAWN_PROTECTION_HOURS=23         # Min hours between backups
FORCE_BACKUP=false                  # Bypass respawn protection

# DB connection retry
DB_RETRY_ATTEMPTS=5                 # Max connection retries
DB_RETRY_DELAY=2                    # Initial retry delay (seconds)

# Serve mode
HEALTH_PORT=8080                    # Health check server port
BACKUP_CRON_SCHEDULE=0 3 * * *     # Cron schedule for serve mode
```

## Storage Backends

### Local (Default)

Stores backups on the local filesystem. Works with zero configuration for development.

```
./backups/
├── clara/
│   ├── clara_20260201_030000.sql.gz
│   └── clara_20260131_030000.sql.gz
├── rook/
│   ├── rook_20260201_030000.sql.gz
│   └── rook_20260131_030000.sql.gz
└── .last_backup
```

### S3-Compatible

Stores backups in S3-compatible object storage (Wasabi, AWS S3, MinIO).

```
s3://clara-backups/
└── backups/
    ├── clara/
    │   └── clara_20260201_030000.sql.gz
    ├── rook/
    │   └── rook_20260201_030000.sql.gz
    └── .last_backup
```

Backward compatibility: listing also scans the `backups/mem0/` prefix for old backups.

#### S3 Providers

**Wasabi (Recommended):**
```bash
S3_ENDPOINT_URL=https://s3.wasabisys.com
S3_REGION=us-east-1
```

**AWS S3:**
```bash
S3_ENDPOINT_URL=https://s3.amazonaws.com
S3_REGION=us-east-1
```

**MinIO (Self-hosted):**
```bash
S3_ENDPOINT_URL=https://minio.example.com
S3_REGION=us-east-1
```

## Docker Compose

The backup service runs as a sidecar container with a built-in cron scheduler.

### Start

```bash
docker compose --profile backup up -d
```

### Manual Commands

```bash
# Run backup manually
docker compose exec backup python -m backup_service run --force

# List backups
docker compose exec backup python -m backup_service list

# Check status
docker compose exec backup python -m backup_service status
```

### Configuration

Set in `.env` or docker-compose override:

```bash
BACKUP_STORAGE=local                  # or "s3"
BACKUP_RETENTION_DAYS=7
BACKUP_CRON_SCHEDULE=0 3 * * *       # Daily at 3 AM
```

For S3, also set `S3_BUCKET`, `S3_ENDPOINT_URL`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`.

## Health Checks

Available on port 8080 (configurable via `HEALTH_PORT`):

| Endpoint | Description |
|----------|-------------|
| `/health` | General health + backup state |
| `/ready` | Readiness probe |
| `/live` | Liveness probe |

## Restore from Backup

### Interactive Restore

```bash
poetry run backup restore
```

Shows a numbered list of backups, prompts for selection, confirms before restoring.

### From Local File

```bash
poetry run backup restore --file ./backups/clara/clara_20260201_030000.sql.gz
```

### To Different Database

```bash
poetry run backup restore --target postgresql://user:pass@host:5432/clara_restore
```

## See Also

- [[Deployment]] - Production deployment guide
- [[Configuration]] - Database configuration
- [[Troubleshooting]] - Common issues
