#!/usr/bin/env python3
"""
Migrate Cortex schema to Postgres.

Creates the long_term_memories and project_context tables with pgvector support.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Load .env
from dotenv import load_dotenv

load_dotenv()


SCHEMA_SQL = """
-- Cortex Memory Schema for PostgreSQL with pgvector

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Long-term memory table with embeddings for semantic search
CREATE TABLE IF NOT EXISTS long_term_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),  -- text-embedding-3-small dimension
    category VARCHAR(100),
    importance FLOAT DEFAULT 0.5,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',

    -- Indexes for common queries
    CONSTRAINT valid_importance CHECK (importance >= 0.0 AND importance <= 1.0)
);

-- Index for user_id lookups
CREATE INDEX IF NOT EXISTS idx_ltm_user_id ON long_term_memories(user_id);

-- Index for category filtering
CREATE INDEX IF NOT EXISTS idx_ltm_category ON long_term_memories(category);

-- Index for timestamp ordering
CREATE INDEX IF NOT EXISTS idx_ltm_created_at ON long_term_memories(created_at DESC);

-- Vector index for semantic search (IVFFlat for approximate nearest neighbor)
-- Use lists = rows/1000 for optimal performance, minimum 100
CREATE INDEX IF NOT EXISTS idx_ltm_embedding ON long_term_memories
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Project context table (optional, for project-specific memories)
CREATE TABLE IF NOT EXISTS project_context (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    key VARCHAR(255) NOT NULL,
    value TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(project_id, user_id, key)
);

CREATE INDEX IF NOT EXISTS idx_pc_project_user ON project_context(project_id, user_id);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for project_context
DROP TRIGGER IF EXISTS update_project_context_updated_at ON project_context;
CREATE TRIGGER update_project_context_updated_at
    BEFORE UPDATE ON project_context
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
"""


async def migrate():
    """Run the Cortex schema migration."""
    import asyncpg

    # Get database URL from environment
    db_url = os.getenv("CORTEX_POSTGRES_URL") or os.getenv("MEM0_DATABASE_URL")

    if not db_url:
        print("ERROR: No database URL found.")
        print("Set CORTEX_POSTGRES_URL or MEM0_DATABASE_URL in .env")
        sys.exit(1)

    print(f"Connecting to database...")
    print(f"URL: {db_url.split('@')[1] if '@' in db_url else db_url}")  # Hide password

    try:
        conn = await asyncpg.connect(dsn=db_url)

        print("Running Cortex schema migration...")
        await conn.execute(SCHEMA_SQL)

        # Verify tables exist
        tables = await conn.fetch(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('long_term_memories', 'project_context')
            """
        )
        table_names = [t["table_name"] for t in tables]

        print(f"\nCreated tables: {', '.join(table_names)}")

        # Check pgvector extension
        ext = await conn.fetchrow(
            "SELECT extname FROM pg_extension WHERE extname = 'vector'"
        )
        if ext:
            print("pgvector extension: enabled")
        else:
            print("WARNING: pgvector extension not found")

        await conn.close()
        print("\nMigration complete!")

    except Exception as e:
        print(f"ERROR: Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(migrate())
