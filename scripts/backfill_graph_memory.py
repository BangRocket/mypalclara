#!/usr/bin/env python3
"""
Backfill graph memory from existing Discord chat history.

This script processes existing conversations in the database through mem0.add()
to extract entity relationships for the graph memory.

Usage:
    poetry run python scripts/backfill_graph_memory.py              # Dry run
    poetry run python scripts/backfill_graph_memory.py --apply      # Actually process
    poetry run python scripts/backfill_graph_memory.py --user <id>  # Specific user only
    poetry run python scripts/backfill_graph_memory.py --limit 100  # Limit sessions
    poetry run python scripts/backfill_graph_memory.py --resume     # Resume from progress file
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import func
from sqlalchemy.orm import Session as OrmSession

from db import SessionLocal
from db.models import Message, Session

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Progress file for resuming
PROGRESS_FILE = Path(__file__).parent.parent / ".graph_backfill_progress.json"

# Agent ID to use for graph memory (should match your bot)
AGENT_ID = os.getenv("BOT_NAME", "clara").lower()


def load_progress() -> dict:
    """Load progress from file."""
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_progress(progress: dict) -> None:
    """Save progress to file."""
    PROGRESS_FILE.write_text(json.dumps(progress, indent=2))


def get_sessions_to_process(
    db: OrmSession,
    user_id: str | None = None,
    limit: int | None = None,
    processed_ids: set[str] | None = None,
) -> list[Session]:
    """Get sessions to process, optionally filtered by user."""
    query = db.query(Session).order_by(Session.started_at.asc())

    if user_id:
        query = query.filter(Session.user_id == user_id)

    if processed_ids:
        query = query.filter(~Session.id.in_(processed_ids))

    if limit:
        query = query.limit(limit)

    return query.all()


def get_session_messages(db: OrmSession, session_id: str) -> list[Message]:
    """Get all messages for a session ordered by time."""
    return (
        db.query(Message)
        .filter(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
        .all()
    )


def chunk_messages(messages: list[Message], chunk_size: int = 6) -> list[list[dict]]:
    """
    Chunk messages into conversation slices for processing.

    Each chunk contains up to chunk_size messages, preserving conversation flow.
    Overlaps by 2 messages to maintain context.
    """
    if not messages:
        return []

    chunks = []
    msg_dicts = [{"role": m.role, "content": m.content} for m in messages]

    for i in range(0, len(msg_dicts), chunk_size - 2):
        chunk = msg_dicts[i : i + chunk_size]
        if len(chunk) >= 2:  # Need at least a user-assistant pair
            chunks.append(chunk)

    return chunks


def process_session(
    session: Session,
    messages: list[Message],
    mem0,
    dry_run: bool = True,
) -> dict:
    """
    Process a session's messages to extract graph relations.

    Returns stats about what was processed.
    """
    user_id = session.user_id
    project_id = session.project_id

    chunks = chunk_messages(messages)
    stats = {
        "session_id": session.id,
        "user_id": user_id,
        "message_count": len(messages),
        "chunk_count": len(chunks),
        "graph_entities_added": 0,
        "memories_added": 0,
        "errors": [],
    }

    if dry_run:
        logger.info(
            f"  [DRY RUN] Would process {len(chunks)} chunks "
            f"({len(messages)} messages)"
        )
        return stats

    for i, chunk in enumerate(chunks):
        try:
            result = mem0.add(
                chunk,
                user_id=user_id,
                agent_id=AGENT_ID,
                metadata={"project_id": project_id, "backfill": True},
            )

            if isinstance(result, dict):
                # Count memories added
                stats["memories_added"] += len(result.get("results", []))

                # Count graph entities
                relations = result.get("relations", {})
                if isinstance(relations, dict):
                    added = relations.get("added_entities", [])
                    stats["graph_entities_added"] += len(added)

        except Exception as e:
            error_msg = f"Chunk {i}: {str(e)}"
            stats["errors"].append(error_msg)
            logger.warning(f"  Error processing chunk {i}: {e}")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Backfill graph memory from existing chat history"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually process (default is dry run)",
    )
    parser.add_argument(
        "--user",
        type=str,
        help="Only process sessions for this user ID",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of sessions to process",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last progress",
    )
    parser.add_argument(
        "--clear-progress",
        action="store_true",
        help="Clear progress file and start fresh",
    )
    args = parser.parse_args()

    dry_run = not args.apply

    # Check if graph memory is enabled
    from config.mem0 import ENABLE_GRAPH_MEMORY, MEM0

    if not ENABLE_GRAPH_MEMORY:
        logger.error("Graph memory is not enabled. Set ENABLE_GRAPH_MEMORY=true")
        sys.exit(1)

    if MEM0 is None:
        logger.error("mem0 failed to initialize. Check your configuration.")
        sys.exit(1)

    # Handle progress
    progress = {}
    processed_ids = set()

    if args.clear_progress and PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()
        logger.info("Cleared progress file")

    if args.resume:
        progress = load_progress()
        processed_ids = set(progress.get("processed_session_ids", []))
        logger.info(f"Resuming from progress: {len(processed_ids)} sessions already processed")

    # Get sessions to process
    db = SessionLocal()
    try:
        sessions = get_sessions_to_process(
            db,
            user_id=args.user,
            limit=args.limit,
            processed_ids=processed_ids if args.resume else None,
        )

        total_sessions = len(sessions)
        logger.info(f"Found {total_sessions} sessions to process")

        if dry_run:
            logger.info("=" * 60)
            logger.info("DRY RUN - No changes will be made")
            logger.info("Run with --apply to actually process")
            logger.info("=" * 60)

        # Summary stats
        total_stats = {
            "sessions_processed": 0,
            "messages_processed": 0,
            "chunks_processed": 0,
            "graph_entities_added": 0,
            "memories_added": 0,
            "errors": 0,
        }

        for i, session in enumerate(sessions):
            messages = get_session_messages(db, session.id)

            if not messages:
                logger.debug(f"Session {session.id}: No messages, skipping")
                continue

            logger.info(
                f"[{i + 1}/{total_sessions}] Session {session.id[:8]}... "
                f"(user={session.user_id}, msgs={len(messages)})"
            )

            stats = process_session(session, messages, MEM0, dry_run=dry_run)

            # Update totals
            total_stats["sessions_processed"] += 1
            total_stats["messages_processed"] += stats["message_count"]
            total_stats["chunks_processed"] += stats["chunk_count"]
            total_stats["graph_entities_added"] += stats["graph_entities_added"]
            total_stats["memories_added"] += stats["memories_added"]
            total_stats["errors"] += len(stats["errors"])

            # Save progress after each session (if not dry run)
            if not dry_run:
                processed_ids.add(session.id)
                progress["processed_session_ids"] = list(processed_ids)
                progress["last_updated"] = datetime.now().isoformat()
                progress["stats"] = total_stats
                save_progress(progress)

        # Print summary
        logger.info("=" * 60)
        logger.info("SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Sessions processed: {total_stats['sessions_processed']}")
        logger.info(f"Messages processed: {total_stats['messages_processed']}")
        logger.info(f"Chunks processed: {total_stats['chunks_processed']}")
        logger.info(f"Graph entities added: {total_stats['graph_entities_added']}")
        logger.info(f"Memories added: {total_stats['memories_added']}")
        logger.info(f"Errors: {total_stats['errors']}")

        if dry_run:
            logger.info("")
            logger.info("This was a DRY RUN. Run with --apply to actually process.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
