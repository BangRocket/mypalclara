# Roadmap: v1.0 MyPalClara Desktop UI

## Overview

6 phases to deliver a shared knowledge platform where Clara and the user collaborate on notes, ideas, and conversations.

## Phase Summary

| Phase | Name | Requirements | Research Flag |
|-------|------|--------------|---------------|
| 1 | Foundation | REQ-001, REQ-002, REQ-003 | Skip (standard patterns) |
| 2 | Core Notes | REQ-004 through REQ-008, REQ-022 | Skip (standard patterns) |
| 3 | Wiki Links & Search | REQ-009 through REQ-012, REQ-023, REQ-024 | **Research needed** |
| 4 | Calendar & Daily Notes | REQ-013, REQ-014 | Skip (standard patterns) |
| 5 | Chat Integration | REQ-015, REQ-016 | Skip (standard patterns) |
| 6 | Clara Note Tools | REQ-017 through REQ-021 | **Research needed** |

---

## Phase 1: Foundation

**Goal:** Establish data layer and IPC patterns correctly to avoid rewrites later.

**Plans:** 3 plans

Plans:
- [ ] 01-01-PLAN.md — Tauri + React project scaffold
- [ ] 01-02-PLAN.md — SQLite database setup with migrations
- [ ] 01-03-PLAN.md — Type-safe IPC with tauri-specta

**Delivers:**
- Tauri 2.9.x project scaffold in `/webui/`
- SQLite database with migration system
- Basic Rust commands (notes CRUD skeleton)
- React app shell with Zustand + TanStack Query setup
- Type-safe IPC via tauri-specta
- Capability permissions configured

**Requirements:**
- REQ-001: Desktop app shell (Tauri + React + TypeScript)
- REQ-002: SQLite database with migrations
- REQ-003: Type-safe IPC between Rust and React

**Key Patterns to Establish:**
- WAL mode for SQLite (`PRAGMA journal_mode=WAL`)
- Batch operations on Rust side (minimize IPC round-trips)
- TanStack Query for DB-backed state
- Error handling patterns across IPC boundary

**Pitfalls to Avoid:**
- Capability misconfiguration (test release build early)
- Missing busy_timeout on SQLite
- Unbatched IPC calls

**Acceptance:**
- `tauri dev` launches app with React frontend
- SQLite database created on first launch
- At least one Rust command callable from React with type safety
- Release build works (`tauri build`)

---

## Phase 2: Core Notes

**Goal:** Primary user interaction must feel solid before adding complexity.

**Delivers:**
- Notes list view with folder tree sidebar
- TipTap markdown editor with live preview
- Note CRUD operations (create, read, update, delete)
- Folder creation and organization
- Drag-drop for moving notes between folders
- Autosave with 1-2 second debounce
- Export note as markdown file

**Requirements:**
- REQ-004: Notes CRUD
- REQ-005: Markdown editor with live preview
- REQ-006: Folder/hierarchy organization
- REQ-007: Sidebar navigation with folder tree
- REQ-008: Auto-save with debounced persistence
- REQ-022: Export notes as markdown files

**Key Patterns:**
- TipTap extensions for markdown (bold, italic, headers, code, lists)
- Optimistic updates with TanStack Query
- Debounced save on content change
- Zustand for UI state (selected note, sidebar collapsed)

**Pitfalls to Avoid:**
- React state desyncing from SQLite (always refetch after write)
- Autosave too aggressive (1-2s debounce, not 200ms)
- Missing loading/error states

**Acceptance:**
- Can create note in any folder
- Can edit note with markdown formatting
- Changes auto-save after typing stops
- Can organize notes into folders
- Can export note as .md file

---

## Phase 3: Wiki Links & Search

**Goal:** Link index is central dependency for backlinks, unlinked mentions, and future graph view.

**Research Flag:** Custom TipTap extension required. No built-in wiki-link support.

**Delivers:**
- `[[wiki-link]]` syntax with autocomplete on `[[`
- Backlinks panel showing which notes link to current note
- Unlinked mentions detection (title appears without link)
- Link preview on hover
- Full-text search with FTS5
- Quick switcher (Cmd+P / Ctrl+P)

**Requirements:**
- REQ-009: Wiki-links with autocomplete
- REQ-010: Backlinks panel
- REQ-011: Full-text search (FTS5)
- REQ-012: Quick switcher
- REQ-023: Unlinked mentions
- REQ-024: Link preview on hover

