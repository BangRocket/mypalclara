# Domain Pitfalls

**Domain:** Tauri + React + SQLite Desktop Note-Taking App
**Researched:** 2026-01-23
**Confidence:** MEDIUM-HIGH (verified via official docs, GitHub discussions, community reports)

---

## Critical Pitfalls

Mistakes that cause rewrites or major issues.

### Pitfall 1: IPC Serialization Bottleneck

**What goes wrong:** All Tauri `invoke` calls serialize data as JSON strings. Passing large content (note bodies, search results, bulk operations) over IPC becomes slow. Apps feel sluggish when loading or saving large notes.

**Why it happens:** Tauri's invoke/command system has a fundamental bottleneck - parameters and return values are serialized around strings due to webview library restrictions across platforms.

**Consequences:**
- Noticeable lag when saving/loading notes >10KB
- Search results with many matches take seconds to render
- Bulk operations (import/export) become unusably slow

**Prevention:**
- Batch operations on the Rust side, return only summaries
- Paginate search results (return 20 at a time, not 1000)
- For large data, use custom protocol via `register_uri_scheme_protocol` (bypasses IPC)
- Keep note content in Rust, send only what's needed to render

**Detection:**
- Profile IPC call times early
- Test with realistic note sizes (5KB+ of markdown)
- Monitor for >100ms IPC round-trips

**Phase to address:** Phase 1 (Foundation) - establish IPC patterns before building features

