"""Idempotent ALTER TABLE migration for the Obsidian columns added in Task A2.

The identity service does not use Alembic; it relies on Base.metadata.create_all()
which won't add columns to existing tables. This script fills that gap.
"""
from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def _column_decl(name: str, dialect: str) -> str:
    """Return the DDL fragment for a single new column, given the DB dialect."""
    if dialect == "postgresql":
        mapping = {
            "encrypted_obsidian_token": "BYTEA",
            "obsidian_api_host":        "TEXT",
            "obsidian_verify_tls":      "BOOLEAN NOT NULL DEFAULT true",
            "obsidian_updated_at":      "TIMESTAMP",
        }
    else:  # sqlite and anything else
        mapping = {
            "encrypted_obsidian_token": "BLOB",
            "obsidian_api_host":        "TEXT",
            "obsidian_verify_tls":      "BOOLEAN NOT NULL DEFAULT 1",
            "obsidian_updated_at":      "TIMESTAMP",
        }
    return mapping[name]


NEW_COLUMN_NAMES = [
    "encrypted_obsidian_token",
    "obsidian_api_host",
    "obsidian_verify_tls",
    "obsidian_updated_at",
]


def migrate(engine: Engine) -> None:
    """Add Obsidian columns to `canonical_users` if missing. Idempotent, no-op if absent."""
    inspector = inspect(engine)
    if "canonical_users" not in inspector.get_table_names():
        return
    existing = {c["name"] for c in inspector.get_columns("canonical_users")}
    dialect = engine.dialect.name
    with engine.begin() as conn:
        for name in NEW_COLUMN_NAMES:
            if name in existing:
                continue
            decl = _column_decl(name, dialect)
            conn.execute(text(f"ALTER TABLE canonical_users ADD COLUMN {name} {decl}"))


def main() -> None:
    from identity.db import engine
    migrate(engine)
    print("Obsidian columns migration complete.")


if __name__ == "__main__":
    main()
