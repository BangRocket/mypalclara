"""Tests for the idempotent Obsidian columns migration helper."""

import pytest
from sqlalchemy import create_engine, inspect, text

from identity.db import Base
from identity.scripts.migrate_obsidian_columns import migrate


def test_migration_adds_columns_to_legacy_table(tmp_path):
    db_url = f"sqlite:///{tmp_path}/legacy.db"
    engine = create_engine(db_url)

    # Simulate legacy table WITHOUT obsidian columns
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE canonical_users (
                id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                primary_email TEXT,
                avatar_url TEXT,
                status TEXT DEFAULT 'active',
                is_admin BOOLEAN DEFAULT 0,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """))

    migrate(engine)

    cols = {c["name"] for c in inspect(engine).get_columns("canonical_users")}
    assert "encrypted_obsidian_token" in cols
    assert "obsidian_api_host" in cols
    assert "obsidian_verify_tls" in cols
    assert "obsidian_updated_at" in cols


def test_migration_is_idempotent(tmp_path):
    db_url = f"sqlite:///{tmp_path}/fresh.db"
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    migrate(engine)  # should be a no-op
    migrate(engine)  # should still be a no-op — verifies no duplicate-column errors


def test_migration_skips_when_table_missing(tmp_path):
    db_url = f"sqlite:///{tmp_path}/empty.db"
    engine = create_engine(db_url)
    # No canonical_users table at all — migrate should not crash
    migrate(engine)
