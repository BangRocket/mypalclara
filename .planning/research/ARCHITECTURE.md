# Architecture Research: MyPalClara Desktop UI

**Domain:** Desktop note-taking app with AI integration
**Researched:** 2026-01-23
**Confidence:** HIGH (verified via official Tauri v2 docs, Context7-equivalent official sources)

## Executive Summary

Tauri v2 + React + TypeScript is a well-established pattern with clear architectural guidance. The key insight: **Rust owns data and security, React owns UI and user interaction, IPC bridges them via commands and events.**

For MyPalClara Desktop, the architecture separates:
1. **Rust backend** - SQLite access, file operations, security-sensitive work
2. **React frontend** - UI rendering, state management, user interaction
3. **IPC layer** - Type-safe commands (React calls Rust) and events (Rust notifies React)

## Project Structure

### Recommended Layout

```
/webui/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── index.html
├── src/                          # React frontend
│   ├── main.tsx                  # App entry point
│   ├── App.tsx                   # Root component
│   ├── bindings.ts               # Auto-generated Tauri command bindings
│   ├── components/               # Shared UI components
│   │   ├── ui/                   # Base components (buttons, inputs, etc.)
│   │   ├── layout/               # Layout components (sidebar, panels)
│   │   └── common/               # Shared feature components
│   ├── features/                 # Feature-based modules
│   │   ├── notes/
│   │   │   ├── components/       # Note-specific components
│   │   │   ├── hooks/            # Note-related hooks
│   │   │   ├── stores/           # Note state (Zustand)
│   │   │   └── types.ts          # Note types
│   │   ├── chat/
│   │   │   ├── components/
│   │   │   ├── hooks/
│   │   │   └── api.ts            # Chat API calls
│   │   ├── search/
│   │   │   ├── components/
│   │   │   └── hooks/
│   │   ├── calendar/
│   │   │   ├── components/
│   │   │   ├── hooks/
│   │   │   └── stores/
│   │   └── folders/
│   │       ├── components/
│   │       └── hooks/
│   ├── stores/                   # Global Zustand stores
│   │   ├── ui.ts                 # UI state (sidebar collapsed, theme)
│   │   └── settings.ts           # App settings
│   ├── hooks/                    # Shared hooks
│   │   └── useTheme.ts
│   ├── lib/                      # Utilities
│   │   ├── markdown.ts           # Markdown parsing utilities
│   │   └── wikilinks.ts          # Wiki link parsing/rendering
│   └── styles/                   # Global styles
│       └── index.css
├── src-tauri/                    # Rust backend
│   ├── Cargo.toml
│   ├── Cargo.lock
│   ├── build.rs
│   ├── tauri.conf.json           # Tauri configuration
│   ├── capabilities/
│   │   └── default.json          # Permission capabilities
│   ├── icons/                    # App icons
│   └── src/
│       ├── main.rs               # Desktop entry (minimal)
│       ├── lib.rs                # Main app logic, plugin registration
│       ├── commands/             # Tauri commands (IPC handlers)
│       │   ├── mod.rs
│       │   ├── notes.rs          # Note CRUD commands
│       │   ├── search.rs         # FTS5 search commands
│       │   ├── folders.rs        # Folder management
│       │   └── sync.rs           # External API sync
│       ├── db/                   # Database layer
│       │   ├── mod.rs
│       │   ├── schema.rs         # SQLite schema definitions
│       │   ├── migrations.rs     # Migration definitions
│       │   └── queries.rs        # Query helpers
│       ├── models/               # Data models
│       │   ├── mod.rs
│       │   ├── note.rs
│       │   └── folder.rs
│       └── services/             # Business logic
│           ├── mod.rs
│           ├── wikilinks.rs      # Wiki link parsing/backlink calculation
│           └── fts.rs            # Full-text search indexing
└── migrations/                   # SQL migration files
    ├── 001_initial_schema.sql
    └── 002_fts_tables.sql
```

