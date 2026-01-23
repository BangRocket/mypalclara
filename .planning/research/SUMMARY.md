# Project Research Summary

**Project:** MyPalClara Desktop UI
**Domain:** Desktop note-taking app with AI integration (Tauri + React + SQLite)
**Researched:** 2026-01-23
**Confidence:** HIGH

## Executive Summary

MyPalClara Desktop is a Tauri 2.x + React + TypeScript desktop application for AI-collaborative note-taking. The stack is mature and well-documented, with Tauri providing a ~600KB bundle (vs Electron's 150MB), native OS webview integration, and a security-first permission model. The recommended architecture separates concerns cleanly: Rust owns data and security (SQLite, file operations, wiki link parsing), React owns UI and user interaction, and IPC bridges them via typed commands and events.

The primary differentiator is the **Clara as Co-Author** model where the AI is not just an assistant but an active participant with equal read/write access to the knowledge base. Table stakes features (note CRUD, wiki-links, backlinks, full-text search, local storage) are well-understood with established patterns. The riskiest custom work is the wiki-link system, which requires a custom TipTap extension and a link index that multiple features depend on.

Key risks center on IPC performance (JSON serialization overhead), SQLite write locking under aggressive autosave, and FTS5 sync drift. All three have well-documented mitigations: batch operations on the Rust side, WAL mode with proper debouncing, and SQLite triggers for FTS sync. The foundation phase must establish these patterns correctly to avoid rewrites later.

## Key Findings

### Recommended Stack

Tauri 2.9.x with React 19 and TypeScript 5.x provides an optimal foundation. Vite 7 handles builds with 5x faster full builds than previous versions. The tauri-plugin-sql (backed by SQLx) and tauri-plugin-fs cover database and file system needs.

**Core technologies:**
- **Tauri 2.9.x**: Desktop runtime - minimal bundle, native webview, granular permissions, mobile-ready
- **React 19 + TypeScript**: Frontend framework - first-class Vite support, HMR, large ecosystem
- **SQLite + FTS5**: Database and search - local-first, sub-6ms queries, bundled via rusqlite
- **TipTap 3.15.x**: Markdown editor - headless, ProseMirror-based, extensible for wiki-links
- **Zustand 5.x**: State management - minimal boilerplate, no providers, perfect for desktop apps
- **TanStack Query + Router**: Data/routing - type-safe, SPA-optimized, excellent caching
- **shadcn/ui + Tailwind 4**: UI components - copy-paste ownership, accessible, modern styling
- **tauri-specta**: Type safety - generates TypeScript bindings from Rust types

### Expected Features

**Must have (table stakes):**
- Note CRUD with markdown editor and live preview
- Folder/hierarchy organization with drag-drop
- [[wiki-links]] with autocomplete on `[[` typed
- Backlinks panel showing bidirectional connections
- Full-text search with SQLite FTS5
- Quick switcher (Cmd+P) for note navigation
- Auto-save with debounced persistence
- Local SQLite storage (user owns their data)
- Daily notes with calendar navigation

**Should have (competitive):**
- Graph view visualizing note connections
- Unlinked mentions detection
- Link preview on hover
- Export/import functionality
- Clara note operations (read/create/edit/search tools)

**Defer (v2+):**
- AI-suggested links (entity extraction)
- Conversation-to-note synthesis
- Notes sync with mem0 (bidirectional)
- Cross-reference discovery (semantic similarity)
- Real-time collaboration, cloud sync, mobile app

### Architecture Approach

The architecture follows a strict separation: Rust backend handles all SQLite access, wiki link parsing, and FTS5 indexing. The React frontend manages UI state via Zustand (for UI concerns like sidebar collapsed, theme) and TanStack Query (for data from Rust/API). IPC uses Tauri commands for frontend-to-Rust calls and events/channels for Rust-to-frontend notifications. Type safety is enforced via tauri-specta generating TypeScript bindings from Rust struct definitions.

**Major components:**
1. **Rust Commands Layer** (`src-tauri/src/commands/`) - IPC handlers for notes, search, folders, sync
2. **Database Layer** (`src-tauri/src/db/`) - SQLx-backed SQLite with migrations, FTS5 triggers
3. **Services Layer** (`src-tauri/src/services/`) - Wiki link parsing, backlink calculation, FTS indexing
4. **Feature Modules** (`src/features/`) - React components grouped by feature (notes, chat, calendar, search)
5. **Shared Stores** (`src/stores/`) - Zustand stores for UI state (theme, sidebar, selection)

### Critical Pitfalls

1. **IPC Serialization Bottleneck** - All `invoke` calls serialize as JSON. Batch operations on Rust side, paginate results, keep note content in Rust and send only what's needed. Test with realistic note sizes (5KB+) early.

2. **SQLite Write Locking Under Autosave** - Use `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=5000`. Debounce saves at 1-2 seconds, not 200ms. Queue writes through a single writer channel.

3. **FTS5 External Content Sync Drift** - Use SQLite triggers (not application logic) to keep FTS5 in sync with notes table. Add integrity checks comparing note count vs FTS rowcount.

4. **Tauri Capability Misconfiguration** - Features work in `tauri dev` but break in production. Test release builds early (`tauri build`), document every capability, check that permissions match JS function names in kebab-case.

5. **React State Desync from SQLite** - SQLite is source of truth, React is cache. Use TanStack Query for DB-backed state, invalidate/refetch after writes, optimistic updates must have rollback.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Foundation
**Rationale:** Everything depends on the data layer and IPC patterns. Establish these correctly to avoid rewrites.
**Delivers:** Tauri project scaffold, SQLite schema with migrations, basic Rust commands (CRUD), React app shell with Zustand/TanStack Query setup.
**Addresses:** Local-first storage, auto-save foundation, data ownership (table stakes)
**Avoids:** IPC bottleneck (establishes batching patterns), SQLite write locking (WAL + debounce), capability misconfigurations (configured from day 1)

### Phase 2: Core Notes
**Rationale:** Primary user interaction. Must feel solid before adding complexity.
**Delivers:** Notes CRUD UI, TipTap markdown editor with live preview, folder tree component, autosave with proper debouncing.
**Uses:** TipTap, Zustand, TanStack Query, tauri-specta
**Implements:** Notes feature module, UI state management patterns

### Phase 3: Wiki Links & Search
**Rationale:** Link index is central dependency for backlinks, unlinked mentions, and graph view. FTS5 enables quick switcher and search.
**Delivers:** Wiki link parsing in Rust, `[[autocomplete]]`, backlinks panel, FTS5 search, quick switcher (Cmd+P)
**Avoids:** FTS5 sync drift (triggers), wiki link parse performance (debounced extraction), FTS5 JOIN performance (LIMIT before JOIN)

### Phase 4: Calendar & Daily Notes
**Rationale:** Independent feature that can be developed in parallel with Phase 3 refinement.
**Delivers:** Calendar widget, daily note creation, date-based navigation, basic event CRUD
**Uses:** shadcn/ui calendar component, existing notes infrastructure

### Phase 5: Chat Integration
**Rationale:** Requires existing notes system to be stable. HTTP-based, mostly frontend work.
**Delivers:** Chat panel connecting to Clara backend, message history, streaming responses
**Uses:** TanStack Query, Tauri HTTP plugin with capability permissions

### Phase 6: Clara Note Tools
**Rationale:** Final integration layer. Clara needs stable note system to read/write.
**Delivers:** Clara can read/create/edit/search notes, "save this as a note" from conversation, author attribution (user vs Clara)
**Implements:** Note tools API endpoints, attribution toggle UI

### Phase Ordering Rationale

- **Foundation first:** Database schema, IPC patterns, and state management patterns must be established before any feature work. Changing these later causes cascading rewrites.
- **Notes before links:** Wiki link parsing operates on note content. Need stable note storage and editor before link features.
- **Links before graph:** The link index powers backlinks, unlinked mentions, and eventually graph view. Build the index infrastructure in Phase 3.
- **Calendar parallel-safe:** Calendar/daily notes use the notes table but don't depend on wiki links. Can overlap with Phase 3.
- **Chat late:** HTTP integration is independent of local features. Doing it later means more stable local foundation.
- **Clara integration last:** Requires both stable notes system and chat integration. This is the capstone.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (Wiki Links):** Custom TipTap extension required. No built-in wiki-link support. Reference GitHub Discussion #5067 for partial implementation patterns.
- **Phase 6 (Clara Tools):** API design for note operations needs coordination with existing Clara backend. May need new endpoints.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Foundation):** Well-documented Tauri + SQLite patterns, official plugin documentation.
- **Phase 2 (Core Notes):** TipTap has excellent React integration docs, autosave is a solved pattern.
- **Phase 4 (Calendar):** shadcn/ui calendar component exists, daily notes are simple templates.
- **Phase 5 (Chat):** Standard HTTP/streaming patterns, TanStack Query handles caching.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified via npm registry, official Tauri 2.x docs |
| Features | HIGH | Extensive market research, established patterns from Obsidian/Notion |
| Architecture | HIGH | Official Tauri IPC docs, verified code patterns from GitHub examples |
| Pitfalls | MEDIUM-HIGH | Combination of official docs and community reports, some pitfalls are experiential |