**Key Patterns:**
- Wiki link parsing in Rust (regex + link index table)
- FTS5 external content table synced via triggers
- Debounced link extraction on save
- TipTap Mark extension for wiki-links

**Pitfalls to Avoid:**
- FTS5 sync drift (use SQLite triggers, not app logic)
- FTS5 JOIN performance (LIMIT before JOIN)
- Blocking UI during link extraction

**Acceptance:**
- Typing `[[` shows autocomplete of note titles
- Clicking wiki-link navigates to linked note
- Backlinks panel shows incoming links
- Search returns relevant notes ranked by FTS5
- Quick switcher opens with Cmd+P

---

## Phase 4: Calendar & Daily Notes

**Goal:** Independent feature for temporal organization. Can develop in parallel with Phase 3 refinement.

**Delivers:**
- Calendar widget showing current month
- Click date to navigate to daily note
- Daily notes auto-created with date title
- Date-based navigation (prev/next day)

**Requirements:**
- REQ-013: Calendar widget with date navigation
- REQ-014: Daily notes (auto-created for today)

**Key Patterns:**
- shadcn/ui calendar component
- Daily note template (configurable later)
- Date-based note lookup (special folder or naming convention)

**Pitfalls to Avoid:**
- Timezone issues (use local date consistently)
- Creating duplicate daily notes

**Acceptance:**
- Calendar displays in sidebar or dedicated panel
- Clicking date opens/creates daily note for that date
- Today's note easily accessible
- Can navigate between days

---

## Phase 5: Chat Integration

**Goal:** Connect to Clara backend for AI conversations. HTTP-based, mostly frontend work.

**Delivers:**
- Chat panel (sidebar or split view)
- Message input with send button
- Message history display
- Streaming response rendering
- Connection to existing Clara backend

**Requirements:**
- REQ-015: Chat panel connected to Clara backend
- REQ-016: Message history with streaming responses

**Key Patterns:**
- Tauri HTTP plugin for API calls
- Server-sent events (SSE) for streaming
- TanStack Query for message caching
- Zustand for chat UI state

**Pitfalls to Avoid:**
- Missing capability permissions for HTTP
- Not handling connection errors gracefully
- Blocking UI during streaming

**Acceptance:**
- Can send message to Clara and receive response
- Responses stream in real-time
- Message history persists across sessions
- Errors displayed gracefully

---

## Phase 6: Clara Note Tools

**Goal:** Final integration layer. Clara becomes co-author with full note access.

**Research Flag:** API design for note operations needs coordination with existing Clara backend.

**Delivers:**
- Clara can search and read notes
- Clara can create new notes
- Clara can edit existing notes
- "Save this as a note" action from conversation
- Attribution toggle (see who wrote what)

**Requirements:**
- REQ-017: Clara can read notes
- REQ-018: Clara can create notes
- REQ-019: Clara can edit existing notes
- REQ-020: Save conversation as note
- REQ-021: Attribution toggle

**Key Patterns:**
- Note tools exposed as API endpoints (or direct IPC if local)
- Author field on notes/edits (user vs clara)
- UI indicator for Clara-authored content

**Pitfalls to Avoid:**
- Clara edits overwriting user changes (conflict handling)
- Missing attribution on Clara-created content
- Tool permissions too broad

**Acceptance:**
- Can ask Clara "what notes do I have about X"
- Can ask Clara to create a note
- Can ask Clara to update a note
- "Save as note" button in chat
- Can toggle to see Clara vs user authorship

---

## Parallelization

```
Phase 1 (Foundation)
    |
    v
Phase 2 (Core Notes)
    |
    +------------------+
    v                  v
Phase 3 (Wiki/Search)  Phase 4 (Calendar)
    |                  |
    +------------------+
            |
            v
      Phase 5 (Chat)
            |
            v
      Phase 6 (Clara Tools)
```

Phases 3 and 4 can run in parallel after Phase 2 is complete.

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Custom TipTap wiki-link extension | Phase 3 delay | Research early, allow iteration |
| Clara backend API changes needed | Phase 6 delay | Coordinate API design before Phase 6 |
| Cross-platform WebView variance | All phases | Test macOS/Windows/Linux, CI early |
| IPC performance with large notes | Phase 2+ | Batch operations, pagination patterns |

---
*Generated: 2026-01-23*
*Source: .planning/REQUIREMENTS.md, .planning/research/SUMMARY.md*
