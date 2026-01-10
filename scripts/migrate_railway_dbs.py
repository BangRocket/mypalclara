#!/usr/bin/env python3
"""
Migrate Railway Postgres databases to new instances.

Copies data from:
- postgres -> postgres v2 (main database)
- postgres-vectors -> postgres-vectors v2 (mem0/cortex vectors)

Uses pg_dump and psql for reliable migration.
"""

import subprocess
import sys
from urllib.parse import urlparse

# Source databases (production)
SOURCE_MAIN = "postgresql://postgres:KRqPfxSFzNZaHTNrcOTdAfreidIBoOAy@switchback.proxy.rlwy.net:11688/railway"
SOURCE_VECTORS = "postgres://postgres:jI~tY1nWzyPW0l~guH6AhvNnmDS14U88@shinkansen.proxy.rlwy.net:24932/railway"

# Destination databases (new v2)
DEST_MAIN = "postgresql://postgres:rGHBKaQroxJLpZQBEhPLkOcIqeqDflQv@mainline.proxy.rlwy.net:23086/railway"
DEST_VECTORS = "postgres://postgres:NshYYkKG3i9tlNErMCr3CYo0I6Y5Qk4j@turntable.proxy.rlwy.net:51674/railway"


def parse_db_url(url: str) -> dict:
    """Parse database URL into components."""
    parsed = urlparse(url)
    return {
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "user": parsed.username,
        "password": parsed.password,
        "database": parsed.path.lstrip("/"),
    }


def migrate_database(source_url: str, dest_url: str, name: str) -> bool:
    """
    Migrate a database from source to destination.

    Uses pg_dump to export and psql to import.
    """
    print(f"\n{'='*60}")
    print(f"Migrating: {name}")
    print(f"{'='*60}")

    source = parse_db_url(source_url)
    dest = parse_db_url(dest_url)

    print(f"Source: {source['host']}:{source['port']}/{source['database']}")
    print(f"Dest:   {dest['host']}:{dest['port']}/{dest['database']}")

    # Build pg_dump command
    dump_env = {"PGPASSWORD": source["password"]}
    dump_cmd = [
        "pg_dump",
        "-h", source["host"],
        "-p", str(source["port"]),
        "-U", source["user"],
        "-d", source["database"],
        "--no-owner",           # Don't set ownership
        "--no-privileges",      # Don't set privileges
        "--clean",              # Drop objects before recreating
        "--if-exists",          # Don't error if objects don't exist
    ]

    # Build psql command
    restore_env = {"PGPASSWORD": dest["password"]}
    restore_cmd = [
        "psql",
        "-h", dest["host"],
        "-p", str(dest["port"]),
        "-U", dest["user"],
        "-d", dest["database"],
        "-v", "ON_ERROR_STOP=0",  # Continue on errors (for clean/if-exists)
    ]

    print(f"\nDumping from source...")

    try:
        # Run pg_dump and pipe to psql
        import os

        # Combine environment
        env = os.environ.copy()

        # First, dump to a file
        dump_file = f"/tmp/{name.replace(' ', '_')}_dump.sql"

        env.update(dump_env)
        with open(dump_file, "w") as f:
            result = subprocess.run(
                dump_cmd,
                env=env,
                stdout=f,
                stderr=subprocess.PIPE,
                text=True,
            )

        if result.returncode != 0:
            print(f"ERROR: pg_dump failed: {result.stderr}")
            return False

        # Get dump file size
        import os.path
        size_mb = os.path.getsize(dump_file) / (1024 * 1024)
        print(f"Dump complete: {size_mb:.2f} MB")

        print(f"Restoring to destination...")

        env.update(restore_env)
        with open(dump_file, "r") as f:
            result = subprocess.run(
                restore_cmd,
                env=env,
                stdin=f,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

        # psql may return warnings, check for fatal errors
        if "FATAL" in result.stderr or "could not connect" in result.stderr:
            print(f"ERROR: psql failed: {result.stderr}")
            return False

        if result.stderr:
            # Print warnings but continue
            print(f"Warnings: {result.stderr[:500]}...")

        print(f"Migration complete for {name}!")

        # Cleanup
        os.remove(dump_file)

        return True

    except FileNotFoundError as e:
        print(f"ERROR: Command not found. Make sure pg_dump and psql are installed.")
        print(f"On macOS: brew install postgresql")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False


def verify_migration(dest_url: str, name: str):
    """Verify migration by counting tables and rows."""
    import os

    dest = parse_db_url(dest_url)
    env = os.environ.copy()
    env["PGPASSWORD"] = dest["password"]

    # Count tables
    result = subprocess.run(
        [
            "psql",
            "-h", dest["host"],
            "-p", str(dest["port"]),
            "-U", dest["user"],
            "-d", dest["database"],
            "-t", "-c",
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';"
        ],
        env=env,
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        table_count = result.stdout.strip()
        print(f"\n{name}: {table_count} tables in destination")

    # List tables with row counts
    result = subprocess.run(
        [
            "psql",
            "-h", dest["host"],
            "-p", str(dest["port"]),
            "-U", dest["user"],
            "-d", dest["database"],
            "-c",
            """
            SELECT schemaname, relname as table, n_live_tup as rows
            FROM pg_stat_user_tables
            ORDER BY n_live_tup DESC
            LIMIT 10;
            """
        ],
        env=env,
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        print(result.stdout)


def main():
    print("Railway Database Migration Tool")
    print("================================")
    print("\nThis will copy data from old databases to new v2 databases.")
    print("\nDatabases to migrate:")
    print("  1. postgres -> postgres v2 (main)")
    print("  2. postgres-vectors -> postgres-vectors v2 (mem0/cortex)")

    # Check for --yes flag
    if "--yes" not in sys.argv:
        response = input("\nProceed with migration? [y/N] ")
        if response.lower() != "y":
            print("Aborted.")
            sys.exit(0)

    success = True

    # Migrate main database
    if not migrate_database(SOURCE_MAIN, DEST_MAIN, "Main Database"):
        success = False
    else:
        verify_migration(DEST_MAIN, "Main Database")

    # Migrate vectors database
    if not migrate_database(SOURCE_VECTORS, DEST_VECTORS, "Vectors Database"):
        success = False
    else:
        verify_migration(DEST_VECTORS, "Vectors Database")

    print("\n" + "="*60)
    if success:
        print("Migration completed successfully!")
        print("\nNext steps:")
        print("1. Verify data in new databases")
        print("2. Update .env to point to new databases")
        print("3. Restart your application")
    else:
        print("Migration completed with errors. Check output above.")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
