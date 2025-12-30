#!/usr/bin/env python3
"""
Database backup service for Clara.

Backs up both Clara DB and Mem0 DB to S3-compatible storage (Wasabi).
Designed to run as a Railway cron job.

Usage:
    python backup.py              # Run backup
    python backup.py --list       # List available backups
    python backup.py --restore    # Show restore instructions

Environment Variables:
    DATABASE_URL      - Clara PostgreSQL connection string
    MEM0_DATABASE_URL - Mem0 PostgreSQL connection string
    S3_BUCKET         - S3 bucket name
    S3_ENDPOINT_URL   - S3 endpoint (e.g., https://s3.wasabisys.com)
    S3_ACCESS_KEY     - S3 access key
    S3_SECRET_KEY     - S3 secret key
    S3_REGION         - S3 region (default: us-east-1)
    BACKUP_RETENTION_DAYS - Days to keep backups (default: 7)
"""

import gzip
import logging
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Configuration
CLARA_DB_URL = os.getenv("DATABASE_URL", "")
MEM0_DB_URL = os.getenv("MEM0_DATABASE_URL", "")

S3_BUCKET = os.getenv("S3_BUCKET", "clara-backups")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "https://s3.wasabisys.com")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "")
S3_REGION = os.getenv("S3_REGION", "us-east-1")

BACKUP_PREFIX = "backups"
RETENTION_DAYS = int(os.getenv("BACKUP_RETENTION_DAYS", "7"))


def get_s3_client():
    """Create S3 client."""
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT_URL,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        region_name=S3_REGION,
    )


def parse_db_url(url: str) -> dict:
    """Parse database URL into components."""
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    parsed = urlparse(url)
    return {
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "user": parsed.username,
        "password": parsed.password,
        "database": parsed.path.lstrip("/"),
    }


def dump_database(db_url: str, db_name: str) -> bytes | None:
    """Dump a PostgreSQL database using pg_dump."""
    if not db_url:
        logger.warning(f"[{db_name}] Skipped - no DATABASE_URL configured")
        return None

    db = parse_db_url(db_url)
    logger.info(f"[{db_name}] Starting dump of {db['database']}@{db['host']}")

    # Set password in environment
    env = os.environ.copy()
    env["PGPASSWORD"] = db["password"]

    cmd = [
        "pg_dump",
        "-h", db["host"],
        "-p", str(db["port"]),
        "-U", db["user"],
        "-d", db["database"],
        "--format=plain",
        "--no-owner",
        "--no-acl",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            env=env,
            timeout=600,  # 10 minute timeout
        )

        if result.returncode != 0:
            logger.error(f"[{db_name}] pg_dump failed: {result.stderr.decode()[:500]}")
            return None

        # Compress the dump
        dump_data = result.stdout
        compressed = gzip.compress(dump_data, compresslevel=9)

        ratio = (1 - len(compressed) / len(dump_data)) * 100 if dump_data else 0
        logger.info(
            f"[{db_name}] Dump complete: {len(dump_data):,} bytes -> "
            f"{len(compressed):,} bytes ({ratio:.1f}% compression)"
        )
        return compressed

    except FileNotFoundError:
        logger.error(f"[{db_name}] pg_dump not found - install postgresql-client")
        return None
    except subprocess.TimeoutExpired:
        logger.error(f"[{db_name}] pg_dump timed out after 10 minutes")
        return None
    except Exception as e:
        logger.error(f"[{db_name}] Dump failed: {e}")
        return None


def upload_backup(s3, data: bytes, db_name: str, timestamp: str) -> bool:
    """Upload backup to S3."""
    key = f"{BACKUP_PREFIX}/{db_name}/{db_name}_{timestamp}.sql.gz"

    try:
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=data,
            ContentType="application/gzip",
            Metadata={
                "backup-timestamp": timestamp,
                "database": db_name,
            },
        )
        logger.info(f"[{db_name}] Uploaded to s3://{S3_BUCKET}/{key}")
        return True
    except ClientError as e:
        logger.error(f"[{db_name}] Upload failed: {e}")
        return False


def cleanup_old_backups(s3, db_name: str) -> int:
    """Remove backups older than retention period. Returns count deleted."""
    prefix = f"{BACKUP_PREFIX}/{db_name}/"
    cutoff = datetime.now(UTC) - timedelta(days=RETENTION_DAYS)
    deleted = 0

    try:
        paginator = s3.get_paginator("list_objects_v2")

        for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
            for obj in page.get("Contents", []):
                if obj["LastModified"].replace(tzinfo=UTC) < cutoff:
                    s3.delete_object(Bucket=S3_BUCKET, Key=obj["Key"])
                    logger.info(f"[{db_name}] Deleted old backup: {obj['Key']}")
                    deleted += 1

    except ClientError as e:
        logger.warning(f"[{db_name}] Cleanup failed: {e}")

    return deleted


