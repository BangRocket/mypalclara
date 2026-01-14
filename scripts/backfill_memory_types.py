#!/usr/bin/env python3
"""
Backfill memory_type metadata for existing memories.

This script classifies all existing memories and updates their metadata
with the memory_type field (stable, active, or ephemeral).

Usage:
    python -m scripts.backfill_memory_types              # Dry run (preview only)
    python -m scripts.backfill_memory_types --apply      # Apply changes
    python -m scripts.backfill_memory_types --user josh  # Specific user
    python -m scripts.backfill_memory_types --stats      # Show type distribution only

Examples:
    # Local development - preview
    poetry run python -m scripts.backfill_memory_types

    # Local development - apply
    poetry run python -m scripts.backfill_memory_types --apply

    # Railway production (shinkansen service)
    railway run -s shinkansen python -m scripts.backfill_memory_types --all

    # Railway production - apply
    railway run -s shinkansen python -m scripts.backfill_memory_types --all --apply

    # Railway production - skip confirmation
    railway run -s shinkansen python -m scripts.backfill_memory_types --all --apply --yes

Note: On Railway, env vars (DATABASE_URL, MEM0_DATABASE_URL, OPENAI_API_KEY, etc.)
are automatically available. No .env file needed.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from typing import TYPE_CHECKING

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env only if it exists (not needed on Railway)
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # dotenv not required in production

if TYPE_CHECKING:
    from vendor.mem0 import Memory


def get_all_memories(mem0: "Memory", user_id: str) -> list[dict]:
    """Fetch all memories for a user, handling pagination."""
    all_memories = []
    limit = 100
    offset = 0

    while True:
        # mem0's get_all doesn't support offset, so we fetch with high limit
        # and handle duplicates
        result = mem0.get_all(user_id=user_id, limit=limit)
        memories = result.get("results", [])

        if not memories:
            break

        # Check for duplicates (in case we're re-fetching)
        seen_ids = {m.get("id") for m in all_memories}
        new_memories = [m for m in memories if m.get("id") not in seen_ids]

        if not new_memories:
            break

        all_memories.extend(new_memories)

        # If we got fewer than limit, we're done
        if len(memories) < limit:
            break

        offset += limit

    return all_memories


def update_memory_metadata(
    mem0: "Memory",
    memory_id: str,
    new_metadata: dict,
) -> bool:
    """Update a memory's metadata directly through the vector store.

    Args:
        mem0: The mem0 Memory instance
        memory_id: ID of the memory to update
        new_metadata: Complete metadata dict to set

    Returns:
        True if successful, False otherwise
    """
    try:
        # Update through the vector store directly
        mem0.vector_store.update(
            vector_id=memory_id,
            vector=None,  # Keep existing embeddings
            payload=new_metadata,
        )
        return True
    except Exception as e:
        print(f"  Error updating memory {memory_id}: {e}")
        return False


def detect_environment() -> str:
    """Detect if running in production (Railway) or local dev."""
    if os.getenv("RAILWAY_ENVIRONMENT"):
        return "railway"
    if os.getenv("MEM0_DATABASE_URL") and "railway" in os.getenv("MEM0_DATABASE_URL", ""):
        return "railway"
    if os.getenv("MEM0_DATABASE_URL"):
        return "postgres"
    return "local"


def backfill_memory_types(
    user_id: str,
    apply: bool = False,
    stats_only: bool = False,
) -> dict:
    """Backfill memory_type for all memories of a user.

    Args:
        user_id: User ID to process
        apply: If True, apply changes. If False, dry run only.
        stats_only: If True, only show statistics without classifying.

    Returns:
        Dict with statistics about the backfill
    """
    from clara_core.memory_types import classify_memory
    from config.mem0 import MEM0, MEM0_DATABASE_URL

    if MEM0 is None:
        print("Error: mem0 is not initialized")
        print("Make sure OPENAI_API_KEY is set (required for embeddings)")
        return {"error": "mem0 not initialized"}

    # Show environment info
    env = detect_environment()
    env_label = {
        "railway": "PRODUCTION (Railway)",
        "postgres": "PostgreSQL",
        "local": "Local (Qdrant)",
    }.get(env, env)

    print(f"\n{'=' * 60}")
    print("Memory Type Backfill")
    print(f"{'=' * 60}")
    print(f"Environment: {env_label}")
    if MEM0_DATABASE_URL:
        # Mask the password in the URL for display
        import re

        masked_url = re.sub(r":([^:@]+)@", r":****@", MEM0_DATABASE_URL)
        print(f"Database:    {masked_url}")
    print(f"User:        {user_id}")
    print(f"Mode:        {'APPLY' if apply else 'DRY RUN'}")
    print(f"{'=' * 60}\n")

    # Fetch all memories
    print("Fetching memories...")
    memories = get_all_memories(MEM0, user_id)
    print(f"Found {len(memories)} memories\n")

    if not memories:
        return {"total": 0, "classified": 0, "skipped": 0, "errors": 0}

    # Analyze current state
    type_counts: Counter[str] = Counter()
    already_typed = 0
    needs_typing = 0

    for mem in memories:
        metadata = mem.get("metadata", {})
        existing_type = metadata.get("memory_type")
        if existing_type:
            type_counts[existing_type] += 1
            already_typed += 1
        else:
            needs_typing += 1

    print("Current state:")
    print(f"  Already typed: {already_typed}")
    print(f"  Needs typing:  {needs_typing}")
    if type_counts:
        print(f"  Distribution:  {dict(type_counts)}")
    print()

    if stats_only:
        # Also show what classification would produce
        print("Projected classification (all memories):")
        projected_counts: Counter[str] = Counter()
        for mem in memories:
            content = mem.get("memory", "")
            mem_type = classify_memory(content)
            projected_counts[mem_type.value] += 1
        for t, count in sorted(projected_counts.items()):
            print(f"  {t}: {count}")
        return {
            "total": len(memories),
            "already_typed": already_typed,
            "needs_typing": needs_typing,
            "distribution": dict(type_counts),
            "projected": dict(projected_counts),
        }

    # Process memories
    classified = 0
    skipped = 0
    errors = 0
    new_type_counts: Counter[str] = Counter()

    print("Processing memories...\n")

    for i, mem in enumerate(memories, 1):
        memory_id = mem.get("id", "unknown")
        content = mem.get("memory", "")
        metadata = mem.get("metadata", {})

        # Check if already typed
        existing_type = metadata.get("memory_type")
        if existing_type:
            skipped += 1
            continue

        # Classify
        mem_type = classify_memory(content)
        new_type_counts[mem_type.value] += 1

        # Preview
        content_preview = content[:60] + "..." if len(content) > 60 else content
        print(f"[{i}/{len(memories)}] {mem_type.value:10} | {content_preview}")

        if apply:
            # Build updated metadata
            updated_metadata = deepcopy(mem.get("payload", metadata))
            if not updated_metadata:
                # Fall back to reconstructing from mem dict
                updated_metadata = {
                    "data": content,
                    "hash": mem.get("hash"),
                    "created_at": mem.get("created_at"),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "user_id": mem.get("user_id", user_id),
                }
                # Copy any existing metadata
                if metadata:
                    updated_metadata.update(metadata)

            # Add memory_type
            updated_metadata["memory_type"] = mem_type.value

            # Apply update
            if update_memory_metadata(MEM0, memory_id, updated_metadata):
                classified += 1
            else:
                errors += 1
        else:
            classified += 1  # Would be classified in apply mode

    # Summary
    print(f"\n{'=' * 60}")
    print("Summary:")
    print(f"  Total memories:  {len(memories)}")
    print(f"  Already typed:   {skipped}")
    print(f"  {'Classified' if apply else 'Would classify'}: {classified}")
    if errors:
        print(f"  Errors:          {errors}")
    print("\n  New type distribution:")
    for t, count in sorted(new_type_counts.items()):
        print(f"    {t}: {count}")
    print(f"{'=' * 60}\n")

    if not apply:
        print("This was a DRY RUN. Use --apply to make changes.\n")

    return {
        "total": len(memories),
        "skipped": skipped,
        "classified": classified,
        "errors": errors,
        "new_distribution": dict(new_type_counts),
    }


def get_all_user_ids() -> list[str]:
    """Get all unique user IDs from the database.

    Falls back to environment variable if database query fails.
    """
    try:
        from db import SessionLocal
        from db.models import Session

        db = SessionLocal()
        try:
            # Get unique user IDs from sessions
            user_ids = db.query(Session.user_id).distinct().all()
            return [uid[0] for uid in user_ids if uid[0]]
        finally:
            db.close()
    except Exception as e:
        print(f"Warning: Could not query database for users: {e}")
        # Fall back to env var
        default_user = os.getenv("USER_ID", "demo-user")
        return [default_user]


def main():
    parser = argparse.ArgumentParser(
        description="Backfill memory_type metadata for existing memories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m scripts.backfill_memory_types              # Dry run for default user
  python -m scripts.backfill_memory_types --apply      # Apply changes
  python -m scripts.backfill_memory_types --all        # Process all users (dry run)
  python -m scripts.backfill_memory_types --all --apply  # Process all users (apply)
  python -m scripts.backfill_memory_types --stats      # Show statistics only
        """,
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes (default is dry run)",
    )
    parser.add_argument(
        "--user",
        "-u",
        type=str,
        default=None,
        help="User ID to process (default: from USER_ID env var)",
    )
    parser.add_argument(
        "--all",
        "-a",
        action="store_true",
        help="Process all users found in database",
    )
    parser.add_argument(
        "--stats",
        "-s",
        action="store_true",
        help="Show type distribution statistics only",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompt for production",
    )
    args = parser.parse_args()

    # Production safety check
    env = detect_environment()
    if args.apply and env == "railway" and not args.yes:
        print("\n" + "=" * 60)
        print("WARNING: You are about to modify PRODUCTION data!")
        print("=" * 60)
        print("\nThis will update memory metadata in the Railway database.")
        response = input("\nType 'yes' to continue: ").strip().lower()
        if response != "yes":
            print("Aborted.")
            return
        print()

    if args.all:
        user_ids = get_all_user_ids()
        print(f"Found {len(user_ids)} users: {user_ids}\n")
        results = {}
        for user_id in user_ids:
            results[user_id] = backfill_memory_types(
                user_id,
                apply=args.apply,
                stats_only=args.stats,
            )
        # Overall summary
        print("\n" + "=" * 60)
        print("OVERALL SUMMARY")
        print("=" * 60)
        total_mems = sum(r.get("total", 0) for r in results.values())
        total_classified = sum(r.get("classified", 0) for r in results.values())
        total_errors = sum(r.get("errors", 0) for r in results.values())
        print(f"Total memories across all users: {total_mems}")
        print(f"Total classified: {total_classified}")
        if total_errors:
            print(f"Total errors: {total_errors}")
    else:
        user_id = args.user or os.getenv("USER_ID", "demo-user")
        backfill_memory_types(
            user_id,
            apply=args.apply,
            stats_only=args.stats,
        )


if __name__ == "__main__":
    main()
