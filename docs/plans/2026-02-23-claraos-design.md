# ClaraOS Design

**Date:** 2026-02-23
**Status:** Approved
**Approach:** Inspired rewrite using bogdan-os (github.com/bgevko/bogdan-os) patterns

## Concept

ClaraOS is a browser-based desktop OS interface where Clara (an AI assistant with a visual anime-style character) is the central presence. The OS frame — windows, taskbar, file system, desktop — wraps Clara's capabilities. Clara-centric: chat is the primary experience, the OS is the stage around it.

All current web UI features (Chat, Knowledge Base, Graph Explorer, Intentions, Settings, Admin, Games) survive as windowed "apps" within ClaraOS.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Clara's role | Clara-centric | Chat is primary, OS is the frame |
| Feature migration | All current features | Everything becomes a windowed app |
| File system | Full port | With backend persistence, app shortcuts |
| Visual identity | Clara-branded from start | Custom palette, avatar prominent |
| Approach | Inspired rewrite (B) | Clean architecture, split stores, own code |
| Window chrome | Windows-style | `— □ ×` on right, square buttons |
| Avatar usage | Prominent | Boot screen, chat, taskbar, desktop |

## Architecture

### State Management — Split Zustand+Immer Stores

| Store | Responsibility |
|-------|---------------|
| `windowStore` | Window lifecycle, positions, sizes, focus stack, z-index |
| `fileSystemStore` | File/directory tree, icon positions, selection, clipboard |
| `desktopStore` | Desktop state, drag-select, wallpaper prefs |
| `appRegistry` | App definitions, component resolution, default sizes |
| `claraStore` | Chat state, WebSocket connection, message history |

Stores communicate via subscriptions where needed, not cross-imports.

### Directory Structure

```
web-ui/frontend/src/
├── system/                      # Core OS infrastructure
│   ├── window/                  # Window manager
│   │   ├── store.ts             # windowStore
│   │   ├── Window.tsx           # Window container
│   │   ├── WindowHeader.tsx     # Draggable title bar + controls
│   │   ├── ResizeHandles.tsx    # 8-point resize
│   │   ├── hooks/
│   │   │   ├── useWindowMove.ts
│   │   │   └── useWindowResize.ts
│   │   └── utils.ts             # Bounds clamping, position helpers
│   ├── filesystem/              # File system
│   │   ├── store.ts             # fileSystemStore
│   │   ├── Desktop.tsx          # Desktop icon grid
│   │   ├── Directory.tsx        # Folder window view
│   │   ├── Icon.tsx             # Draggable file/folder icon
│   │   ├── SelectRect.tsx       # Drag selection overlay
│   │   └── hooks/
│   │       ├── useIconDrag.ts
│   │       ├── useIconSelect.ts
│   │       └── useDragSelect.ts
│   ├── taskbar/                 # Bottom taskbar
│   │   ├── Taskbar.tsx
│   │   ├── TaskbarEntry.tsx
│   │   └── Clock.tsx
│   ├── contextmenu/             # Right-click menus
│   │   ├── ContextMenu.tsx
│   │   └── menuBuilder.ts
│   └── theme/                   # Clara visual identity
│       ├── constants.ts         # Grid size, header height, colors
│       └── Wallpaper.tsx        # Clara-branded background
├── apps/                        # ClaraOS applications
│   ├── clara-chat/              # Chat with Clara (primary app)
│   ├── knowledge-base/          # Memory/knowledge browser
│   ├── graph-explorer/          # Entity relationship graph
│   ├── intentions/              # Intentions manager
│   ├── settings/                # User settings
│   ├── admin/                   # Admin panel
│   ├── blackjack/               # Blackjack game
│   ├── checkers/                # Checkers game
│   └── text-editor/             # File content editor
├── clara/                       # Clara integration layer
│   ├── store.ts                 # claraStore (chat state, WS)
│   ├── ChatRuntimeProvider.tsx  # assistant-ui bridge
│   └── notifications.ts        # Proactive message handling
├── api/                         # Backend API client (keep existing)
│   └── client.ts
├── auth/                        # Auth flow (keep existing)
├── App.tsx                      # Root: Desktop + WindowSystem + Taskbar
└── main.tsx                     # Entry point
```

### Data Flow

```
ClaraOS Frontend
  ├── Window actions → windowStore (local state)
  ├── File actions → fileSystemStore → Rails API (persist)
  ├── Clara chat → claraStore → WebSocket → Python Gateway (direct)
  ├── App data → Rails API → GatewayProxy → Python Gateway
  └── Games → Rails API (local game logic)
```

### Backend Changes

Rails backend stays unchanged except:
- New filesystem CRUD endpoints: `POST/GET/PUT/DELETE /api/v1/filesystem`
- Rails stores FS entries in its PostgreSQL database
- New `FileSystemEntry` model in Rails

## Window Manager

### Window State

```typescript
interface WindowState {
  id: string
  position: { x: number; y: number }
  size: { width: number; height: number }
  state: 'normal' | 'minimized' | 'maximized'
  defaultSize: { width: number; height: number }
}
```

### Focus Stack

Flat array where position = z-index:
- Click window → move to end of array (highest z)
- Close window → remove from array
- `zIndex = focused.indexOf(id) + 2`

