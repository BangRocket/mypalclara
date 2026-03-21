-- Core tables matching Python SQLAlchemy models

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at DATETIME,
    updated_at DATETIME
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    user_id TEXT NOT NULL,
    context_id TEXT NOT NULL DEFAULT 'default',
    title TEXT,
    archived TEXT NOT NULL DEFAULT 'false',
    started_at DATETIME NOT NULL,
    last_activity_at DATETIME NOT NULL,
    previous_session_id TEXT,
    context_snapshot TEXT,
    session_summary TEXT
);

CREATE INDEX IF NOT EXISTS ix_session_user_context_project
    ON sessions (user_id, context_id, project_id);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at DATETIME NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_message_session_created
    ON messages (session_id, created_at);

CREATE TABLE IF NOT EXISTS channel_summaries (
    id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL UNIQUE,
    summary TEXT DEFAULT '',
    summary_cutoff_at DATETIME,
    last_updated_at DATETIME
);

CREATE TABLE IF NOT EXISTS channel_configs (
    id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL UNIQUE,
    guild_id TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'mention',
    configured_by TEXT,
    configured_at DATETIME,
    updated_at DATETIME
);

CREATE INDEX IF NOT EXISTS ix_channel_config_channel_id
    ON channel_configs (channel_id);

CREATE INDEX IF NOT EXISTS ix_channel_config_guild_id
    ON channel_configs (guild_id);

CREATE TABLE IF NOT EXISTS log_entries (
    id TEXT PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    level TEXT NOT NULL,
    logger_name TEXT NOT NULL,
    message TEXT NOT NULL,
    module TEXT,
    function TEXT,
    line_number INTEGER,
    exception TEXT,
    extra_data TEXT,
    user_id TEXT,
    session_id TEXT
);

CREATE INDEX IF NOT EXISTS ix_log_entry_timestamp ON log_entries (timestamp);
CREATE INDEX IF NOT EXISTS ix_log_entry_level ON log_entries (level);
CREATE INDEX IF NOT EXISTS ix_log_entry_logger_name ON log_entries (logger_name);
CREATE INDEX IF NOT EXISTS ix_log_entry_user_id ON log_entries (user_id);
CREATE INDEX IF NOT EXISTS ix_log_entry_session_id ON log_entries (session_id);
