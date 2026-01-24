---
phase: 03-wiki-links-search
plan: 01
subsystem: search
tags: [fts5, sqlite, search, tauri, rust]

# Dependency Graph
requires: [02-04]
provides: [search-backend, note-autocomplete]
affects: [03-02, 03-05]

# Tech Stack
tech-stack:
  added: []
  patterns: [fts5-external-content, after-triggers, bm25-ranking]

# Files
key-files:
  created:
    - webui/migrations/002_fts5_search.sql
    - webui/src-tauri/src/commands/search.rs
  modified:
    - webui/src-tauri/src/commands/mod.rs
    - webui/src-tauri/src/lib.rs
    - webui/src/lib/bindings.ts

# Decisions
decisions:
  - id: fts5-external-content
    choice: External content table with AFTER triggers
    rationale: Saves 50-80% space, automatic sync via SQLite triggers
  - id: porter-unicode61
    choice: Combined porter + unicode61 tokenizers
    rationale: Porter enables stemming (run matches running), unicode61 handles international characters
  - id: bm25-ranking
    choice: BM25 ranking algorithm
    rationale: Industry-standard relevance ranking, built into FTS5
  - id: empty-query-behavior
    choice: Empty queries return empty results
    rationale: Prevents expensive full-table scans on empty input

# Metrics
metrics:
  duration: 6m
  completed: 2026-01-24
---

# Phase 3 Plan 01: FTS5 Search Backend Summary

FTS5 full-text search with external content table, AFTER triggers for automatic sync, BM25 ranking, and highlighted snippets

## What Was Built

### FTS5 Migration (002_fts5_search.sql)
Created SQLite FTS5 virtual table with external content configuration:
- `notes_fts` virtual table points to `notes` table (no data duplication)
- Combined `porter unicode61` tokenizers for stemming and international support
- Three AFTER triggers for INSERT/DELETE/UPDATE operations
- Automatic rebuild on migration for existing data

### Search Commands (search.rs)
Two new Tauri commands:
1. **search_notes(query, limit)** - Full-text search with BM25 ranking and snippet generation
   - Uses `snippet()` function with `<mark>` tags for highlighting
   - Limits results (default 50) for performance
   - Returns empty array for empty queries

2. **get_all_note_titles()** - Lightweight note list for autocomplete
   - Returns only id and title
   - Ordered by updated_at DESC (most recent first)

### TypeScript Bindings
Generated bindings include:
- `commands.searchNotes(query: string, limit: number | null)`
- `commands.getAllNoteTitles()`
- `SearchResult` type: `{ id, title, snippet, rank }`
- `NoteTitle` type: `{ id, title }`

## Technical Details

### FTS5 Trigger Pattern
Critical: Use AFTER triggers, not BEFORE. BEFORE triggers fail because FTS5 needs to fetch old values from the content table during delete operations.

```sql
-- Delete uses special FTS5 syntax
CREATE TRIGGER notes_fts_delete AFTER DELETE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, title, content)
    VALUES('delete', old.id, old.title, old.content);
END;
```

### Search Query Pattern
```sql
SELECT n.id, n.title,
       snippet(notes_fts, 1, '<mark>', '</mark>', '...', 32) as snippet,
       bm25(notes_fts) as rank
FROM notes_fts
JOIN notes n ON notes_fts.rowid = n.id
WHERE notes_fts MATCH ?
ORDER BY rank
LIMIT ?
```

## Verification

1. FTS5 table created with correct schema
2. All three triggers (insert, delete, update) present
3. Note counts match between notes and notes_fts tables (5 = 5)
4. Search query returns results with `<mark>` highlighted snippets
5. Rust tests pass (7/7)
6. TypeScript bindings include all new commands and types

## Deviations from Plan

None - plan executed exactly as written.

## Dependencies for Next Plans

- **03-02 (Quick Switcher):** Uses `getAllNoteTitles()` for fuzzy search autocomplete
- **03-05 (Search Bar):** Uses `searchNotes()` for full-text search UI

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 10e2365 | FTS5 migration with external content and AFTER triggers |
| 2 | 329f6b6 | Search commands with BM25 ranking and snippets |
| 3 | b5b3fc0 | TypeScript bindings regenerated (includes search commands) |
