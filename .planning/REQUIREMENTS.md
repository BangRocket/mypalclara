# Requirements: v1.0 MyPalClara Desktop UI

## Overview

This document defines the scoped requirements for v1.0. Features are categorized by priority and mapped to implementation phases.

## Must Have (Table Stakes)

These are non-negotiable for v1.0 - users expect these from any note-taking app.

| ID | Requirement | Phase |
|----|-------------|-------|
| REQ-001 | Desktop app shell (Tauri + React + TypeScript) | 1 |
| REQ-002 | SQLite database with migrations | 1 |
| REQ-003 | Type-safe IPC between Rust and React | 1 |
| REQ-004 | Notes CRUD (create, read, update, delete) | 2 |
| REQ-005 | Markdown editor with live preview (TipTap) | 2 |
| REQ-006 | Folder/hierarchy organization | 2 |
| REQ-007 | Sidebar navigation with folder tree | 2 |
| REQ-008 | Auto-save with debounced persistence | 2 |
| REQ-009 | [[Wiki-links]] with autocomplete on `[[` | 3 |
| REQ-010 | Backlinks panel showing bidirectional connections | 3 |
| REQ-011 | Full-text search (SQLite FTS5) | 3 |
| REQ-012 | Quick switcher (Cmd+P) for note navigation | 3 |
| REQ-013 | Calendar widget with date navigation | 4 |
| REQ-014 | Daily notes (auto-created for today) | 4 |
| REQ-015 | Chat panel connected to Clara backend | 5 |
| REQ-016 | Message history with streaming responses | 5 |

## Should Have (Competitive Differentiators)

These make MyPalClara stand out - the "Clara as co-author" model is the key differentiator.

| ID | Requirement | Phase |
|----|-------------|-------|
| REQ-017 | Clara can read notes (search and retrieve) | 6 |
| REQ-018 | Clara can create notes | 6 |
| REQ-019 | Clara can edit existing notes | 6 |
| REQ-020 | "Save this as a note" from conversation | 6 |
| REQ-021 | Attribution toggle (see who wrote what) | 6 |
| REQ-022 | Export notes as markdown files | 2 |
| REQ-023 | Unlinked mentions detection | 3 |
| REQ-024 | Link preview on hover | 3 |

## Out of Scope (v2+)

Explicitly deferred to keep v1.0 focused and shippable.

| Feature | Rationale |
|---------|-----------|
| Graph view | Nice-to-have visualization, not core functionality |
| AI-suggested links | Requires entity extraction, complex ML |
| Conversation-to-note synthesis | Advanced AI integration |
| Notes sync with mem0 | Bidirectional sync is complex |
| Cross-reference discovery | Semantic similarity requires embeddings |
| Mobile app | Desktop-first, mobile later |
| Multi-user collaboration | Single user + Clara only for v1 |
| Cloud sync | Local SQLite only, export for backup |
| Real-time collaboration | Not needed for single user + AI |
| Calendar event CRUD | Calendar is for navigation, not full PIM |

## Phase Mapping

### Phase 1: Foundation
**Goal:** Establish data layer and IPC patterns correctly to avoid rewrites.
- REQ-001: Desktop app shell
- REQ-002: SQLite with migrations
- REQ-003: Type-safe IPC (tauri-specta)

### Phase 2: Core Notes
**Goal:** Primary user interaction must feel solid before adding complexity.
- REQ-004: Notes CRUD
- REQ-005: Markdown editor
- REQ-006: Folder organization
- REQ-007: Sidebar navigation
- REQ-008: Auto-save
- REQ-022: Export to markdown

### Phase 3: Wiki Links & Search
**Goal:** Link index is central dependency for backlinks and search.
- REQ-009: Wiki-links with autocomplete
- REQ-010: Backlinks panel
- REQ-011: FTS5 search
- REQ-012: Quick switcher
- REQ-023: Unlinked mentions
- REQ-024: Link preview

### Phase 4: Calendar & Daily Notes
**Goal:** Independent feature, can develop in parallel with Phase 3 refinement.
- REQ-013: Calendar widget
- REQ-014: Daily notes

### Phase 5: Chat Integration
**Goal:** HTTP-based, mostly frontend work. Requires stable local features first.
- REQ-015: Chat panel
- REQ-016: Message history + streaming

### Phase 6: Clara Note Tools
**Goal:** Final integration layer - Clara needs stable note system.
- REQ-017: Clara read notes
- REQ-018: Clara create notes
- REQ-019: Clara edit notes
- REQ-020: Save conversation as note
- REQ-021: Attribution toggle

## Success Criteria

v1.0 is complete when:
1. User can create, edit, organize, and search notes locally
2. Wiki-links work with autocomplete and backlinks
3. Clara can be chatted with from the desktop app
4. Clara can read, create, and edit notes
5. User can see who authored what (attribution)
6. Notes can be exported as markdown files

## Dependencies

| Phase | Depends On | Rationale |
|-------|------------|-----------|
| 2 | 1 | Notes need database and IPC |
| 3 | 2 | Links operate on note content |
| 4 | 2 | Daily notes use notes table |
| 5 | 1 | Chat needs HTTP capability configured |
| 6 | 2, 5 | Clara tools need notes + chat |

## Technical Constraints

From research findings:
- Use WAL mode for SQLite (concurrent reads during writes)
- Batch IPC operations (JSON serialization overhead)
- FTS5 sync via SQLite triggers (not application logic)
- Debounce autosave at 1-2 seconds (not 200ms)
- Test release builds early (capability permissions)

---
*Generated: 2026-01-23*
*Source: .planning/research/SUMMARY.md*
