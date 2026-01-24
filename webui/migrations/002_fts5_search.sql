-- FTS5 Full-Text Search Migration for MyPalClara Desktop
-- Creates FTS5 virtual table with external content and triggers for automatic sync

-- FTS5 virtual table with external content pointing to notes table
-- Uses porter tokenizer for stemming (search "run" matches "running")
-- Uses unicode61 for international character support
CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    title,
    content,
    content='notes',
    content_rowid='id',
    tokenize='porter unicode61'
);

-- CRITICAL: Use AFTER triggers, not BEFORE
-- BEFORE triggers fail because FTS5 needs to fetch old values from content table

-- Trigger for INSERT operations
CREATE TRIGGER IF NOT EXISTS notes_fts_insert AFTER INSERT ON notes BEGIN
    INSERT INTO notes_fts(rowid, title, content)
    VALUES (new.id, new.title, new.content);
END;

-- Trigger for DELETE operations
-- Uses special FTS5 delete syntax to remove entries
CREATE TRIGGER IF NOT EXISTS notes_fts_delete AFTER DELETE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, title, content)
    VALUES('delete', old.id, old.title, old.content);
END;

-- Trigger for UPDATE operations
-- Must delete old entry then insert new entry
CREATE TRIGGER IF NOT EXISTS notes_fts_update AFTER UPDATE ON notes BEGIN
    -- Delete old entry
    INSERT INTO notes_fts(notes_fts, rowid, title, content)
    VALUES('delete', old.id, old.title, old.content);
    -- Insert new entry
    INSERT INTO notes_fts(rowid, title, content)
    VALUES (new.id, new.title, new.content);
END;

-- Rebuild index from existing data (handles migration on existing databases)
INSERT INTO notes_fts(notes_fts) VALUES('rebuild');