### Key Principles

1. **Feature-based organization** - Group by feature (notes, chat, calendar), not by type
2. **Rust owns data** - All SQLite operations go through Rust commands
3. **React owns UI** - Frontend never touches files or databases directly
4. **Clear IPC boundary** - TypeScript bindings generated from Rust types

## Tauri <-> React Communication

### IPC Pattern Overview

Tauri uses **Asynchronous Message Passing** - processes exchange serialized requests/responses. This is safer than shared memory or FFI.

| Mechanism | Direction | Use Case |
|-----------|-----------|----------|
| Commands | Frontend -> Rust | Data fetching, CRUD, file ops |
| Events | Bidirectional | Notifications, state updates, streaming |
| Channels | Rust -> Frontend | High-throughput streaming |

### Commands (Primary Pattern)

Commands are Rust functions invoked from React via `invoke()`.

**Rust side (`src-tauri/src/commands/notes.rs`):**

```rust
use serde::{Deserialize, Serialize};
use tauri::State;
use crate::db::Database;

#[derive(Serialize, Deserialize)]
pub struct Note {
    pub id: i64,
    pub title: String,
    pub content: String,
    pub folder_id: Option<i64>,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Deserialize)]
pub struct CreateNoteInput {
    pub title: String,
    pub content: String,
    pub folder_id: Option<i64>,
}

#[tauri::command]
pub async fn get_note(
    db: State<'_, Database>,
    id: i64
) -> Result<Note, String> {
    db.get_note(id)
        .await
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn create_note(
    db: State<'_, Database>,
    input: CreateNoteInput
) -> Result<Note, String> {
    db.create_note(input)
        .await
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn update_note(
    db: State<'_, Database>,
    id: i64,
    title: String,
    content: String
) -> Result<Note, String> {
    db.update_note(id, &title, &content)
        .await
        .map_err(|e| e.to_string())
}
```

**Registration (`src-tauri/src/lib.rs`):**

```rust
mod commands;
mod db;

use commands::notes;
use db::Database;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_sql::Builder::default().build())
        .manage(Database::new().expect("Failed to initialize database"))
        .invoke_handler(tauri::generate_handler![
            notes::get_note,
            notes::create_note,
            notes::update_note,
            notes::delete_note,
            notes::list_notes,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application")
}
```

**React side:**

```typescript
import { invoke } from '@tauri-apps/api/core';

interface Note {
  id: number;
  title: string;
  content: string;
  folder_id: number | null;
  created_at: string;
  updated_at: string;
}

// Fetch a note
const note = await invoke<Note>('get_note', { id: 123 });

// Create a note
const newNote = await invoke<Note>('create_note', {
  input: { title: 'My Note', content: '# Hello', folder_id: null }
});
```

### Type-Safe Bindings with tauri-specta

