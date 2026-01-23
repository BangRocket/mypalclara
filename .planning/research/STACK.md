# Stack Research: MyPalClara Desktop UI

**Project:** Desktop note-taking app with Tauri + React + SQLite
**Researched:** 2026-01-23
**Overall Confidence:** HIGH

## Executive Summary

This document provides prescriptive technology recommendations for building a Tauri 2.x desktop application with React, TypeScript, and SQLite. The stack is well-established with mature tooling, though wiki-link/backlink features require custom implementation.

---

## Core Stack

### Framework: Tauri 2.x

| Component | Version | Source | Confidence |
|-----------|---------|--------|------------|
| Tauri (Rust) | 2.9.5 | [npm registry](https://www.npmjs.com/package/@tauri-apps/cli) | HIGH |
| @tauri-apps/api | 2.9.1 | [npm registry](https://www.npmjs.com/package/@tauri-apps/api) | HIGH |
| @tauri-apps/cli | 2.9.6 | [npm registry](https://www.npmjs.com/package/@tauri-apps/cli) | HIGH |

**Why Tauri over Electron:**
- Minimal bundle size (~600KB vs Electron's ~150MB)
- Uses native OS WebView (no bundled Chromium)
- Better security model with granular permissions
- Rust backend for performance-critical operations
- Mobile support (iOS/Android) in v2

**Minimum Rust:** 1.80+ (required for plugins)

### Frontend: React + TypeScript + Vite

| Component | Version | Source | Confidence |
|-----------|---------|--------|------------|
| Vite | 7.3.1 | [npm registry](https://www.npmjs.com/package/vite) | HIGH |
| React | 19.x | [vite templates](https://vite.dev/guide/) | HIGH |
| TypeScript | 5.x | Bundled with Vite | HIGH |

**Why Vite 7 over older versions:**
- 5x faster full builds, 100x faster incremental builds
- Native TypeScript support
- Hot Module Replacement (HMR) works excellently with Tauri
- First-party React template

**Project Creation:**
```bash
# Method 1: create-tauri-app (recommended)
npm create tauri-app@latest -- --template react-ts

# Method 2: Vite first, then Tauri
npm create vite@latest mypalclara-desktop -- --template react-ts
cd mypalclara-desktop
npm install -D @tauri-apps/cli@latest
npx tauri init
```

---

## Tauri Plugins

All plugins should match the Tauri minor version (2.x.x).

### Required Plugins

| Plugin | Rust Crate | npm Package | Purpose |
|--------|------------|-------------|---------|
| SQL | tauri-plugin-sql | @tauri-apps/plugin-sql | SQLite database access |
| File System | tauri-plugin-fs | @tauri-apps/plugin-fs | Local file read/write |

**Installation:**
```bash
# In src-tauri/
cargo add tauri-plugin-sql --features sqlite
cargo add tauri-plugin-fs

# In project root
npm add @tauri-apps/plugin-sql @tauri-apps/plugin-fs
```

**Plugin Registration (src-tauri/src/main.rs):**
```rust
fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_sql::Builder::default().build())
        .plugin(tauri_plugin_fs::init())
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

### Optional Plugins (Consider for Later)

| Plugin | Purpose | When Needed |
|--------|---------|-------------|
| tauri-plugin-dialog | Native file dialogs | Export/import features |
| tauri-plugin-clipboard-manager | System clipboard | Copy/paste rich content |
| tauri-plugin-shell | Execute system commands | Git integration |
| tauri-plugin-window-state | Remember window size/position | Polish phase |
| tauri-plugin-autostart | Launch on system startup | Power user feature |

---

## Database: SQLite with FTS5

### SQLite Setup via Tauri Plugin

The `tauri-plugin-sql` uses sqlx under the hood with SQLite support.

**JavaScript Usage:**
```typescript
import Database from "@tauri-apps/plugin-sql";

// Path relative to app data directory
const db = await Database.load("sqlite:mypalclara.db");

// Execute queries
await db.execute("CREATE TABLE IF NOT EXISTS notes (...)");
const notes = await db.select<Note[]>("SELECT * FROM notes WHERE folder_id = ?", [folderId]);
```

### FTS5 Full-Text Search Setup

FTS5 is the recommended full-text search extension for SQLite. It provides excellent performance with minimal configuration.

**Schema Design:**
```sql
-- Main notes table
CREATE TABLE notes (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  content TEXT NOT NULL,  -- Markdown stored as text blob
  folder_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- FTS5 virtual table for search
CREATE VIRTUAL TABLE notes_fts USING fts5(
  title,
  content,
  content='notes',
  content_rowid='rowid'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER notes_ai AFTER INSERT ON notes BEGIN
  INSERT INTO notes_fts(rowid, title, content) VALUES (new.rowid, new.title, new.content);
END;

CREATE TRIGGER notes_ad AFTER DELETE ON notes BEGIN
  INSERT INTO notes_fts(notes_fts, rowid, title, content) VALUES('delete', old.rowid, old.title, old.content);
END;

CREATE TRIGGER notes_au AFTER UPDATE ON notes BEGIN
  INSERT INTO notes_fts(notes_fts, rowid, title, content) VALUES('delete', old.rowid, old.title, old.content);
  INSERT INTO notes_fts(rowid, title, content) VALUES (new.rowid, new.title, new.content);
END;
```

**Search Queries:**
```sql
-- Basic search with ranking
SELECT n.*, bm25(notes_fts) as rank
FROM notes_fts
JOIN notes n ON notes_fts.rowid = n.rowid
WHERE notes_fts MATCH 'search terms'
ORDER BY rank;

-- Snippet highlighting
SELECT n.*, snippet(notes_fts, 1, '<mark>', '</mark>', '...', 32) as snippet
FROM notes_fts
JOIN notes n ON notes_fts.rowid = n.rowid
WHERE notes_fts MATCH 'search terms';
```

**Performance Notes:**
- Query time typically <6ms even on large datasets
- Use external content tables (as shown above) for efficient storage
- Consider tokenizer options: `unicode61` (default), `porter` (stemming)

---

## Frontend Libraries

### State Management: Zustand

| Package | Version | Confidence |
|---------|---------|------------|
| zustand | 5.0.10 | HIGH |

**Why Zustand over alternatives:**
- Minimal boilerplate, no providers needed
- Excellent DevTools support
- Perfect for desktop apps with centralized state
- 14M+ weekly downloads, actively maintained
- Same creator as Jotai (Daishi Kato), but better for this use case

**Not Jotai because:** Zustand's centralized store model fits better for app-wide state (notes, folders, settings) vs. Jotai's atomic approach.

**Basic Store Pattern:**
```typescript
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface NotesStore {
  notes: Note[];
  selectedNoteId: string | null;
  setSelectedNote: (id: string | null) => void;
  // ...
}

export const useNotesStore = create<NotesStore>()(
  persist(
    (set) => ({
      notes: [],
      selectedNoteId: null,
      setSelectedNote: (id) => set({ selectedNoteId: id }),
    }),
    { name: 'notes-storage' }
  )
);
```

### Markdown Editor: TipTap

| Package | Version | Purpose | Confidence |
|---------|---------|---------|------------|
| @tiptap/react | 3.15.3 | React bindings | HIGH |
| @tiptap/pm | 3.x | ProseMirror dependencies | HIGH |
| @tiptap/starter-kit | 3.x | Basic extensions bundle | HIGH |
| @tiptap/markdown | 3.x | Markdown serialization | HIGH |
| @tiptap/extension-link | 3.15.3 | Link handling | HIGH |

**Why TipTap:**
- Headless architecture = full UI control
- ProseMirror foundation = battle-tested
- First-party Markdown extension (v3.7.0+)
- Extensible for wiki-link implementation
- Active development, large community

**Not Milkdown because:** TipTap has better React integration and larger ecosystem. Milkdown requires more manual UI work.

**Not @uiw/react-md-editor because:** Too basic for wiki-links/backlinks. Great for simple markdown, but we need rich extensions.

**Installation:**
```bash
npm add @tiptap/react @tiptap/pm @tiptap/starter-kit @tiptap/markdown @tiptap/extension-link @tiptap/extension-placeholder
```

**Basic Setup:**
```typescript
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import { Markdown } from '@tiptap/markdown';
import Link from '@tiptap/extension-link';

const editor = useEditor({
  extensions: [
    StarterKit,
    Markdown.configure({
      transformPastedText: true,
      transformCopiedText: true,
    }),
    Link.configure({
      openOnClick: false,
    }),
  ],
  content: '',
});
```

### Wiki Links / Backlinks: Custom Extension Required

**Important:** TipTap does not have built-in wiki-link (`[[Page Name]]`) support. This requires custom implementation.

**Approach:**
1. Create custom TipTap extension extending Link
2. Use InputRule to detect `[[...]]` syntax
3. Store link relationships in SQLite
4. Query backlinks when viewing a note

**Reference Implementation:** See [GitHub Discussion #5067](https://github.com/ueberdosis/tiptap/discussions/5067) for partial implementation pattern.

**Schema for Backlinks:**
```sql
CREATE TABLE note_links (
  source_note_id TEXT NOT NULL,
  target_note_id TEXT NOT NULL,
  link_text TEXT NOT NULL,
  PRIMARY KEY (source_note_id, target_note_id, link_text),
  FOREIGN KEY (source_note_id) REFERENCES notes(id) ON DELETE CASCADE,
  FOREIGN KEY (target_note_id) REFERENCES notes(id) ON DELETE CASCADE
);

CREATE INDEX idx_note_links_target ON note_links(target_note_id);
```

### UI Components: shadcn/ui

| Technology | Notes | Confidence |
|------------|-------|------------|
| shadcn/ui | Copy-paste components (not versioned) | HIGH |
| Tailwind CSS | 4.0+ | HIGH |
| Radix UI | 1.4.3 (underlying primitives) | HIGH |

**Why shadcn/ui:**
- Full ownership of component code
- Tailwind + Radix = modern + accessible
- No version lock-in (components in your repo)
- Perfect for desktop apps with custom UI needs
- 100k+ GitHub stars, industry standard

**Setup:**
```bash
# Tailwind 4 is auto-configured with Vite plugin
npm add -D tailwindcss @tailwindcss/vite

# Initialize shadcn/ui
npx shadcn@latest init
```

**Essential Components to Install:**
```bash
npx shadcn@latest add button input textarea
npx shadcn@latest add dialog dropdown-menu popover
npx shadcn@latest add sidebar tree  # For folder structure
npx shadcn@latest add calendar      # For calendar view
npx shadcn@latest add command       # For search/command palette
```

### Routing: TanStack Router

| Package | Version | Confidence |
|---------|---------|------------|
| @tanstack/react-router | Latest | HIGH |

**Why TanStack Router over React Router:**
- Superior TypeScript type safety
- Designed for SPAs (perfect for desktop)
- Search parameter handling built-in
- Modern developer experience
- React Router v7's best features require "framework mode" (SSR)

**For a desktop app (SPA), TanStack Router is the better choice.**

```bash
npm add @tanstack/react-router
```

### Data Fetching (for API Connection): TanStack Query

| Package | Version | Confidence |
|---------|---------|------------|
| @tanstack/react-query | 5.x | HIGH |

**Why:** The app connects to an existing backend API. TanStack Query handles:
- Caching API responses
- Background refetching
- Optimistic updates
- Offline handling (with persist plugins)

```bash
npm add @tanstack/react-query
```

---

## Development Tools

### Build & Bundle

| Tool | Purpose | Confidence |
|------|---------|------------|
| Vite 7 | Development server, bundling | HIGH |
| @vitejs/plugin-react-swc | React Fast Refresh with SWC | HIGH |
| @tailwindcss/vite | Tailwind 4 Vite plugin | HIGH |

### Code Quality

| Tool | Purpose | Config |
|------|---------|--------|
| TypeScript | Type checking | `strict: true` in tsconfig.json |
| ESLint | Linting | Use eslint-config-react-app or custom |
| Prettier | Formatting | Integrate with ESLint |

### Testing

| Tool | Purpose | Confidence |
|------|---------|------------|
| Vitest | Unit tests | HIGH |
| @testing-library/react | React component tests | HIGH |
| Playwright | E2E tests (optional) | MEDIUM |
| @tauri-apps/api/mocks | Mock Tauri APIs in tests | HIGH |

**Vitest Setup for Tauri:**
```bash
npm add -D vitest jsdom @testing-library/react
```

Vitest needs `jsdom` environment since there's no browser window in Node.js. Mock Tauri IPC calls using `@tauri-apps/api/mocks`.

---

## Complete Installation Commands

```bash
# Create project
npm create tauri-app@latest mypalclara-desktop -- --template react-ts

cd mypalclara-desktop

# Core dependencies
npm add zustand @tanstack/react-query @tanstack/react-router

# TipTap for markdown editing
npm add @tiptap/react @tiptap/pm @tiptap/starter-kit @tiptap/markdown @tiptap/extension-link @tiptap/extension-placeholder

# Tauri plugins (JavaScript side)
npm add @tauri-apps/plugin-sql @tauri-apps/plugin-fs

# Tailwind 4 + shadcn/ui
npm add -D tailwindcss @tailwindcss/vite
npx shadcn@latest init

# Dev dependencies
npm add -D vitest jsdom @testing-library/react

# In src-tauri/ directory
cd src-tauri
cargo add tauri-plugin-sql --features sqlite
cargo add tauri-plugin-fs
cd ..
```

---

## Not Recommended

### Electron
**Why not:** 150MB+ bundle size vs Tauri's ~600KB. Tauri uses native WebView.

### Redux / Redux Toolkit
**Why not:** Overkill for this app. Zustand provides same benefits with less boilerplate. Redux is better for very large teams or apps with complex state requirements.

### Milkdown
**Why not:** Less mature React integration than TipTap. Requires more manual UI work. TipTap has larger community and better docs.

### React Router v7 (Framework Mode)
**Why not:** Framework mode's features (SSR, data loading) aren't needed for a desktop SPA. TanStack Router provides better type safety for SPAs.

### MobX
**Why not:** More complex than needed. Zustand's simplicity is preferred for this project size.

### Tauri v1
**Why not:** v2 is stable since October 2024, has mobile support, and better plugin architecture. No reason to use v1 for new projects.

### better-sqlite3 / sql.js
**Why not:** The Tauri SQL plugin handles SQLite integration. These are for different contexts (Node.js native / WASM).

### Tailwind CSS v3
**Why not:** v4 is stable (Jan 2025), 5x faster builds, simpler configuration. Only use v3 if you need Safari <16.4 support.

---

## Version Compatibility Matrix

Keep these in sync to avoid issues:

| Tauri Rust | @tauri-apps/api | @tauri-apps/cli | Plugins |
|------------|-----------------|-----------------|---------|
| 2.9.x | 2.9.x | 2.9.x | 2.x.x (exact match) |

**Critical:** Plugin npm packages and Rust crates must have exact same version (e.g., `@tauri-apps/plugin-sql@2.4.5` with `tauri-plugin-sql = "2.4.5"`).

---

## Sources

### Official Documentation
- [Tauri 2.0 Stable Release](https://v2.tauri.app/blog/tauri-20/)
- [Tauri SQL Plugin](https://v2.tauri.app/plugin/sql/)
- [Tauri File System Plugin](https://v2.tauri.app/plugin/file-system/)
- [Tauri Testing Guide](https://v2.tauri.app/develop/tests/)
- [TipTap React Installation](https://tiptap.dev/docs/editor/getting-started/install/react)
- [TipTap Markdown Extension](https://tiptap.dev/docs/editor/markdown)
- [Zustand Documentation](https://zustand.docs.pmnd.rs/)
- [SQLite FTS5 Documentation](https://www.sqlite.org/fts5.html)
- [Tailwind CSS v4.0](https://tailwindcss.com/blog/tailwindcss-v4)
- [shadcn/ui Documentation](https://ui.shadcn.com/)

### npm Registry (Version Verification)
- [@tauri-apps/api](https://www.npmjs.com/package/@tauri-apps/api) - 2.9.1
- [@tiptap/react](https://www.npmjs.com/package/@tiptap/react) - 3.15.3
- [zustand](https://www.npmjs.com/package/zustand) - 5.0.10
- [vite](https://www.npmjs.com/package/vite) - 7.3.1

### Community Resources
- [TipTap Wiki Links Discussion](https://github.com/ueberdosis/tiptap/discussions/5067)
- [Tauri SQLite Example](https://github.com/FocusCookie/tauri-sqlite-example)
- [State Management in 2025](https://dev.to/hijazi313/state-management-in-2025-when-to-use-context-redux-zustand-or-jotai-2d2k)
- [TanStack Router vs React Router](https://medium.com/ekino-france/tanstack-router-vs-react-router-v7-32dddc4fcd58)
