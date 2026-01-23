# Feature Landscape: MyPalClara Desktop UI

**Domain:** Personal knowledge management / AI-collaborative note-taking
**Researched:** 2026-01-23
**Confidence:** HIGH (extensive market research, established patterns)

## Executive Summary

The note-taking app landscape is mature with clear user expectations. Table stakes are well-defined by Obsidian, Notion, and Evernote. The differentiator for MyPalClara Desktop is the **AI co-author model** where Clara is not just an assistant that answers questions about notes, but an active participant who can create, edit, and reference the shared knowledge base.

The key insight: most "AI note apps" treat AI as a feature (summarize this, search that). MyPalClara treats Clara as a **collaborator** with equal access to the knowledge base.

---

## Table Stakes

Features users expect from any modern note-taking app. Missing these makes the product feel incomplete or amateur.

### Core Note Operations

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Create/Edit/Delete notes** | Fundamental CRUD | Low | Must be instant, no lag |
| **Markdown support** | Industry standard for power users | Medium | CommonMark + GFM tables/checkboxes minimum |
| **Live preview / WYSIWYG toggle** | Users expect to see formatting as they type | Medium | Split-pane or inline preview |
| **Auto-save** | Losing work is unacceptable | Low | Save on every keystroke, debounced |
| **Folder/hierarchy organization** | Mental model users bring from filesystems | Low | Tree structure, drag-drop |
| **Quick note creation** | Capture ideas without friction | Low | Keyboard shortcut, empty state |

### Wiki-Style Linking (Critical for this app)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **[[wiki-links]]** | Core feature for knowledge bases | Medium | Autocomplete on `[[` typed |
| **Backlinks panel** | "What links to this?" is expected | Medium | Show bidirectional connections |
| **Unlinked mentions** | Find references that aren't links yet | Medium | Text search for note title |
| **Link preview on hover** | Quick peek without navigation | Medium | Popup with note excerpt |
| **Broken link detection** | Users need to know when links break | Low | Visual indicator for missing targets |

### Search & Navigation

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Full-text search** | Must find content across all notes | Medium | SQLite FTS5 recommended |
| **Quick switcher** | Cmd+P / Ctrl+P to jump to any note | Low | Fuzzy search by title |
| **Recent notes** | Quick access to recent work | Low | Track last 10-20 opened |
| **Search highlighting** | Show where matches are | Low | Highlight in results and in-note |

### Data Ownership & Storage

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Local-first storage** | Users own their data | Low | SQLite or plain files |
| **Offline capability** | Must work without internet | Low | No cloud dependency for core |
| **Export (Markdown/JSON)** | No vendor lock-in | Low | Standard formats |
| **Import from other apps** | Migration path matters | Medium | At minimum: plain markdown import |

### Editor Quality

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Syntax highlighting in code blocks** | Developers expect this | Medium | Use Prism or highlight.js |
| **Undo/Redo** | Basic editing | Low | Built into most editors |
| **Find & Replace** | Standard editing feature | Low | In-note search |
| **Keyboard shortcuts** | Power users expect efficiency | Low | Standard conventions |

---

## Differentiators

What makes MyPalClara Desktop special. These are not expected but highly valued, and define the product's unique value proposition.

### Clara as Co-Author (Primary Differentiator)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Clara can read any note** | AI has full context of knowledge base | Medium | Tool: `read_note(title)` |
| **Clara can create notes** | AI proactively captures knowledge | Medium | Tool: `create_note(title, content)` |
| **Clara can edit notes** | AI can update/append information | Medium | Tool: `edit_note(title, changes)` |
| **Clara can search notes** | AI can find relevant context | Low | Tool: `search_notes(query)` |
| **Clara remembers note context** | Reference past conversations about notes | High | Integrate with mem0 |
| **"Save this as a note"** | Quick capture from conversation | Low | User command, Clara executes |