### Window Lifecycle

1. **Open**: Create state, add to focus stack, position near center (random ±50px offset)
2. **Focus**: Move to end of focus stack
3. **Minimize**: state='minimized', scale→0, remove from focus (stays open)
4. **Maximize**: state='maximized', position (0,0), size=viewport
5. **Restore**: Reverse minimize/maximize to previous position/size
6. **Close**: Remove state + focus entry

### Window Chrome (Windows-style)

- Title on left, `— □ ×` buttons on right (square/rectangular)
- Close: red highlight on hover
- Maximize: green highlight on hover
- Minimize: amber highlight on hover
- Focused: subtle outer glow in Clara accent
- Unfocused: reduced opacity, no glow
- Rounded corners (8px radius)

### Clara Chat Window — Special Behavior

- Opens automatically on boot
- Cannot be fully closed — close button minimizes instead
- Distinct visual treatment (accent border/glow)
- Taskbar entry always visible
- Receives proactive notifications

## File System

### Data Model

```typescript
interface FSEntry {
  id: string                      // UUID
  name: string
  parentId: string | null
  type: 'file' | 'directory' | 'app-shortcut'
  iconPosition: { x: number; y: number }
  createdAt: Date
  updatedAt: Date
}

interface FSFile extends FSEntry {
  type: 'file'
  extension: string
  content: string
}

interface FSDirectory extends FSEntry {
  type: 'directory'
  children: string[]
}

interface FSAppShortcut extends FSEntry {
  type: 'app-shortcut'
  appId: string
  extension: '.app'
}
```

### Persistence

- Rails API endpoints for CRUD
- Optimistic local updates + API calls
- Full tree fetched on load, hydrated into store
- File content stored as blobs in PostgreSQL

### Desktop Grid

- 100px grid cells, column-major fill
- Snap to grid on release
- Drag to folder → move into folder

### Default Desktop (First Login)

- Clara Chat (app shortcut, pinned)
- Knowledge Base (app shortcut)
- Games folder (directory: Blackjack, Checkers)
- Settings (app shortcut)
- Graph Explorer (app shortcut)
- Intentions (app shortcut)
- My Files (empty directory)

## Apps

### App Registry

```typescript
interface AppDefinition {
  id: string
  name: string
  icon: string
  defaultWindowSize: { width: number; height: number }
  component: React.LazyExoticComponent<any>
  singleton?: boolean
  closeBehavior?: 'close' | 'minimize'
  menubarOptions?: MenubarItem[]
  contextMenuOptions?: ContextMenuItem[]
}
```

### App Roster

| App | Source | Notes |
|-----|--------|-------|
| Clara Chat | Migrate chatStore + assistant-ui | Singleton, minimize-on-close, auto-open |
| Knowledge Base | Migrate Knowledge page | Memory CRUD, search |
| Graph Explorer | Migrate Graph page | Entity relationships |
| Intentions | Migrate Intentions page | Intention management |
| Settings | Migrate Settings page | Prefs, adapter linking |
| Admin | Migrate Admin page | Admin only, hidden from non-admins |
| Blackjack | Migrate game | Multiple instances OK |
| Checkers | Migrate game | Multiple instances OK |
| Text Editor | New | Opens .txt files from file system |

### App Contract

Apps receive entry metadata as prop. Apps use existing `api/client.ts`. Apps are fully encapsulated — no knowledge of window system beyond their prop.

## Taskbar

- Fixed bottom (40px height), dark surface + backdrop-blur
- Left: Clara icon/logo
- Center: open window entries (icon + title)
- Right: clock, notification indicators
- Active window highlighted, minimized windows dimmed
- Clara Chat entry always pinned/visible
- Click entry → focus/restore window
- Right-click → context menu (Close, Minimize, Maximize)

## Context Menus

Generic data-driven system:
- Desktop: New Folder, New Text File, Paste, Refresh, Settings
- Icon: Open, Rename, Delete, Copy, Cut, Properties
- Folder: Open, Rename, Delete, Copy, Paste Into
- Taskbar entry: Close, Minimize, Maximize

## Visual Identity

### Clara's Avatar

Three poses available (center, left, right) at 750x1500px (PSD source, need PNG/WebP export):
- **Boot screen**: Center pose with loading animation
- **Chat window**: Avatar next to Clara's messages
- **Taskbar**: Small icon
- **Desktop**: Potential widget/presence

### Color Palette

- **Primary**: Deep indigo (`#6366f1` family)
- **Surface**: Dark slate (`#0f172a` → `#1e293b`)
- **Window chrome**: Lighter surface with subtle gradient
- **Accent**: Warm violet (Clara-specific glow, notifications)
- **Text**: White / light gray
- **Taskbar**: Dark surface + frosted glass (backdrop-blur)

### Wallpaper

Animated gradient in Clara's palette (Three.js shader) or static high-quality gradient for V1.

### Typography

System font stack (San Francisco / Segoe UI / system-ui). Monospace for text editor content.

## Tech Stack

- React 19 + TypeScript + Vite
- Zustand + Immer (split stores)
- TailwindCSS
- `@assistant-ui/react` (chat, proven)
- Lazy loading for all apps
- Rails backend (unchanged except new FS endpoints)
