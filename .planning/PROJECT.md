# MyPalClara

## What This Is

MyPalClara is a personal AI assistant with persistent memory, currently accessed via Discord. This milestone adds a desktop UI — a shared knowledge platform where Clara and the user collaborate on notes, ideas, and conversations in one unified workspace.

## Core Value

A seamless collaborative space where human and AI knowledge blend together — Clara reads, writes, and references notes alongside the user, making the knowledge base truly shared.

## Current Milestone: v1.0 MyPalClara Desktop UI

**Goal:** Build a Tauri + React desktop app that serves as the primary interface for Clara, combining chat and collaborative knowledge management.

**Target features:**
- Desktop chat interface connected to Clara's backend
- Notes with markdown editor, folders, autosave
- Wiki-style linking with backlinks
- Full-text search across notes
- Calendar with daily notes and events
- Clara can read, create, and edit notes
- Attribution toggle (see who wrote what)

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Desktop app shell (Tauri + React + TypeScript)
- [ ] Notes CRUD with markdown editor
- [ ] Folder organization with sidebar navigation
- [ ] Clara chat panel integrated into UI
- [ ] Wiki links and backlinks
- [ ] Full-text search (SQLite FTS5)
- [ ] Calendar view with daily notes
- [ ] Clara can create/read/edit notes
- [ ] Export notes as markdown files
- [ ] Attribution toggle for Clara vs user content

### Out of Scope

- Mobile app — desktop-first, mobile later
- Multi-user collaboration — single user + Clara only for v1
- Cloud sync — local SQLite only, export for backup
- Real-time collaboration — not needed for single user + AI

## Context

**Starting point:** Grafnote (github.com/ily123/grafnote) as UI reference — an Evernote clone with Obsidian styling. Completely rewritten with modern stack.

**Existing infrastructure:**
- Clara backend: mem0 for memory, PostgreSQL for sessions/messages
- Discord bot: Current primary interface
- FastAPI services: OAuth, monitoring dashboards

**Technical approach:**
- Tauri for desktop shell (~5MB binary vs Electron's ~150MB)
- React + TypeScript for frontend
- SQLite for local note storage (markdown as text blobs)
- Connects to existing Clara backend via API

## Constraints

- **Stack**: Tauri + React + TypeScript + SQLite (decided)
- **Location**: `/webui/` directory in existing repo
- **Integration**: Must connect to existing Clara backend, not standalone

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Tauri over Electron | Smaller binary (~5MB vs ~150MB), Rust performance, modern | — Pending |
| SQLite with markdown blobs | Local-first, portable, exportable to files | — Pending |
| Shared knowledge model | Clara is co-author, not just assistant | — Pending |

---
*Last updated: 2026-01-23 after milestone v1.0 initialization*