### Proactive AI Features

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **AI-suggested links** | "You mentioned X, link to [[X]]?" | High | Requires NLP entity extraction |
| **Conversation-to-note synthesis** | Clara creates notes from chat history | Medium | Summarization tool |
| **Note completion suggestions** | AI suggests what to add to incomplete notes | High | Context-aware generation |
| **Cross-reference discovery** | "These 3 notes are related, want to link them?" | High | Semantic similarity search |

### Daily Notes & Calendar Integration

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Daily note creation** | One-click today's note | Low | Template-based |
| **Calendar widget** | Visual navigation to date-based notes | Medium | Dot indicators for notes |
| **Weekly/Monthly notes** | Periodic review templates | Low | Similar to daily notes |
| **Calendar event display** | See events in daily note | Medium | Google Calendar integration via existing Clara tools |

### Graph View

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Visual graph of connections** | See knowledge structure | High | Force-directed graph, D3.js or similar |
| **Filter by tag/folder** | Focus on subsets | Medium | Dynamic filtering |
| **Hover to preview** | Context without leaving graph | Medium | Tooltip with note excerpt |

### Shared Memory Model

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Notes sync with Clara's mem0** | Facts in notes become Clara's knowledge | High | Two-way sync consideration |
| **Clara cites sources** | "I know this because of [[Note X]]" | Medium | Attribution in responses |
| **User can correct Clara via notes** | Update note = update Clara's knowledge | High | Note changes trigger mem0 updates |

---

## Anti-Features

Things to deliberately NOT build in v1. Common mistakes in this domain.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Real-time collaboration** | Massive complexity, not needed for personal use | Single-user local-first. Defer multi-user entirely. |
| **Cloud sync (v1)** | Adds complexity, privacy concerns, server costs | Local SQLite only. Add sync later if needed. |
| **Mobile app (v1)** | Doubles development effort | Desktop only. Mobile is a separate project. |
| **Database/table views** | Notion-level complexity, scope creep | Plain notes + folders. No structured data views. |
| **Kanban/task management** | Feature creep, already solved by other tools | Keep focus on notes + wiki links. |
| **Handwriting/drawing** | Requires entire canvas system | Text only for v1. |
| **PDF annotation** | Specialized viewer, large scope | Plain text/markdown notes only. |
| **Email integration** | Scope creep | Clara already has email tools separately. |
| **Complex templates** | Over-engineering | Simple daily note template only. |
| **Plugin system** | Maintenance burden, security concerns | Build features in, don't build extensibility. |
| **Custom themes (v1)** | Polish over substance | Light/dark mode only. |
| **Version history** | Nice but not essential for v1 | Auto-save is enough. Add history later. |
| **Transclusion/embeds** | Complex rendering, Obsidian-level feature | Simple [[links]] only. |
| **Mind maps** | Different product category | Graph view is enough. |
| **AI voice input** | Specialized feature, not core | Text input only. |

---

## Complexity Assessment

### Low Complexity (1-2 weeks each)

- Note CRUD operations
- Folder hierarchy
- Quick switcher (Cmd+P)
- Auto-save
- Recent notes
- Export to markdown
- Daily note creation
- Basic keyboard shortcuts
- Light/dark mode

### Medium Complexity (2-4 weeks each)

- Markdown editor with live preview
- [[wiki-links]] with autocomplete
- Backlinks panel
- Full-text search (SQLite FTS5)
- Syntax highlighting in code blocks
- Calendar widget for daily notes
- Clara tools for note operations (read/create/edit/search)
- Import from markdown files/folders

### High Complexity (4-8 weeks each)

- Graph view with force-directed layout
- AI-suggested links (entity extraction)
- Conversation-to-note synthesis
- Notes sync with mem0 (bidirectional)
- Cross-reference discovery (semantic similarity)
- Note completion suggestions

---

## MVP Feature Set Recommendation

For MVP, prioritize Table Stakes + Core Clara Integration:

### Must Have (MVP)
1. Note CRUD with Markdown editor
2. Folder organization
3. [[wiki-links]] with autocomplete
4. Backlinks panel
5. Full-text search
6. Quick switcher
7. Auto-save + local SQLite storage
8. Clara can read/create/edit/search notes (tools)
9. Daily notes with calendar navigation

### Should Have (Post-MVP v1.1)
1. Graph view
2. Unlinked mentions
3. Link preview on hover
4. Export/Import functionality
5. "Save this as a note" from Clara conversation

### Could Have (v2+)
1. AI-suggested links
2. Conversation-to-note synthesis
3. Notes sync with mem0
4. Cross-reference discovery
5. Note completion suggestions

---

## Feature Dependencies

```
Core Editor
    |
    +-- Markdown parsing
    |       |
    |       +-- [[wiki-links]] detection
    |               |
    |               +-- Autocomplete
    |               +-- Backlinks (requires link index)
    |               +-- Unlinked mentions (requires search)
    |               +-- Graph view (requires link index)
    |
    +-- SQLite storage
            |
            +-- FTS5 full-text search
            +-- Quick switcher (uses search)
            +-- Clara note tools (uses storage API)
```

**Key dependency:** The link index is central. Build it early and well, as backlinks, unlinked mentions, and graph view all depend on it.

---

## Sources

### Obsidian/Notion Comparisons
- [Notion vs Obsidian - All Features Compared (2026)](https://productive.io/blog/notion-vs-obsidian/)
- [Notion Vs Obsidian: Side-by-Side Comparison (2026)](https://thebusinessdive.com/notion-vs-obsidian)
- [Zapier: Best Note-Taking Apps 2026](https://zapier.com/blog/best-note-taking-apps/)
- [ProofHub: Obsidian vs Notion](https://www.proofhub.com/articles/obsidian-vs-notion)

### Wiki Links & Backlinks
- [AlternativeTo: Apps with Backlinks feature](https://alternativeto.net/feature/backlinks/)
- [Notenik Community: Back links for wiki links](https://discourse.notenik.app/t/back-links-for-wiki-links-between-collections/263)
- [Wiki.js: Add support for backlinks](https://feedback.js.wiki/wiki/p/add-support-for-backlinks)

### AI Note-Taking
- [Lindy: Best AI Note-Taking Apps 2026](https://www.lindy.ai/blog/ai-note-taking-app)
- [Digital Project Manager: AI Note-Taking Apps 2026](https://thedigitalprojectmanager.com/tools/best-ai-note-taking-apps/)
- [Microsoft: Copilot in OneNote](https://support.microsoft.com/en-us/office/welcome-to-copilot-in-onenote-34b30802-02ae-4676-a88c-82f8d5e586dd)

### Calendar & Daily Notes
- [GitHub: Obsidian Calendar Plugin](https://github.com/liamcain/obsidian-calendar-plugin)
- [Obsidian Help: Daily Notes](https://help.obsidian.md/plugins/daily-notes)
- [GitHub: Obsidian Full Calendar](https://github.com/obsidian-community/obsidian-full-calendar)

### Technical Implementation
- [SQLite FTS5 Extension](https://www.sqlite.org/fts5.html)
- [SQLite Full-Text Search Guide](https://medium.com/@johnidouglasmarangon/full-text-search-in-sqlite-a-practical-guide-80a69c3f42a4)
- [DoltHub: Electron vs Tauri](https://www.dolthub.com/blog/2025-11-13-electron-vs-tauri/)
- [UMLBoard: Tauri Local Data Storage](https://www.umlboard.com/blog/moving-from-electron-to-tauri-2/)

### MVP Development
- [DevTeam.Space: How to make a note-taking app](https://www.devteam.space/blog/how-to-make-a-note-taking-app-like-evernote/)
- [Inkdrop: Note-taking tips](https://www.inkdrop.app/note-taking-tips/)
