-- Cortex Memory Schema for PostgreSQL with pgvector
-- Run this against your Cortex database to set up the schema

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