**Sources:** [Tauri IPC Discussion #5690](https://github.com/tauri-apps/tauri/discussions/5690)

---

### Pitfall 2: SQLite Write Locking Under Autosave

**What goes wrong:** Autosave triggers write transactions while FTS5 indexing or other writes are in progress. Results in "database is locked" errors, data loss, or corrupt state.

**Why it happens:** SQLite uses a global write lock - only one writer at a time. With aggressive autosave (every keystroke or short debounce), writes pile up and conflict.

**Consequences:**
- "Database is locked" errors appearing randomly
- Autosaved content not persisting
- FTS5 index becoming stale or corrupt
- App hangs waiting for lock timeout

**Prevention:**
```rust
// In database setup:
PRAGMA journal_mode=WAL;      // Allow concurrent reads during writes
PRAGMA busy_timeout=5000;     // Wait 5s instead of failing immediately
```

- Use longer debounce (1-2 seconds, not 200ms)
- Queue write operations through a single writer channel
- Keep transactions small (one note save = one transaction)
- Separate FTS5 updates from content saves (or batch them)

**Detection:**
- Test rapid typing with autosave enabled
- Log all SQLITE_BUSY errors
- Monitor write transaction durations

**Phase to address:** Phase 1 (Foundation) - database layer setup

**Sources:** [SQLite Locking v3](https://sqlite.org/lockingv3.html), [SQLite Concurrent Writes](https://tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors/)

---

### Pitfall 3: FTS5 External Content Sync Drift

**What goes wrong:** The FTS5 virtual table and the actual notes table become out of sync. Searches return stale results, deleted notes appear in search, or notes are missing from search.

**Why it happens:** When using FTS5 with external content tables (recommended for avoiding data duplication), you must manually keep them in sync via triggers or application logic. Missed updates, failed transactions, or VACUUM operations can break sync.

**Consequences:**
- Search results don't match actual content
- Deleted notes haunt search results
- New notes invisible to search
- Users lose trust in search feature

**Prevention:**
```sql
-- Create triggers to auto-sync
CREATE TRIGGER notes_ai AFTER INSERT ON notes BEGIN
  INSERT INTO notes_fts(rowid, title, content) VALUES (new.id, new.title, new.content);
END;

CREATE TRIGGER notes_ad AFTER DELETE ON notes BEGIN
  INSERT INTO notes_fts(notes_fts, rowid, title, content) VALUES('delete', old.id, old.title, old.content);
END;

CREATE TRIGGER notes_au AFTER UPDATE ON notes BEGIN
  INSERT INTO notes_fts(notes_fts, rowid, title, content) VALUES('delete', old.id, old.title, old.content);
  INSERT INTO notes_fts(rowid, title, content) VALUES (new.id, new.title, new.content);
END;
```

- Use SQLite triggers (not application logic) for FTS sync
- Test FTS sync after every write operation type
- Add integrity checks that compare note count vs FTS rowcount
- Never run `VACUUM` expecting it to fix FTS inconsistencies - it won't

**Detection:**
- Periodic integrity check: `SELECT COUNT(*) FROM notes` vs `SELECT COUNT(*) FROM notes_fts`
- Test: create note, search immediately, verify found
- Test: delete note, search immediately, verify not found

**Phase to address:** Phase 2 (Search) - when implementing FTS5

**Sources:** [SQLite FTS5](https://www.sqlite.org/fts5.html), [FTS5 External Content](https://sqlite.work/optimizing-fts5-external-content-tables-and-vacuum-interactions/)

---

### Pitfall 4: Tauri Capability/Permission Misconfigurations

**What goes wrong:** Features work in `tauri dev` but fail silently or with cryptic errors in production builds. File system access, dialog boxes, or other Tauri APIs stop working.

**Why it happens:** Tauri v2 uses capability-based security. All plugins and commands are blocked by default. Dev mode may have different defaults than release builds.

**Consequences:**
- Features mysteriously break in production
- "Permission denied" errors with no clear cause
- Security vulnerabilities if permissions are overly broad
- Hours debugging release-only issues

**Prevention:**
```json
// src-tauri/capabilities/default.json
{
  "identifier": "default",
  "windows": ["main"],
  "permissions": [
    "core:default",
    "sql:allow-select",
    "sql:allow-execute",
    "dialog:allow-open",
    "dialog:allow-save"
    // Be explicit about every permission needed
  ]
}
```

- Test release builds early and often (`tauri build` not just `tauri dev`)
- Document every capability your app needs
- Use minimal permissions - add only what's needed
- Check permissions match JS function names in kebab-case

**Detection:**
- Build and test release version in CI weekly
- Log all Tauri API errors with full context
- Test on fresh machine (not just dev environment)

**Phase to address:** Phase 1 (Foundation) - configure immediately when setting up Tauri

**Sources:** [Tauri Capabilities](https://v2.tauri.app/security/capabilities/), [Tauri Permissions](https://v2.tauri.app/security/permissions/)

---

## Moderate Pitfalls

Mistakes that cause delays or technical debt.

### Pitfall 5: React State Desync from SQLite

**What goes wrong:** React state and SQLite database drift apart. User sees stale data, edits overwrite each other, or the app shows inconsistent state across components.

**Why it happens:**
- React state updated optimistically without confirming DB write
- Multiple components holding copies of the same note
- Autosave races with manual saves
- No single source of truth pattern

**Consequences:**
- User edits lost silently
- "I saved this!" frustration
- Inconsistent UI across windows/components
- Hard-to-debug state corruption

**Prevention:**
- SQLite is the source of truth, React state is a cache
- Use React Query, SWR, or similar for DB-backed state
- Optimistic updates must have rollback on failure
- Invalidate/refetch after any write operation
- Single writer pattern for each entity

```typescript
// Pattern: Always confirm write before updating React state
const saveNote = async (note: Note) => {
  try {
    await invoke('save_note', { note });
    // Only update React state AFTER successful write
    queryClient.invalidateQueries(['notes', note.id]);
  } catch (e) {
    // Rollback optimistic update
    showError("Save failed");
  }
};
```

**Detection:**
- Compare UI state vs database state in dev tools
- Test rapid editing with network/IPC delays simulated
- Log all write failures prominently

**Phase to address:** Phase 1 (Foundation) - establish patterns before building features

**Sources:** [Tauri State Management](https://v2.tauri.app/develop/state-management/), [Zustand with Tauri](https://www.gethopp.app/blog/tauri-window-state-sync)

---

### Pitfall 6: Autosave Debounce State Loss

**What goes wrong:** User types quickly, autosave fires mid-keystroke, and subsequent keystrokes are lost or the input becomes unresponsive.

**Why it happens:**
- Debounced save function recreated on every render
- State updated in the debounced callback (too late)
- Component re-renders with stale/saved state during typing

**Consequences:**
- Characters disappear while typing
- Cursor jumps unexpectedly
- Input feels laggy/broken
- Users learn to pause after typing (terrible UX)

**Prevention:**
```typescript
// WRONG: Debounce the whole onChange
const debouncedOnChange = useMemo(
  () => debounce((value) => {
    setValue(value); // TOO LATE - input won't work
    saveToDb(value);
  }, 500),
  []
);

// RIGHT: Update state immediately, debounce only the save
const [value, setValue] = useState('');
const debouncedSave = useMemo(
  () => debounce((v) => saveToDb(v), 1000),
  []
);

const onChange = (e) => {
  setValue(e.target.value);        // Immediate
  debouncedSave(e.target.value);   // Debounced
};
```

- Use `useRef` for debounced function to survive re-renders
- Never update controlled input state in debounced callback
- Separate immediate state from persistence layer
- Use 1000-2000ms debounce, not 200ms

**Detection:**
- Test rapid typing (80+ WPM)
- Test typing during save operations
- Check for characters being dropped

**Phase to address:** Phase 1 (Foundation) - establish autosave pattern immediately

**Sources:** [Debouncing in React](https://www.developerway.com/posts/debouncing-in-react), [React Query Autosave](https://pz.com.au/avoiding-race-conditions-and-data-loss-when-autosaving-in-react-query)

---

### Pitfall 7: Wiki Link Parsing Performance

**What goes wrong:** Parsing `[[wiki links]]` on every keystroke causes input lag. Large notes with many links become slow to edit.

**Why it happens:**
- Regex parsing on every content change
- Full document re-parse instead of incremental
- Link resolution (checking if target exists) during parse

**Consequences:**
- Typing lag in link-heavy notes
- UI freezes during paste of large content
- Poor experience on slower machines

**Prevention:**
- Parse links only on debounced intervals, not every keystroke
- Use incremental parsing (only re-parse changed sections)
- Cache link existence checks
- Separate parsing from rendering (parse in background, render cached)

```typescript
// Pattern: Debounced link extraction
const [links, setLinks] = useState<string[]>([]);
const extractLinks = useMemo(
  () => debounce((content: string) => {
    const found = content.match(/\[\[([^\]]+)\]\]/g) || [];
    setLinks(found.map(l => l.slice(2, -2)));
  }, 300),
  []
);
```

**Detection:**
- Profile with notes containing 50+ wiki links
- Test pasting large markdown documents
- Measure time from keystroke to render

**Phase to address:** Phase 2 (Wiki Links) - when implementing link parsing

**Sources:** [remark-wiki-link](https://github.com/landakram/remark-wiki-link)

---

### Pitfall 8: FTS5 JOIN Performance Cliff

**What goes wrong:** Search queries that JOIN FTS5 results with the notes table become extremely slow when result sets are large.

**Why it happens:** FTS5 virtual tables have different query planning than regular tables. JOINs often result in suboptimal query plans.

**Consequences:**
- Search fast for rare terms, painfully slow for common terms
- "database" search takes 10+ seconds
- App appears frozen during broad searches

**Prevention:**
```sql
-- SLOW: Direct JOIN
SELECT n.* FROM notes n
JOIN notes_fts f ON n.id = f.rowid
WHERE notes_fts MATCH 'search term'
ORDER BY rank;

-- FASTER: Subquery with LIMIT
SELECT * FROM notes WHERE id IN (
  SELECT rowid FROM notes_fts
  WHERE notes_fts MATCH 'search term'
  ORDER BY rank
  LIMIT 50
);
```

- Always LIMIT FTS5 results before JOINing
- Use subqueries instead of JOINs for FTS5
- Paginate search results (never return all matches)
- Consider ranking in application code for complex scoring

**Detection:**
- Test search for common words ("the", "is", "note")
- Profile queries returning >100 results
- Add query timing to search implementation

**Phase to address:** Phase 2 (Search) - when implementing search

**Sources:** [SQLite Forum: JOINs with FTS5](https://sqlite.org/forum/info/509bdbe534f58f20)

---

### Pitfall 9: WebView Compatibility Variance

**What goes wrong:** App looks/works differently on different operating systems because Tauri uses native webviews (WebKit on Linux/macOS, WebView2 on Windows).

**Why it happens:** Unlike Electron which bundles Chromium, Tauri uses the system's webview. CSS features, JS APIs, and rendering can vary.

**Consequences:**
- Layout breaks on certain platforms
- Features work on dev machine, fail in production
- Inconsistent user experience across platforms

**Prevention:**
- Test on all target platforms early and often
- Use autoprefixer for CSS
- Avoid bleeding-edge CSS/JS features
- Check WebKit and WebView2 compatibility for any API used
- Set up CI to build and test on macOS, Windows, and Linux

**Detection:**
- Visual regression testing across platforms
- Feature tests in CI for all platforms
- Beta test on diverse user machines

**Phase to address:** Phase 1 (Foundation) - set up multi-platform CI immediately

**Sources:** [Tauri Cross-Platform](https://v1.tauri.app/v1/guides/building/cross-platform/), [Tauri Prerequisites](https://v2.tauri.app/start/prerequisites/)

---

## Minor Pitfalls

Mistakes that cause annoyance but are fixable.

### Pitfall 10: Database Path Issues in Dev vs Production

**What goes wrong:** Database file created in wrong location, or dev database overwrites production data, or database not found in release builds.

**Why it happens:** Hardcoded paths, relative paths, or dotenv-based paths that don't exist in production.

**Prevention:**
```rust
// Use Tauri's app_data_dir(), never hardcode paths
let app_data = app_handle.path_resolver().app_data_dir()
    .expect("Failed to get app data dir");
let db_path = app_data.join("notes.db");
```

- Never use relative paths for database
- Never use dotenv in production
- Use `app_data_dir()` from Tauri path resolver
- Create directory if it doesn't exist

**Phase to address:** Phase 1 (Foundation)

**Sources:** [Tauri + SQLite Guide](https://dev.to/focuscookie/tauri-20-sqlite-db-react-2aem)

---

### Pitfall 11: No Stemming in FTS5 Default

**What goes wrong:** Search for "running" doesn't find notes containing "run" or "runs".

**Why it happens:** FTS5 default tokenizer does exact word matching, no stemming.

**Prevention:**
```sql
-- Use porter tokenizer for English stemming
CREATE VIRTUAL TABLE notes_fts USING fts5(
  title, content,
  tokenize='porter unicode61'
);
```

**Phase to address:** Phase 2 (Search)

**Sources:** [SQLite FTS5](https://www.sqlite.org/fts5.html)

---

### Pitfall 12: BM25 Ranking Direction

**What goes wrong:** Search results appear in worst-to-best order instead of best-to-worst.

**Why it happens:** BM25 returns negative scores (lower = better). Forgetting to use DESC or misunderstanding the scoring.

**Prevention:**
```sql
-- Note: bm25() returns NEGATIVE values, so this works correctly
SELECT * FROM notes_fts WHERE notes_fts MATCH 'query'
ORDER BY bm25(notes_fts);  -- Lower (more negative) = better match

-- Or explicitly:
ORDER BY bm25(notes_fts) ASC;  -- Best matches first
```

**Phase to address:** Phase 2 (Search)

**Sources:** [SQLite FTS5](https://www.sqlite.org/fts5.html)

---

### Pitfall 13: Missing FTS5 Extension

**What goes wrong:** "no such module: fts5" error on user machines.

**Why it happens:** Some SQLite builds don't include FTS5 by default.

**Prevention:**
- Use rusqlite with `bundled` feature (includes FTS5)
- Or use `bundled-sqlcipher` for encryption + FTS5
- Test on fresh system without development SQLite

```toml
# Cargo.toml
[dependencies]
rusqlite = { version = "0.31", features = ["bundled"] }
```

**Phase to address:** Phase 1 (Foundation) - ensure bundled SQLite

**Sources:** [SQLite FTS5](https://www.sqlite.org/fts5.html)

---

### Pitfall 14: Cross-Compilation Not Supported

**What goes wrong:** Attempting to build Windows app from macOS or vice versa fails.

**Why it happens:** Tauri relies on native libraries and toolchains. True cross-compilation is not possible.

**Prevention:**
- Use GitHub Actions with Tauri Action for multi-platform builds
- Set up CI to build on each target platform
- Don't promise cross-compilation to stakeholders

**Phase to address:** Phase 1 (Foundation) - set up CI immediately

**Sources:** [Tauri Cross-Platform](https://v1.tauri.app/v1/guides/building/cross-platform/)

---

### Pitfall 15: Rust Errors in Frontend Development

**What goes wrong:** Frontend developer makes change, Rust code fails to compile, unclear error messages.

**Why it happens:** Tauri requires valid Rust code. TypeScript developers may not understand Rust compiler errors.

**Actually a benefit:** Tauri won't compile with Rust errors, catching issues at build time rather than runtime.

**Prevention:**
- Keep Rust layer thin and stable
- Establish clear interface contracts between frontend and backend
- Document Tauri commands and their types
- Use TypeScript types generated from Rust types

**Phase to address:** Ongoing throughout development

**Sources:** [Tauri Opinion Blog](https://blog.frankel.ch/opinion-tauri/)

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|----------------|------------|
| Foundation/Database | SQLite path issues, FTS5 not bundled | Use Tauri paths, bundled rusqlite |
| Foundation/IPC | Serialization bottleneck | Establish batching patterns early |
| Foundation/State | React/SQLite desync | SQLite as truth, React as cache |
| Autosave | Debounce state loss | Immediate state, debounced save |
| Wiki Links | Parse performance | Debounced/incremental parsing |
| Search/FTS5 | Sync drift, JOIN performance | Triggers, LIMIT before JOIN |
| Production | Capabilities broken | Test release builds in CI |
| Multi-platform | WebView variance | Test all platforms in CI |

---

## Sources

### Official Documentation
- [Tauri v2 Security - Capabilities](https://v2.tauri.app/security/capabilities/)
- [Tauri v2 Security - Permissions](https://v2.tauri.app/security/permissions/)
- [Tauri v2 State Management](https://v2.tauri.app/develop/state-management/)
- [Tauri v2 Prerequisites](https://v2.tauri.app/start/prerequisites/)
- [SQLite FTS5 Extension](https://www.sqlite.org/fts5.html)
- [SQLite Locking v3](https://sqlite.org/lockingv3.html)

### GitHub Discussions & Issues
- [Tauri IPC Improvements #5690](https://github.com/tauri-apps/tauri/discussions/5690)
- [SQLite Forum: JOINs with FTS5](https://sqlite.org/forum/info/509bdbe534f58f20)
- [Tauri Cross-Platform #1114](https://github.com/tauri-apps/tauri/issues/1114)

### Community Resources
- [SQLite Concurrent Writes](https://tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors/)
- [Debouncing in React](https://www.developerway.com/posts/debouncing-in-react)
- [React Query Autosave](https://pz.com.au/avoiding-race-conditions-and-data-loss-when-autosaving-in-react-query)
- [Zustand with Tauri](https://www.gethopp.app/blog/tauri-window-state-sync)
- [Tauri + SQLite Guide](https://dev.to/focuscookie/tauri-20-sqlite-db-react-2aem)