def list_backups(s3):
    """List all available backups."""
    print(f"\nAvailable backups in s3://{S3_BUCKET}/{BACKUP_PREFIX}/")
    print(f"Retention: {RETENTION_DAYS} days\n")

    for db_name in ["clara", "mem0"]:
        prefix = f"{BACKUP_PREFIX}/{db_name}/"
        print(f"{db_name.upper()} backups:")

        try:
            response = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=prefix)

            backups = sorted(
                response.get("Contents", []),
                key=lambda x: x["LastModified"],
                reverse=True,
            )

            if not backups:
                print("  (none)")
            else:
                for obj in backups[:10]:  # Show last 10
                    size_mb = obj["Size"] / (1024 * 1024)
                    timestamp = obj["LastModified"].strftime("%Y-%m-%d %H:%M:%S UTC")
                    filename = obj["Key"].split("/")[-1]
                    print(f"  - {filename} ({size_mb:.2f} MB, {timestamp})")

                if len(backups) > 10:
                    print(f"  ... and {len(backups) - 10} more")

        except ClientError as e:
            print(f"  Error: {e}")

        print()


def run_backup() -> bool:
    """Run backup of all databases. Returns True if all succeeded."""
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

    logger.info("=" * 60)
    logger.info(f"Clara Database Backup Service - {timestamp}")
    logger.info("=" * 60)

    # Validate configuration
    if not S3_ACCESS_KEY or not S3_SECRET_KEY:
        logger.error("S3 credentials not configured (S3_ACCESS_KEY, S3_SECRET_KEY)")
        return False

    if not CLARA_DB_URL and not MEM0_DB_URL:
        logger.error("No database URLs configured (DATABASE_URL, MEM0_DATABASE_URL)")
        return False

    try:
        s3 = get_s3_client()
        # Test S3 connection
        s3.head_bucket(Bucket=S3_BUCKET)
        logger.info(f"S3 connection OK: {S3_ENDPOINT_URL} / {S3_BUCKET}")
    except ClientError as e:
        logger.error(f"S3 connection failed: {e}")
        return False

    results = {"success": 0, "failed": 0, "skipped": 0}

    # Backup Clara DB
    logger.info("-" * 40)
    logger.info("Backing up Clara DB...")
    clara_data = dump_database(CLARA_DB_URL, "clara")
    if clara_data:
        if upload_backup(s3, clara_data, "clara", timestamp):
            results["success"] += 1
            cleanup_old_backups(s3, "clara")
        else:
            results["failed"] += 1
    elif CLARA_DB_URL:
        results["failed"] += 1
    else:
        results["skipped"] += 1

    # Backup Mem0 DB
    logger.info("-" * 40)
    logger.info("Backing up Mem0 DB...")
    mem0_data = dump_database(MEM0_DB_URL, "mem0")
    if mem0_data:
        if upload_backup(s3, mem0_data, "mem0", timestamp):
            results["success"] += 1
            cleanup_old_backups(s3, "mem0")
        else:
            results["failed"] += 1
    elif MEM0_DB_URL:
        results["failed"] += 1
    else:
        results["skipped"] += 1

    # Summary
    logger.info("=" * 60)
    logger.info(
        f"Backup complete: {results['success']} succeeded, "
        f"{results['failed']} failed, {results['skipped']} skipped"
    )

    return results["failed"] == 0


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Clara database backup service")
    parser.add_argument("--list", "-l", action="store_true", help="List available backups")
    parser.add_argument(
        "--restore", "-r", action="store_true", help="Show restore instructions"
    )
    args = parser.parse_args()

    if args.list:
        if not S3_ACCESS_KEY or not S3_SECRET_KEY:
            logger.error("S3 credentials not configured")
            sys.exit(1)
        s3 = get_s3_client()
        list_backups(s3)
    elif args.restore:
        print(
            """
To restore from backup:

1. List available backups:
   python backup.py --list

2. Download the backup file:
   aws s3 cp s3://BUCKET/backups/DB/FILE.sql.gz . --endpoint-url=ENDPOINT

3. Decompress:
   gunzip FILE.sql.gz

4. Restore to database:
   psql DATABASE_URL < FILE.sql

Or use the Wasabi/S3 console to download the file directly.

Note: For mem0 vectors, you may also need to run:
   CREATE EXTENSION IF NOT EXISTS vector;
before restoring.
"""
        )
    else:
        success = run_backup()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
