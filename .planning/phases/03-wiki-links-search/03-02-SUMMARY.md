---
phase: 03
plan: 02
subsystem: wiki-links
tags: [rust, regex, backlinks, wiki-links, sqlite]
completed: 2026-01-24
duration: ~6 minutes
dependency-graph:
  requires: [01-02]
  provides: [wiki-link-extraction, backlinks-query, unlinked-mentions-query]
  affects: [03-03, 03-04]
tech-stack:
  added: [regex]
  patterns: [lazy-static-regex, case-insensitive-sql, snippet-extraction]
key-files:
  created:
    - webui/src-tauri/src/commands/wiki_links.rs
  modified:
    - webui/src-tauri/Cargo.toml
    - webui/src-tauri/src/commands/mod.rs
    - webui/src-tauri/src/lib.rs
    - webui/src/lib/bindings.ts
decisions:
  - "LazyLock for regex compilation (Rust 1.80+ stable)"
  - "Delete-then-insert pattern for wiki links (full replace on save)"
  - "COLLATE NOCASE for case-insensitive title matching"
  - "Skip titles shorter than 3 chars to avoid false positives"
  - "LIMIT 50 for unlinked mentions performance"
---

# Phase 3 Plan 02: Wiki Link Extraction Summary

Wiki link extraction and backlinks query system using regex parsing and SQLite.

## One-liner

Regex-based [[wiki link]] extraction with COLLATE NOCASE matching, populating existing wiki_links table for backlinks and unlinked mentions.

## What Was Built

### 1. Wiki Link Regex Pattern

```rust
static WIKI_LINK_REGEX: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"\[\[(?P<title>[^\[\]|]+)(?:\|[^\[\]]*)?\]\]").unwrap()
});
```

Handles:
- Simple links: `[[Note Title]]`
- Display text: `[[Target|display text]]`
- Multi-word: `[[Multi Word Title]]`
- Whitespace trimming: `[[ Padded Title ]]` -> "Padded Title"

### 2. Commands Created

| Command | Description | Returns |
|---------|-------------|---------|
| `extract_and_save_wiki_links` | Parse content and populate wiki_links table | Link count (i64) |
| `get_backlinks` | Notes linking TO given note | Vec<Backlink> |
| `get_unlinked_mentions` | Title mentioned without [[]] wrapper | Vec<UnlinkedMention> |

### 3. Type Definitions

```typescript
type Backlink = { id: number; title: string; updated_at: string }
type UnlinkedMention = { id: number; title: string; snippet: string }
```

### 4. TypeScript Bindings

```typescript
commands.extractAndSaveWikiLinks(noteId: number, content: string)
commands.getBacklinks(noteId: number)
commands.getUnlinkedMentions(noteId: number)
```

## Key Implementation Details

### Case-Insensitive Matching

Title lookups use `COLLATE NOCASE` so `[[my note]]` matches "My Note" in database.

### Full Replace Pattern

On each save, existing links for source note are deleted before inserting new ones. This handles:
- Removed links
- Changed links
- Duplicate prevention

### Unlinked Mentions Logic

1. Query notes where content LIKE '%title%'
2. Exclude notes that already link to target
3. Filter out matches inside [[...]] brackets
4. Extract ~100 char snippet around mention

### Performance Considerations

- LIMIT 50 on unlinked mentions
- Skip titles < 3 chars
- Indexes on source_note_id and target_note_id (from Phase 1 migration)

## Tests

7 unit tests cover:
- Simple link extraction
- Display text handling
- Multiple links
- Multi-word titles
- Whitespace trimming
- No-link content
- Snippet extraction

## Frontend Integration Pattern

Extraction is decoupled from save - frontend controls timing:

```typescript
// In save handler (after successful updateNote)
const result = await commands.updateNote(noteId, { content });
if (result.status === 'ok') {
  // Extract wiki links with separate debounce
  await commands.extractAndSaveWikiLinks(noteId, content);
}
```

## Commits

| Hash | Description |
|------|-------------|
| 7480e24 | Add regex dependency and wiki link extraction |
| ecadd8a | Version bump |

## Deviations from Plan

None - plan executed exactly as written.

## Files Changed

| File | Change |
|------|--------|
| `webui/src-tauri/Cargo.toml` | Added `regex = "1"` |
| `webui/src-tauri/src/commands/wiki_links.rs` | New: 297 lines |
| `webui/src-tauri/src/commands/mod.rs` | Added `pub mod wiki_links` |
| `webui/src-tauri/src/lib.rs` | Registered 3 wiki_links commands |
| `webui/src/lib/bindings.ts` | Added 3 commands + 2 types |

## Verification Results

- [x] Regex handles [[title]] and [[title|display]] patterns
- [x] extract_and_save_wiki_links populates wiki_links table
- [x] get_backlinks returns incoming links for a note
- [x] get_unlinked_mentions finds title mentions without wrapper
- [x] All commands have TypeScript bindings
- [x] Unit tests pass (7/7)
- [x] Cargo build succeeds

## Next Phase Readiness

Ready for:
- Plan 03-03: TipTap wiki-link extension (click-to-navigate)
- Plan 03-04: Backlinks panel UI component
