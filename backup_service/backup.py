#!/usr/bin/env python3
"""
Database backup service for Clara.

Backs up both Clara DB and Mem0 DB to S3-compatible storage (Wasabi).
Designed to run as a Railway cron job with respawn protection.

Features:
- Respawn protection: Prevents duplicate backups on container restarts
- Health endpoints: /health, /ready for Railway healthchecks
- Retry logic: Exponential backoff for database connections
- Retention: Automatic cleanup of old backups

Environment Variables:
    DATABASE_URL          - Clara PostgreSQL connection string
    MEM0_DATABASE_URL     - Mem0 PostgreSQL connection string
    S3_BUCKET             - S3 bucket name
    S3_ENDPOINT_URL       - S3 endpoint (e.g., https://s3.wasabisys.com)
    S3_ACCESS_KEY         - S3 access key
    S3_SECRET_KEY         - S3 secret key
    S3_REGION             - S3 region (default: us-east-1)
    BACKUP_RETENTION_DAYS - Days to keep backups (default: 7)
    RESPAWN_PROTECTION_HOURS - Min hours between backups (default: 23)
    FORCE_BACKUP          - Set to "true" to bypass respawn protection
    HEALTH_PORT           - Port for health endpoints (default: 8080)
    DB_RETRY_ATTEMPTS     - Max DB connection retries (default: 5)
    DB_RETRY_DELAY        - Initial retry delay in seconds (default: 2)
"""

import gzip
import json
import logging
import os
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
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
RESPAWN_PROTECTION_HOURS = int(os.getenv("RESPAWN_PROTECTION_HOURS", "23"))
FORCE_BACKUP = os.getenv("FORCE_BACKUP", "").lower() == "true"
HEALTH_PORT = int(os.getenv("HEALTH_PORT", os.getenv("PORT", "8080")))
DB_RETRY_ATTEMPTS = int(os.getenv("DB_RETRY_ATTEMPTS", "5"))
DB_RETRY_DELAY = int(os.getenv("DB_RETRY_DELAY", "2"))

# Global state for health checks
backup_state = {
    "status": "starting",
    "last_backup": None,
    "last_error": None,
    "backups_completed": 0,
}


class HealthHandler(BaseHTTPRequestHandler):
    """HTTP handler for health check endpoints."""

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

    def do_GET(self):
        if self.path == "/health" or self.path == "/":
            self._respond(200, {"status": "healthy", **backup_state})
        elif self.path == "/ready":
            if backup_state["status"] in ("ready", "completed", "running"):
                self._respond(200, {"ready": True})
            else:
                self._respond(503, {"ready": False, "status": backup_state["status"]})
        elif self.path == "/live":
            self._respond(200, {"alive": True})
        else:
            self._respond(404, {"error": "not found"})

    def _respond(self, code: int, data: dict):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())


def start_health_server():
    """Start health check HTTP server in background thread."""
    server = HTTPServer(("0.0.0.0", HEALTH_PORT), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Health server started on port {HEALTH_PORT}")
    return server


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


def check_db_connection(db_url: str, db_name: str) -> bool:
    """Check if database is reachable with retry logic."""
    if not db_url:
        return False

    db = parse_db_url(db_url)
    env = os.environ.copy()
    env["PGPASSWORD"] = db["password"] or ""

    for attempt in range(1, DB_RETRY_ATTEMPTS + 1):
        try:
            result = subprocess.run(
                [
                    "psql",
                    "-h",
                    db["host"],
                    "-p",
                    str(db["port"]),
                    "-U",
                    db["user"],
                    "-d",
                    db["database"],
                    "-c",
                    "SELECT 1",
                ],
                capture_output=True,
                env=env,
                timeout=10,
            )
            if result.returncode == 0:
                logger.info(f"[{db_name}] Database connection OK")
                return True
        except Exception as e:
            logger.warning(f"[{db_name}] Connection attempt {attempt} failed: {e}")

        if attempt < DB_RETRY_ATTEMPTS:
            delay = DB_RETRY_DELAY * (2 ** (attempt - 1))  # Exponential backoff
            logger.info(f"[{db_name}] Retrying in {delay}s...")
            time.sleep(delay)

    logger.error(f"[{db_name}] Failed to connect after {DB_RETRY_ATTEMPTS} attempts")
    return False


def get_last_backup_time(s3) -> datetime | None:
    """Get timestamp of most recent backup from S3 metadata."""
    marker_key = f"{BACKUP_PREFIX}/.last_backup"

    try:
        response = s3.get_object(Bucket=S3_BUCKET, Key=marker_key)
        data = json.loads(response["Body"].read().decode())
        return datetime.fromisoformat(data["timestamp"])
    except ClientError:
        return None
    except Exception as e:
        logger.warning(f"Failed to read last backup marker: {e}")
        return None


def set_last_backup_time(s3, timestamp: datetime):
    """Store timestamp of backup in S3 for respawn protection."""
    marker_key = f"{BACKUP_PREFIX}/.last_backup"

    try:
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=marker_key,
            Body=json.dumps({"timestamp": timestamp.isoformat()}).encode(),
            ContentType="application/json",
        )
    except Exception as e:
        logger.warning(f"Failed to write backup marker: {e}")


