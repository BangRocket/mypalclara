# Backup Service

Automated database backup service for S3-compatible storage.

## Overview

The backup service provides:
- Automated PostgreSQL backups (Clara DB + Mem0 DB)
- S3-compatible storage (Wasabi, AWS S3, MinIO, etc.)
- Gzip compression
- Configurable retention policy
- Respawn protection (prevents duplicate backups)
- Health check endpoints

## Location

```
backup_service/
├── backup.py       # Main backup script
├── Dockerfile      # Container image
└── requirements.txt
```

## Configuration

```bash
# Database connections
DATABASE_URL=postgresql://user:pass@host:5432/clara_main
MEM0_DATABASE_URL=postgresql://user:pass@host:5432/clara_vectors

# S3 storage
S3_BUCKET=clara-backups
S3_ENDPOINT_URL=https://s3.wasabisys.com
S3_ACCESS_KEY=your-access-key
S3_SECRET_KEY=your-secret-key
S3_REGION=us-east-1

# Backup settings
BACKUP_RETENTION_DAYS=7              # Days to keep backups
RESPAWN_PROTECTION_HOURS=23          # Min hours between backups
FORCE_BACKUP=false                   # Bypass respawn protection

# Retry settings
DB_RETRY_ATTEMPTS=5                  # Max connection retries
DB_RETRY_DELAY=2                     # Initial retry delay (seconds)
```

## Usage

### Run Backup

```bash
cd backup_service
python backup.py
```

### List Backups

```bash
python backup.py --list
```

Output:
```
Available backups in clara-backups:

Clara DB backups:
  - backups/clara/clara_20260201_030000.sql.gz (2.5 MB)
  - backups/clara/clara_20260131_030000.sql.gz (2.4 MB)

Mem0 DB backups:
  - backups/mem0/mem0_20260201_030000.sql.gz (1.2 MB)
  - backups/mem0/mem0_20260131_030000.sql.gz (1.1 MB)
```

### Show Restore Instructions

```bash
python backup.py --restore
```

### Health Server Only

```bash
python backup.py --server
```

Starts health check server without running backup.

## Restore from Backup

### 1. Download Backup

```bash
# Using AWS CLI
aws s3 cp s3://clara-backups/backups/clara/clara_20260201_030000.sql.gz . \
  --endpoint-url=https://s3.wasabisys.com

# Or using boto3 script
python -c "
import boto3
s3 = boto3.client('s3', endpoint_url='https://s3.wasabisys.com')
s3.download_file('clara-backups', 'backups/clara/clara_20260201_030000.sql.gz', 'backup.sql.gz')
"
```

### 2. Decompress

```bash
gunzip clara_20260201_030000.sql.gz
```

### 3. Restore

```bash
# Full restore (WARNING: drops existing data)
psql $DATABASE_URL < clara_20260201_030000.sql

# Or restore to new database first
createdb clara_restore
psql postgresql://user:pass@host:5432/clara_restore < clara_20260201_030000.sql
```

## Railway Deployment

### Setup

1. Create new service from `backup_service/` directory
2. Set root directory to `backup_service`
3. Configure environment variables
4. Set cron schedule

### Cron Configuration

In Railway service settings:
```
Cron Schedule: 0 3 * * *
```

This runs daily at 3:00 AM UTC.

### Dockerfile

```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y postgresql-client && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY backup.py .

CMD ["python", "backup.py"]
```

## Features

### Respawn Protection

Prevents duplicate backups when Railway restarts containers:

- Checks S3 for most recent backup timestamp
- Skips if last backup was within `RESPAWN_PROTECTION_HOURS`
- Bypass with `FORCE_BACKUP=true`

### Retention Policy

Automatically deletes backups older than `BACKUP_RETENTION_DAYS`:

1. Lists all backups in S3
2. Parses timestamps from filenames
3. Deletes expired backups
4. Logs cleanup actions

### Health Checks

Endpoints for container orchestration:

| Endpoint | Description |
|----------|-------------|
| `/health` | General health check |
| `/ready` | Readiness probe |
| `/live` | Liveness probe |

### Retry Logic

Exponential backoff for database connections:

```python
# Attempt 1: wait 2s
# Attempt 2: wait 4s
# Attempt 3: wait 8s
# Attempt 4: wait 16s
# Attempt 5: wait 32s
```

## S3 Providers

### Wasabi (Recommended)

```bash
S3_ENDPOINT_URL=https://s3.wasabisys.com
S3_REGION=us-east-1
```

Cost-effective, S3-compatible, no egress fees.

### AWS S3

```bash
S3_ENDPOINT_URL=https://s3.amazonaws.com
S3_REGION=us-east-1
```

### MinIO (Self-hosted)

```bash
S3_ENDPOINT_URL=https://minio.example.com
S3_REGION=us-east-1
```

## Backup Structure

```
s3://clara-backups/
├── backups/
│   ├── clara/
│   │   ├── clara_20260201_030000.sql.gz
│   │   ├── clara_20260131_030000.sql.gz
│   │   └── ...
│   └── mem0/
│       ├── mem0_20260201_030000.sql.gz
│       ├── mem0_20260131_030000.sql.gz
│       └── ...
└── metadata/
    └── last_backup.json
```

## Monitoring

### Logs

Check Railway logs for backup status:

```
2026-02-01 03:00:00 - Starting backup...
2026-02-01 03:00:05 - Clara DB backup complete: clara_20260201_030000.sql.gz (2.5 MB)
2026-02-01 03:00:10 - Mem0 DB backup complete: mem0_20260201_030000.sql.gz (1.2 MB)
2026-02-01 03:00:12 - Cleanup: removed 2 expired backups
2026-02-01 03:00:12 - Backup complete
```

### Alerts

Set up Railway notifications for failed deployments to catch backup failures.

## See Also

- [[Deployment]] - Production deployment guide
- [[Configuration]] - Database configuration
- [[Troubleshooting]] - Common issues
