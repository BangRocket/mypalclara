#!/usr/bin/env python3
"""
Migrate mem0 memories to Cortex memories table.

Copies data from clara_memories (mem0) to memories (Cortex),
reusing existing embeddings.

Usage:
    poetry run python scripts/migrate_mem0_to_cortex.py
    poetry run python scripts/migrate_mem0_to_cortex.py --verify
    poetry run python scripts/migrate_mem0_to_cortex.py --dry-run
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv()


def build_cortex_db_url() -> str:
    """Build Postgres URL from individual CORTEX_POSTGRES_* env vars."""
    host = os.getenv("CORTEX_POSTGRES_HOST", "localhost")
    port = os.getenv("CORTEX_POSTGRES_PORT", "5432")
    user = os.getenv("CORTEX_POSTGRES_USER", "postgres")
    password = os.getenv("CORTEX_POSTGRES_PASSWORD", "")
    database = os.getenv("CORTEX_POSTGRES_DATABASE", "cortex")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


async def ensure_cortex_schema(conn):
    """Ensure cortex memories table exists with correct schema."""
    # Enable pgvector
    await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Check if memories table exists and has the correct schema
    has_memory_type = await conn.fetchval("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'memories' AND column_name = 'memory_type'
        )
    """)

    table_exists = await conn.fetchval("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'memories'
        )
    """)

    if table_exists and not has_memory_type:
        # Old schema exists (likely mem0's native memories table)
        # Rename it to preserve data
        print("  Found old memories table schema, backing up to memories_mem0_backup...")
        await conn.execute("""
            ALTER TABLE IF EXISTS memories
            RENAME TO memories_mem0_backup
        """)
        print("  Old table renamed to memories_mem0_backup")

    # Create memories table (cortex schema)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id         VARCHAR(255) NOT NULL,
            project_id      VARCHAR(255),
            content         TEXT NOT NULL,
            memory_type     VARCHAR(50) NOT NULL,
            emotional_score FLOAT DEFAULT 0.5,
            importance      FLOAT DEFAULT 0.5,
            confidence      FLOAT DEFAULT 1.0,
            created_at      TIMESTAMPTZ DEFAULT NOW(),
            updated_at      TIMESTAMPTZ DEFAULT NOW(),
            last_accessed   TIMESTAMPTZ,
            access_count    INTEGER DEFAULT 0,
            supersedes      UUID REFERENCES memories(id),
            source          VARCHAR(100) DEFAULT 'conversation',
            tags            TEXT[] DEFAULT ARRAY[]::TEXT[],
            metadata        JSONB DEFAULT '{}',
            embedding       vector(1536),
            status          VARCHAR(50) DEFAULT 'active'
        )
    """)

    # Create indexes
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_memories_user_id ON memories(user_id);
        CREATE INDEX IF NOT EXISTS idx_memories_user_type ON memories(user_id, memory_type);
        CREATE INDEX IF NOT EXISTS idx_memories_user_status ON memories(user_id, status);
        CREATE INDEX IF NOT EXISTS idx_memories_project ON memories(project_id) WHERE project_id IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at DESC);
    """)


async def migrate(dry_run: bool = False):
    """Migrate mem0 memories to Cortex."""
    import asyncpg
    from pgvector.asyncpg import register_vector
    import numpy as np

    # Get database URLs
    mem0_url = os.getenv("MEM0_DATABASE_URL")
    cortex_url = build_cortex_db_url()

    if not mem0_url:
        print("ERROR: MEM0_DATABASE_URL not set")
        sys.exit(1)

    print("mem0 -> Cortex Memory Migration")
    print("=" * 50)
    print(f"Source (mem0): {mem0_url.split('@')[1] if '@' in mem0_url else mem0_url}")
    print(f"Target (cortex): {cortex_url.split('@')[1] if '@' in cortex_url else cortex_url}")
    if dry_run:
        print("DRY RUN - no changes will be made")
    print("=" * 50)

    print("\nConnecting to databases...")
    mem0_conn = await asyncpg.connect(dsn=mem0_url)
    cortex_conn = await asyncpg.connect(dsn=cortex_url)

    # Register pgvector types for both connections
    await register_vector(mem0_conn)
    await register_vector(cortex_conn)

    try:
        # Ensure cortex schema exists
        print("Ensuring cortex schema...")
        await ensure_cortex_schema(cortex_conn)

        # Count source memories
        count = await mem0_conn.fetchval("SELECT COUNT(*) FROM clara_memories")
        print(f"Found {count} memories in clara_memories (mem0)")

        if count == 0:
            print("No memories to migrate")
            return

        # Check existing in cortex memories
        existing = await cortex_conn.fetchval("SELECT COUNT(*) FROM memories")
        print(f"Existing memories in cortex: {existing}")

        # Check for already migrated (by source)
        migrated_count = await cortex_conn.fetchval(
            "SELECT COUNT(*) FROM memories WHERE source = 'mem0_migration'"
        )
        print(f"Already migrated: {migrated_count}")

        # Fetch all memories from clara_memories
        print("\nFetching mem0 memories...")
        rows = await mem0_conn.fetch("""
            SELECT id, vector, payload
            FROM clara_memories
        """)

        migrated = 0
        skipped = 0
        errors = 0

        print(f"Processing {len(rows)} memories...")

        for row in rows:
            try:
                payload = row["payload"]

                # Parse payload if it's a string
                if isinstance(payload, str):
                    payload = json.loads(payload)

                # Extract fields from payload
                content = payload.get("data", "")
                user_id = payload.get("user_id", "unknown")
                created_at_str = payload.get("created_at")
                project_id = payload.get("project_id")

                # Parse created_at string to datetime
                from datetime import datetime
                created_at = None
                if created_at_str:
                    try:
                        created_at = datetime.fromisoformat(created_at_str)
                    except ValueError:
                        pass

                if not content:
                    skipped += 1
                    continue

                # Build metadata from remaining payload fields
                metadata = {
                    "original_mem0_id": str(row["id"]),
                    "hash": payload.get("hash"),
                    "participant_ids": payload.get("participant_ids", []),
                    "participant_names": payload.get("participant_names", []),
                }

                # Convert vector to numpy array for pgvector
                # asyncpg returns vectors in various formats
                vector = row["vector"]
                if vector is None:
                    skipped += 1
                    continue

                # Convert to numpy array for pgvector
                if isinstance(vector, str):
                    # Parse string format "[x,y,z,...]"
                    vector = np.array([float(x) for x in vector.strip("[]").split(",")])
                elif isinstance(vector, (list, tuple)):
                    vector = np.array(vector)
                elif hasattr(vector, "__iter__"):
                    vector = np.array(list(vector))

                # Check if already migrated (by original_mem0_id in metadata)
                exists = await cortex_conn.fetchval("""
                    SELECT 1 FROM memories
                    WHERE metadata->>'original_mem0_id' = $1
                """, str(row["id"]))

                if exists:
                    skipped += 1
                    continue

                if dry_run:
                    migrated += 1
                    if migrated % 10 == 0:
                        print(f"  [DRY RUN] Would migrate {migrated}...")
                    continue

                # Insert into cortex memories table
                await cortex_conn.execute("""
                    INSERT INTO memories (
                        user_id, project_id, content, memory_type,
                        emotional_score, importance, confidence,
                        created_at, source, metadata, embedding, status
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                """,
                    user_id,
                    project_id,
                    content,
                    "episodic",  # Default memory type for migrated memories
                    0.5,  # Default emotional score
                    0.5,  # Default importance
                    1.0,  # Default confidence
                    created_at,
                    "mem0_migration",  # Source marker
                    json.dumps(metadata),
                    vector,
                    "active",
                )

                migrated += 1

                if migrated % 10 == 0:
                    print(f"  Migrated {migrated}...")

            except Exception as e:
                print(f"  Error migrating {row['id']}: {e}")
                errors += 1

        print(f"\n{'DRY RUN ' if dry_run else ''}Migration complete!")
        print(f"  Migrated: {migrated}")
        print(f"  Skipped:  {skipped} (empty, no vector, or already exists)")
        print(f"  Errors:   {errors}")

        if not dry_run:
            # Final count
            final = await cortex_conn.fetchval("SELECT COUNT(*) FROM memories")
            print(f"\nTotal memories in cortex: {final}")

    finally:
        await mem0_conn.close()
        await cortex_conn.close()


async def verify():
    """Verify migration by showing sample data."""
    import asyncpg

    cortex_url = build_cortex_db_url()
    conn = await asyncpg.connect(dsn=cortex_url)

    try:
        print("\nCortex Memory Statistics")
        print("-" * 60)

        # Total count
        total = await conn.fetchval("SELECT COUNT(*) FROM memories")
        print(f"Total memories: {total}")

        # By source
        sources = await conn.fetch("""
            SELECT source, COUNT(*) as count
            FROM memories
            GROUP BY source
            ORDER BY count DESC
        """)
        print("\nBy source:")
        for row in sources:
            print(f"  {row['source']}: {row['count']}")

        # By user
        users = await conn.fetch("""
            SELECT user_id, COUNT(*) as count
            FROM memories
            GROUP BY user_id
            ORDER BY count DESC
            LIMIT 10
        """)
        print("\nTop users:")
        for row in users:
            print(f"  {row['user_id']}: {row['count']}")

        # Sample migrated memories
        print("\nSample migrated memories:")
        print("-" * 60)

        rows = await conn.fetch("""
            SELECT user_id, content, memory_type, created_at, source
            FROM memories
            WHERE source = 'mem0_migration'
            ORDER BY created_at DESC
            LIMIT 5
        """)

        for row in rows:
            print(f"User: {row['user_id']}")
            print(f"Type: {row['memory_type']}")
            print(f"Content: {row['content'][:100]}...")
            print(f"Created: {row['created_at']}")
            print("-" * 60)

    finally:
        await conn.close()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Migrate mem0 to Cortex")
    parser.add_argument("--verify", action="store_true", help="Verify migration status")
    parser.add_argument("--dry-run", action="store_true", help="Dry run (no changes)")
    args = parser.parse_args()

    if args.verify:
        asyncio.run(verify())
    else:
        asyncio.run(migrate(dry_run=args.dry_run))
        if not args.dry_run:
            asyncio.run(verify())


if __name__ == "__main__":
    main()