**Overall confidence:** HIGH

### Gaps to Address

- **Wiki link TipTap extension:** No complete reference implementation. Plan for iteration during Phase 3. Consider looking at Obsidian's editor implementation for inspiration.
- **Clara backend API for note operations:** Existing Clara backend may need new endpoints. Coordinate design before Phase 6.
- **Cross-platform WebView variance:** Test on macOS, Windows, and Linux early. Set up multi-platform CI in Phase 1.

## Sources

### Primary (HIGH confidence)
- [Tauri v2 Official Documentation](https://v2.tauri.app/) - IPC, plugins, capabilities, security
- [TipTap Documentation](https://tiptap.dev/docs/editor/) - React integration, markdown extension
- [SQLite FTS5 Documentation](https://www.sqlite.org/fts5.html) - Full-text search, triggers, ranking
- [npm Registry](https://www.npmjs.com/) - Version verification for all packages
- [Zustand Documentation](https://zustand.docs.pmnd.rs/) - State management patterns

### Secondary (MEDIUM confidence)
- [GitHub tauri-specta](https://github.com/specta-rs/tauri-specta) - TypeScript binding generation
- [TipTap Wiki Links Discussion #5067](https://github.com/ueberdosis/tiptap/discussions/5067) - Partial implementation patterns
- [Tauri IPC Discussion #5690](https://github.com/tauri-apps/tauri/discussions/5690) - Performance bottleneck details
- Community comparison articles (Notion vs Obsidian, state management patterns)

### Tertiary (needs validation)
- Specific debounce timing recommendations (test with actual usage patterns)
- FTS5 JOIN performance thresholds (profile with realistic data volumes)

---
*Research completed: 2026-01-23*
*Ready for roadmap: yes*
