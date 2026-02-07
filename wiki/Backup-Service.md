# Backup Service

Automated database backup service with local and S3 storage, Rich CLI, and Docker Compose sidecar mode.

## Overview

The backup service provides:
- Automated PostgreSQL backups (Clara main DB + Rook vectors DB)
- FalkorDB graph memory backups (RDB dump via redis-cli)
- Config file backups (.env, personality, MCP servers)
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
├── config_files.py      # Config file tar.gz backup/restore
├── database.py          # pg_dump, psql restore, redis-cli RDB dump
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
poetry run backup run                  # Backup all configured targets
poetry run backup run --force          # Bypass respawn protection
poetry run backup run --db clara       # Only Clara DB
poetry run backup run --db rook        # Only Rook vectors DB
poetry run backup run --db falkordb    # Only FalkorDB graph memory
poetry run backup run --db config      # Only config files
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
poetry run backup restore --file X     # From local backup file
poetry run backup restore --target URL # Target DB URL or output path
poetry run backup restore --yes        # Skip confirmation
```

The restore command detects backup type from file extension:

| Extension | Type | Restore behavior |
|-----------|------|-----------------|
| `.sql.gz` | PostgreSQL | Pipes decompressed SQL to `psql` |
| `.rdb.gz` | FalkorDB | Extracts RDB file + prints copy instructions |
| `.tar.gz` | Config | Extracts files to `--target` path or current directory |

PostgreSQL restore notes:
- For rook DB: automatically prepends `CREATE EXTENSION IF NOT EXISTS vector;`
- `--target` specifies the database URL to restore into

FalkorDB restore notes:
- Extracts the RDB dump to a local file
- Manual steps required: stop FalkorDB, copy RDB into data volume, restart

Config restore notes:
- `--target` specifies the output directory (default: current directory)

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

# FalkorDB backup (optional)
FALKORDB_HOST=                       # FalkorDB host (enables backup when set)
FALKORDB_PORT=6379                   # FalkorDB port
FALKORDB_PASSWORD=                   # FalkorDB password (optional)

# Config file backup (optional)
BACKUP_CONFIG_PATHS=                 # Comma-separated paths to back up

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
├── falkordb/
│   └── falkordb_20260201_030000.rdb.gz
├── config/
│   └── config_20260201_030000.tar.gz
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
    ├── falkordb/
    │   └── falkordb_20260201_030000.rdb.gz
    ├── config/
    │   └── config_20260201_030000.tar.gz
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

## Backup Targets

| Target | Extension | Enabled when | Tool |
|--------|-----------|-------------|------|
| Clara (PostgreSQL) | `.sql.gz` | `DATABASE_URL` is set | `pg_dump` |
| Rook (PostgreSQL) | `.sql.gz` | `ROOK_DATABASE_URL` is set | `pg_dump` |
| FalkorDB (graph memory) | `.rdb.gz` | `FALKORDB_HOST` is set | `redis-cli --rdb` |
| Config files | `.tar.gz` | `BACKUP_CONFIG_PATHS` is set | Python `tarfile` |

### FalkorDB

Backs up the FalkorDB graph database using `redis-cli --rdb`, which streams an RDB snapshot. The dump is gzip-compressed before storage. Requires `redis-tools` in the container (included in the Docker image).

### Config Files

Archives specified paths (files or directories) into a single `.tar.gz`. Useful for backing up `.env`, personality config, and MCP server configurations. Missing paths are skipped.

Docker Compose default: `/app/.env,/app/config/personality.md,/app/.mcp_servers`

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
