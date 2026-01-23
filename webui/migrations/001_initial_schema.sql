-- Initial schema for MyPalClara Desktop
-- This migration creates the core tables for notes and folders

-- Folders for organizing notes
CREATE TABLE IF NOT EXISTS folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    parent_id INTEGER REFERENCES folders(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Notes with markdown content
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    folder_id INTEGER REFERENCES folders(id) ON DELETE SET NULL,
    author TEXT NOT NULL DEFAULT 'user',
    is_daily_note INTEGER NOT NULL DEFAULT 0,
    daily_note_date TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Wiki links between notes (populated on save)
CREATE TABLE IF NOT EXISTS wiki_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    target_note_id INTEGER REFERENCES notes(id) ON DELETE CASCADE,
    target_title TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_notes_folder ON notes(folder_id);
CREATE INDEX IF NOT EXISTS idx_notes_updated ON notes(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_notes_daily ON notes(is_daily_note, daily_note_date);
CREATE INDEX IF NOT EXISTS idx_wiki_links_source ON wiki_links(source_note_id);
CREATE INDEX IF NOT EXISTS idx_wiki_links_target ON wiki_links(target_note_id);
CREATE INDEX IF NOT EXISTS idx_folders_parent ON folders(parent_id);

-- Create a default "Notes" folder
INSERT OR IGNORE INTO folders (id, name) VALUES (1, 'Notes');
