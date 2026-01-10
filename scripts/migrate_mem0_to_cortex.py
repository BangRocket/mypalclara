#!/usr/bin/env python3
"""
Migrate mem0 memories to Cortex long_term_memories.

Copies data from clara_memories (mem0) to long_term_memories (Cortex),
reusing existing embeddings.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv()


async def migrate():
    """Migrate mem0 memories to Cortex."""
    import asyncpg
    import json

    # Get database URL
    db_url = os.getenv("CORTEX_POSTGRES_URL") or os.getenv("MEM0_DATABASE_URL")
    if not db_url:
        print("ERROR: No database URL found")
        sys.exit(1)

    print("Connecting to database...")
    conn = await asyncpg.connect(dsn=db_url)

    try:
        # Count source memories
        count = await conn.fetchval("SELECT COUNT(*) FROM clara_memories")
        print(f"Found {count} memories in clara_memories")

        if count == 0:
            print("No memories to migrate")
            return

        # Check existing in long_term_memories
        existing = await conn.fetchval("SELECT COUNT(*) FROM long_term_memories")
        print(f"Existing memories in long_term_memories: {existing}")

        # Fetch all memories from clara_memories
        print("\nFetching memories...")
        rows = await conn.fetch("""
            SELECT id, vector, payload
            FROM clara_memories
        """)

        migrated = 0
        skipped = 0
        errors = 0

        print(f"Migrating {len(rows)} memories...")

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
                    "source": "mem0_migration",
                    "original_id": str(row["id"]),
                    "hash": payload.get("hash"),
                    "project_id": project_id,
                    "participant_ids": payload.get("participant_ids", []),
                    "participant_names": payload.get("participant_names", []),
                }

                # Convert vector to string if it's not already
                # asyncpg returns vectors as strings in format '[x,y,z,...]'
                vector = row["vector"]
                if isinstance(vector, (list, tuple)):
                    vector_str = "[" + ",".join(str(x) for x in vector) + "]"
                else:
                    # Already a string from pgvector
                    vector_str = str(vector)

                # Check if already migrated (by original_id in metadata)
                exists = await conn.fetchval("""
                    SELECT 1 FROM long_term_memories
                    WHERE metadata->>'original_id' = $1
                """, str(row["id"]))

                if exists:
                    skipped += 1
                    continue

                # Insert into long_term_memories
                await conn.execute("""
                    INSERT INTO long_term_memories
                    (user_id, content, embedding, category, importance, created_at, metadata)
                    VALUES ($1, $2, $3::vector, $4, $5, $6, $7::jsonb)
                """,
                    user_id,
                    content,
                    vector_str,
                    "mem0_memory",  # category
                    0.5,  # default importance
                    created_at,
                    json.dumps(metadata),
                )

                migrated += 1

                if migrated % 10 == 0:
                    print(f"  Migrated {migrated}...")

            except Exception as e:
                print(f"  Error migrating {row['id']}: {e}")
                errors += 1

        print(f"\nMigration complete!")
        print(f"  Migrated: {migrated}")
        print(f"  Skipped:  {skipped} (empty or already exists)")
        print(f"  Errors:   {errors}")

        # Final count
        final = await conn.fetchval("SELECT COUNT(*) FROM long_term_memories")
        print(f"\nTotal memories in long_term_memories: {final}")

    finally:
        await conn.close()


async def verify():
    """Verify migration by showing sample data."""
    import asyncpg

    db_url = os.getenv("CORTEX_POSTGRES_URL") or os.getenv("MEM0_DATABASE_URL")
    conn = await asyncpg.connect(dsn=db_url)

    try:
        print("\nSample migrated memories:")
        print("-" * 60)

        rows = await conn.fetch("""
            SELECT user_id, content, category, created_at
            FROM long_term_memories
            WHERE category = 'mem0_memory'
            ORDER BY created_at DESC
            LIMIT 5
        """)

        for row in rows:
            print(f"User: {row['user_id']}")
            print(f"Content: {row['content'][:100]}...")
            print(f"Created: {row['created_at']}")
            print("-" * 60)

    finally:
        await conn.close()


def main():
    print("mem0 -> Cortex Memory Migration")
    print("=" * 40)

    if "--verify" in sys.argv:
        asyncio.run(verify())
    else:
        asyncio.run(migrate())
        asyncio.run(verify())


if __name__ == "__main__":
    main()