def should_run_backup(s3) -> tuple[bool, str]:
    """Check if backup should run based on respawn protection."""
    if FORCE_BACKUP:
        return True, "FORCE_BACKUP enabled"

    last_backup = get_last_backup_time(s3)
    if not last_backup:
        return True, "No previous backup found"

    hours_since = (datetime.now(UTC) - last_backup).total_seconds() / 3600
    if hours_since >= RESPAWN_PROTECTION_HOURS:
        return True, f"{hours_since:.1f} hours since last backup"

    return False, f"Only {hours_since:.1f} hours since last backup (min: {RESPAWN_PROTECTION_HOURS})"


def dump_database(db_url: str, db_name: str) -> bytes | None:
    """Dump a PostgreSQL database using pg_dump."""
    if not db_url:
        logger.warning(f"[{db_name}] Skipped - no DATABASE_URL configured")
        return None

    db = parse_db_url(db_url)
    logger.info(f"[{db_name}] Starting dump of {db['database']}@{db['host']}")

    env = os.environ.copy()
    env["PGPASSWORD"] = db["password"] or ""

    cmd = [
        "pg_dump",
        "-h",
        db["host"],
        "-p",
        str(db["port"]),
        "-U",
        db["user"],
        "-d",
        db["database"],
        "--format=plain",
        "--no-owner",
        "--no-acl",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            env=env,
            timeout=600,
        )

        if result.returncode != 0:
            logger.error(f"[{db_name}] pg_dump failed: {result.stderr.decode()[:500]}")
            return None

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
    """Remove backups older than retention period."""
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
                for obj in backups[:10]:
                    size_mb = obj["Size"] / (1024 * 1024)
                    ts = obj["LastModified"].strftime("%Y-%m-%d %H:%M:%S UTC")
                    filename = obj["Key"].split("/")[-1]
                    print(f"  - {filename} ({size_mb:.2f} MB, {ts})")

                if len(backups) > 10:
                    print(f"  ... and {len(backups) - 10} more")

        except ClientError as e:
            print(f"  Error: {e}")

        print()


def run_backup() -> bool:
    """Run backup of all databases. Returns True if all succeeded."""
    global backup_state
    backup_state["status"] = "running"

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

    logger.info("=" * 60)
    logger.info(f"Clara Database Backup Service - {timestamp}")
    logger.info("=" * 60)

    # Validate configuration
    if not S3_ACCESS_KEY or not S3_SECRET_KEY:
        logger.error("S3 credentials not configured (S3_ACCESS_KEY, S3_SECRET_KEY)")
        backup_state["status"] = "error"
        backup_state["last_error"] = "S3 credentials not configured"
        return False

    if not CLARA_DB_URL and not MEM0_DB_URL:
        logger.error("No database URLs configured (DATABASE_URL, MEM0_DATABASE_URL)")
        backup_state["status"] = "error"
        backup_state["last_error"] = "No database URLs configured"
        return False

    try:
        s3 = get_s3_client()
        s3.head_bucket(Bucket=S3_BUCKET)
        logger.info(f"S3 connection OK: {S3_ENDPOINT_URL} / {S3_BUCKET}")
    except ClientError as e:
        logger.error(f"S3 connection failed: {e}")
        backup_state["status"] = "error"
        backup_state["last_error"] = f"S3 connection failed: {e}"
        return False

    # Check respawn protection
    should_run, reason = should_run_backup(s3)
    if not should_run:
        logger.info(f"Skipping backup: {reason}")
        backup_state["status"] = "skipped"
        return True

    logger.info(f"Running backup: {reason}")

    # Verify database connectivity
    if CLARA_DB_URL and not check_db_connection(CLARA_DB_URL, "clara"):
        backup_state["last_error"] = "Clara DB connection failed"
    if MEM0_DB_URL and not check_db_connection(MEM0_DB_URL, "mem0"):
        backup_state["last_error"] = "Mem0 DB connection failed"

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

    # Update respawn protection marker
    if results["success"] > 0:
        set_last_backup_time(s3, datetime.now(UTC))

    # Summary
    logger.info("=" * 60)
    logger.info(
        f"Backup complete: {results['success']} succeeded, " f"{results['failed']} failed, {results['skipped']} skipped"
    )

    backup_state["status"] = "completed" if results["failed"] == 0 else "partial"
    backup_state["last_backup"] = datetime.now(UTC).isoformat()
    backup_state["backups_completed"] += results["success"]

    return results["failed"] == 0


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Clara database backup service")
    parser.add_argument("--list", "-l", action="store_true", help="List available backups")
    parser.add_argument("--restore", "-r", action="store_true", help="Show restore instructions")
    parser.add_argument("--server", "-s", action="store_true", help="Run health server only (no backup)")
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
    elif args.server:
        # Health server only mode
        backup_state["status"] = "ready"
        start_health_server()
        logger.info("Running in server-only mode. Waiting for cron trigger...")
        while True:
            time.sleep(60)
    else:
        # Start health server for Railway healthchecks
        start_health_server()
        backup_state["status"] = "ready"

        # Run backup
        success = run_backup()

        # Keep container alive briefly for health checks
        logger.info("Backup finished. Container will exit in 30 seconds...")
        time.sleep(30)

        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