**Recommendation:** Use [tauri-specta](https://github.com/specta-rs/tauri-specta) for compile-time type safety.

**Setup (`Cargo.toml`):**

```toml
[dependencies]
tauri-specta = { version = "2", features = ["derive", "typescript"] }
specta = { version = "2", features = ["derive"] }
```

**Usage:**

```rust
use specta::Type;
use tauri_specta::{collect_commands, Builder};

#[derive(Serialize, Deserialize, Type)]
pub struct Note { /* ... */ }

#[tauri::command]
#[specta::specta]
pub async fn get_note(id: i64) -> Result<Note, String> { /* ... */ }

// In lib.rs
let builder = Builder::<tauri::Wry>::new()
    .commands(collect_commands![get_note, create_note, update_note]);

#[cfg(debug_assertions)]
builder.export(specta_typescript::Typescript::default(), "../src/bindings.ts")
    .expect("Failed to export bindings");
```

This generates `bindings.ts` with fully typed functions:

```typescript
// Auto-generated - do not edit
export async function getNote(id: number): Promise<Note> {
  return await invoke('get_note', { id });
}
```

### Events (Rust -> React Notifications)

Use events for notifying the frontend of changes (e.g., background sync completed).

**Rust side:**

```rust
use tauri::{AppHandle, Emitter};

#[tauri::command]
pub async fn sync_with_backend(app: AppHandle) -> Result<(), String> {
    // ... sync logic ...

    // Notify frontend
    app.emit("sync-completed", SyncResult { notes_updated: 5 })
        .map_err(|e| e.to_string())?;

    Ok(())
}
```

**React side:**

```typescript
import { listen, UnlistenFn } from '@tauri-apps/api/event';
import { useEffect } from 'react';

function useSyncEvents() {
  useEffect(() => {
    let unlisten: UnlistenFn;

    listen<{ notes_updated: number }>('sync-completed', (event) => {
      console.log(`Synced ${event.payload.notes_updated} notes`);
    }).then(fn => { unlisten = fn; });

    return () => { unlisten?.(); };
  }, []);
}
```

### Channels (High-Throughput Streaming)

For streaming large data (search results, exports), use Channels.

```rust
use tauri::ipc::Channel;

#[derive(Serialize, Clone)]
pub enum SearchEvent {
    Result { note: Note },
    Complete { total: usize },
}

#[tauri::command]
pub async fn search_notes(
    db: State<'_, Database>,
    query: String,
    on_event: Channel<SearchEvent>
) -> Result<(), String> {
    let results = db.search(&query).await?;

    for note in results.iter() {
        on_event.send(SearchEvent::Result { note: note.clone() })
            .map_err(|e| e.to_string())?;
    }

    on_event.send(SearchEvent::Complete { total: results.len() })
        .map_err(|e| e.to_string())?;

    Ok(())
}
```

## Data Layer

### SQLite Access from Rust

**Recommended approach:** Use the official [tauri-plugin-sql](https://v2.tauri.app/plugin/sql/) with SQLx for migrations, but wrap in custom Rust commands for business logic.

**Why custom commands over direct plugin access:**
1. Wiki link parsing happens in Rust on save
2. Backlinks computed in Rust, not frontend
3. FTS5 indexing is Rust-managed
4. Type safety via tauri-specta

### Database Schema

```sql
-- migrations/001_initial_schema.sql

-- Folders for organization
CREATE TABLE folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    parent_id INTEGER REFERENCES folders(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Notes with markdown content
CREATE TABLE notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    folder_id INTEGER REFERENCES folders(id) ON DELETE SET NULL,
    author TEXT NOT NULL DEFAULT 'user',  -- 'user' or 'clara'
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Wiki links (computed on save)
CREATE TABLE wiki_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    target_note_id INTEGER REFERENCES notes(id) ON DELETE CASCADE,
    target_title TEXT NOT NULL,  -- Store title for unresolved links
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Calendar events
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    date TEXT NOT NULL,  -- ISO date
    all_day INTEGER NOT NULL DEFAULT 1,
    start_time TEXT,
    end_time TEXT,
    note_id INTEGER REFERENCES notes(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indexes
CREATE INDEX idx_notes_folder ON notes(folder_id);
CREATE INDEX idx_notes_updated ON notes(updated_at DESC);
CREATE INDEX idx_wiki_links_source ON wiki_links(source_note_id);
CREATE INDEX idx_wiki_links_target ON wiki_links(target_note_id);
CREATE INDEX idx_events_date ON events(date);
```

### FTS5 Full-Text Search

```sql
-- migrations/002_fts_tables.sql

-- FTS5 virtual table for search
CREATE VIRTUAL TABLE notes_fts USING fts5(
    title,
    content,
    content='notes',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER notes_ai AFTER INSERT ON notes BEGIN
    INSERT INTO notes_fts(rowid, title, content)
    VALUES (new.id, new.title, new.content);
END;

CREATE TRIGGER notes_ad AFTER DELETE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, title, content)
    VALUES('delete', old.id, old.title, old.content);
END;

CREATE TRIGGER notes_au AFTER UPDATE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, title, content)
    VALUES('delete', old.id, old.title, old.content);
    INSERT INTO notes_fts(rowid, title, content)
    VALUES (new.id, new.title, new.content);
END;
```

**Search command:**

```rust
#[derive(Serialize)]
pub struct SearchResult {
    pub id: i64,
    pub title: String,
    pub snippet: String,  // Highlighted match
    pub score: f64,
}

#[tauri::command]
pub async fn search_notes(
    db: State<'_, Database>,
    query: String
) -> Result<Vec<SearchResult>, String> {
    // Use FTS5 with BM25 ranking
    let sql = r#"
        SELECT
            n.id,
            n.title,
            snippet(notes_fts, 1, '<mark>', '</mark>', '...', 32) as snippet,
            bm25(notes_fts) as score
        FROM notes_fts
        JOIN notes n ON n.id = notes_fts.rowid
        WHERE notes_fts MATCH ?
        ORDER BY score
        LIMIT 50
    "#;

    db.query(sql, &[&query])
        .await
        .map_err(|e| e.to_string())
}
```

### Wiki Link Processing

Wiki links are parsed on note save, not on render:

```rust
// src-tauri/src/services/wikilinks.rs

use regex::Regex;
use lazy_static::lazy_static;

lazy_static! {
    static ref WIKI_LINK_RE: Regex = Regex::new(r"\[\[([^\]]+)\]\]").unwrap();
}

pub fn extract_wiki_links(content: &str) -> Vec<String> {
    WIKI_LINK_RE
        .captures_iter(content)
        .map(|cap| cap[1].to_string())
        .collect()
}

#[tauri::command]
pub async fn save_note(
    db: State<'_, Database>,
    id: i64,
    title: String,
    content: String
) -> Result<Note, String> {
    // 1. Update note content
    let note = db.update_note(id, &title, &content).await?;

    // 2. Extract wiki links
    let links = extract_wiki_links(&content);

    // 3. Clear existing links for this note
    db.delete_links_from(id).await?;

    // 4. Insert new links
    for link_title in links {
        let target_id = db.find_note_by_title(&link_title).await?;
        db.insert_link(id, target_id, &link_title).await?;
    }

    Ok(note)
}

#[tauri::command]
pub async fn get_backlinks(
    db: State<'_, Database>,
    note_id: i64
) -> Result<Vec<Note>, String> {
    db.get_notes_linking_to(note_id).await.map_err(|e| e.to_string())
}
```

### Database Initialization

```rust
// src-tauri/src/db/mod.rs

use sqlx::{sqlite::SqlitePoolOptions, SqlitePool};
use tauri::AppHandle;
use std::path::PathBuf;

pub struct Database {
    pool: SqlitePool,
}

impl Database {
    pub async fn new(app: &AppHandle) -> Result<Self, Box<dyn std::error::Error>> {
        let app_dir = app.path().app_data_dir()?;
        std::fs::create_dir_all(&app_dir)?;

        let db_path = app_dir.join("notes.db");
        let db_url = format!("sqlite:{}?mode=rwc", db_path.display());

        let pool = SqlitePoolOptions::new()
            .max_connections(5)
            .connect(&db_url)
            .await?;

        // Run migrations
        sqlx::migrate!("../migrations")
            .run(&pool)
            .await?;

        Ok(Self { pool })
    }
}
```

## State Management

### Three-Layer Pattern

| Layer | Tool | Owns | Example |
|-------|------|------|---------|
| Component | `useState` | Local UI state | Form inputs, open/closed |
| Global UI | Zustand | App-wide UI concerns | Sidebar collapsed, theme, selected note |
| Persistent | TanStack Query | Data from Rust/API | Notes, folders, search results |

### Zustand for UI State

```typescript
// src/stores/ui.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UIState {
  sidebarCollapsed: boolean;
  selectedNoteId: number | null;
  theme: 'light' | 'dark' | 'system';

  toggleSidebar: () => void;
  selectNote: (id: number | null) => void;
  setTheme: (theme: 'light' | 'dark' | 'system') => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      selectedNoteId: null,
      theme: 'system',

      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      selectNote: (id) => set({ selectedNoteId: id }),
      setTheme: (theme) => set({ theme }),
    }),
    { name: 'clara-ui' }
  )
);
```

### TanStack Query for Data

```typescript
// src/features/notes/hooks/useNotes.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { invoke } from '@tauri-apps/api/core';
import type { Note, CreateNoteInput } from '../types';

export function useNotes(folderId?: number) {
  return useQuery({
    queryKey: ['notes', { folderId }],
    queryFn: () => invoke<Note[]>('list_notes', { folderId }),
  });
}

export function useNote(id: number) {
  return useQuery({
    queryKey: ['notes', id],
    queryFn: () => invoke<Note>('get_note', { id }),
    enabled: !!id,
  });
}

export function useCreateNote() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: CreateNoteInput) =>
      invoke<Note>('create_note', { input }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notes'] });
    },
  });
}

export function useUpdateNote() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, title, content }: { id: number; title: string; content: string }) =>
      invoke<Note>('update_note', { id, title, content }),
    onSuccess: (note) => {
      queryClient.setQueryData(['notes', note.id], note);
      queryClient.invalidateQueries({ queryKey: ['notes'] });
    },
  });
}
```

### Autosave Pattern

```typescript
// src/features/notes/hooks/useAutosave.ts
import { useEffect, useRef } from 'react';
import { useDebouncedCallback } from 'use-debounce';
import { useUpdateNote } from './useNotes';

export function useAutosave(noteId: number, title: string, content: string) {
  const { mutate: updateNote } = useUpdateNote();
  const savedRef = useRef({ title, content });

  const debouncedSave = useDebouncedCallback(
    (id: number, t: string, c: string) => {
      if (t !== savedRef.current.title || c !== savedRef.current.content) {
        updateNote({ id, title: t, content: c });
        savedRef.current = { title: t, content: c };
      }
    },
    1000 // 1 second debounce
  );

  useEffect(() => {
    debouncedSave(noteId, title, content);
  }, [noteId, title, content, debouncedSave]);
}
```

## External API Communication

### Chat with Clara Backend

For the chat panel connecting to Clara's existing backend:

**Permissions (`capabilities/default.json`):**

```json
{
  "permissions": [
    "core:default",
    "sql:default",
    {
      "identifier": "http:default",
      "allow": [
        { "url": "https://your-clara-api.railway.app/*" },
        { "url": "http://localhost:8000/*" }
      ]
    }
  ]
}
```

**React hook:**

```typescript
// src/features/chat/hooks/useChat.ts
import { fetch } from '@tauri-apps/plugin-http';
import { useMutation, useQueryClient } from '@tanstack/react-query';

const API_URL = import.meta.env.VITE_CLARA_API_URL;

export function useSendMessage() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (message: string) => {
      const response = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
      });

      if (!response.ok) throw new Error('Chat request failed');
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chat-history'] });
    },
  });
}
```

## Build Order

### Phase Dependencies

```
Phase 1: Foundation (no dependencies)
├── Tauri project scaffold
├── SQLite schema + migrations
├── Basic Rust commands (CRUD)
└── React app shell

Phase 2: Core Features (depends on Phase 1)
├── Notes CRUD UI
├── Markdown editor integration
├── Folder tree component
└── TanStack Query setup

Phase 3: Search & Links (depends on Phase 2)
├── FTS5 implementation
├── Wiki link parsing (Rust)
├── Backlinks UI
└── Search UI

Phase 4: Chat & Calendar (depends on Phase 2)
├── Chat panel (HTTP to Clara)
├── Calendar view
├── Daily notes
└── Event CRUD

Phase 5: Clara Integration (depends on Phase 3, 4)
├── Clara can read notes (API endpoint)
├── Clara can write notes (attribution)
├── Attribution toggle UI
└── Export functionality
```

### Recommended Implementation Order

| Order | Component | Why First |
|-------|-----------|-----------|
| 1 | Tauri scaffold + SQLite | Everything else depends on data layer |
| 2 | Notes CRUD commands | Core feature, validates IPC pattern |
| 3 | Folder tree | Navigation structure for all other features |
| 4 | Markdown editor | Primary user interaction |
| 5 | Autosave | Quality of life, prevents data loss |
| 6 | Wiki link parsing | Must be in place before backlinks |
| 7 | FTS5 search | High value, can be parallelized with editor work |
| 8 | Chat panel | Mostly independent, HTTP-based |
| 9 | Calendar | Independent feature |
| 10 | Clara API integration | Requires backend changes, save for last |

## Anti-Patterns to Avoid

### 1. Direct SQLite from Frontend

**Bad:** Using tauri-plugin-sql directly from React for all queries.

**Why bad:**
- Business logic leaks into frontend
- Wiki link parsing would need JS implementation
- No type safety
- Harder to test

**Instead:** Wrap in Rust commands with business logic in Rust.

### 2. Synchronous IPC

**Bad:** Blocking on every keystroke.

**Why bad:** UI becomes unresponsive, especially during large operations.

**Instead:** Use debounced autosave, optimistic updates, streaming for search.

### 3. Giant Zustand Stores

**Bad:** Putting all state (UI, notes, folders, chat) in one store.

**Why bad:** Re-renders everything on any change.

**Instead:**
- TanStack Query for server/persistent data
- Zustand only for UI state
- Feature-scoped stores

### 4. Manual TypeScript Types

**Bad:** Hand-writing types that mirror Rust structs.

**Why bad:** Types drift, runtime errors.

**Instead:** Use tauri-specta for generated bindings.

### 5. Storing Markdown in JSON

**Bad:** Storing notes as JSON with markdown as one field, serializing/deserializing constantly.

**Why bad:** Performance overhead, harder to query.

**Instead:** Store markdown directly as TEXT in SQLite.

## Sources

### Official Tauri Documentation
- [Project Structure](https://v2.tauri.app/start/project-structure/)
- [Inter-Process Communication](https://v2.tauri.app/concept/inter-process-communication/)
- [Calling Frontend from Rust](https://v2.tauri.app/develop/calling-frontend/)
- [SQL Plugin](https://v2.tauri.app/plugin/sql/)
- [HTTP Client Plugin](https://v2.tauri.app/plugin/http-client/)

### Type Safety
- [tauri-specta](https://github.com/specta-rs/tauri-specta) - TypeScript bindings from Rust
- [specta.dev](https://specta.dev/docs/tauri-specta/v2) - Official documentation

### State Management
- [Zustand vs TanStack Query patterns](https://www.bugragulculer.com/blog/good-bye-redux-how-react-query-and-zustand-re-wired-state-management-in-25)
- [dannysmith/tauri-template](https://github.com/dannysmith/tauri-template) - Production-ready Tauri + React template

### SQLite & FTS5
- [SQLite FTS5 Extension](https://www.sqlite.org/fts5.html)
- [Tauri SQLite integration guide](https://dezoito.github.io/2025/01/01/embedding-sqlite-in-a-tauri-application.html)

### Build Patterns
- [RandomEngy/tauri-sqlite](https://github.com/RandomEngy/tauri-sqlite) - Minimal SQLite example
- [Tauri tutorials](https://tauritutorials.com/blog/building-a-todo-app-in-tauri-with-sqlite-and-sqlx)
