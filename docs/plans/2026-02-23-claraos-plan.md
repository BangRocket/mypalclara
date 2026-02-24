# ClaraOS Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current web UI with ClaraOS — a desktop OS interface where Clara is the central presence, with window management, file system, taskbar, and all current features as windowed apps.

**Architecture:** Inspired rewrite of bogdan-os patterns (Zustand+Immer, focus stack, grid snapping) with split stores, backend persistence, Clara-branded visual identity, and Windows-style window chrome. Rails backend stays unchanged except for new filesystem CRUD endpoints.

**Tech Stack:** React 19, TypeScript, Vite, Zustand+Immer, TailwindCSS, @assistant-ui/react, @rails/actioncable

**Reference code:** bogdan-os source cloned at `/tmp/bogdan-os` — use for pattern reference, not copy-paste.

**Current frontend:** `web-ui/frontend/src/` — existing pages/components/stores to migrate into windowed apps.

---

## Phase 1: Foundation — Theme Constants, Window Store, Window Components

The window manager is the core of the OS. Build it first, test with a dummy app.

### Task 1: Set up directory structure and install immer

**Files:**
- Modify: `web-ui/frontend/package.json`
- Create: `web-ui/frontend/src/system/theme/constants.ts`

**Step 1: Install immer**

```bash
cd web-ui/frontend && npm install immer
```

**Step 2: Create theme constants**

Create `web-ui/frontend/src/system/theme/constants.ts`:

```typescript
// ClaraOS theme constants
// Reference: bogdan-os themes/index.ts with Clara customizations

// Layout
export const TASKBAR_HEIGHT = 44;
export const TASKBAR_ENTRY_WIDTH = 140;
export const TASKBAR_ENTRY_HEIGHT = 32;
export const WINDOW_HEADER_HEIGHT = 36;
export const WINDOW_BORDER_RADIUS = 8;
export const GRID_CELL_SIZE = 100;
export const ICON_SIZE = { width: 80, height: 88 };
export const CONTEXT_MENU_WIDTH = 180;
export const CONTEXT_MENU_ITEM_HEIGHT = 32;
export const DEFAULT_WINDOW_SIZE = { width: 600, height: 450 };

// Animation
export const CLOSE_ANIMATION_DURATION = 200;
export const ICON_ANIMATION_DURATION = 100;
export const WINDOW_OPEN_STAGGER = [1, 200, 300]; // scale, ready, opacity delays

// Colors (Clara palette — indigo/violet on dark slate)
export const COLORS = {
  primary: '#6366f1',        // Indigo-500
  primaryHover: '#818cf8',   // Indigo-400
  accent: '#8b5cf6',         // Violet-500
  accentGlow: 'rgba(139, 92, 246, 0.3)',
  surface: '#0f172a',        // Slate-900
  surfaceLight: '#1e293b',   // Slate-800
  surfaceLighter: '#334155',  // Slate-700
  windowChrome: '#1e293b',
  windowChromeActive: '#283548',
  taskbar: 'rgba(15, 23, 42, 0.85)',
  text: '#f8fafc',           // Slate-50
  textMuted: '#94a3b8',      // Slate-400
  textDim: '#64748b',        // Slate-500
  closeBtn: '#ef4444',       // Red-500
  minimizeBtn: '#f59e0b',    // Amber-500
  maximizeBtn: '#22c55e',    // Green-500
} as const;
```

**Step 3: Commit**

```bash
git add web-ui/frontend/package.json web-ui/frontend/package-lock.json web-ui/frontend/src/system/theme/constants.ts
git commit -m "feat(claraos): add theme constants and install immer"
```

---

### Task 2: Create windowStore

**Files:**
- Create: `web-ui/frontend/src/system/window/store.ts`
- Create: `web-ui/frontend/src/system/window/types.ts`

**Step 1: Create window types**

Create `web-ui/frontend/src/system/window/types.ts`:

```typescript
export interface Position {
  x: number;
  y: number;
}

export interface Size {
  width: number;
  height: number;
}

export type WindowState = 'normal' | 'minimized' | 'maximized';

export interface WindowInstance {
  id: string;
  appId: string;
  position: Position;
  size: Size;
  defaultSize: Size;
  state: WindowState;
  previousPosition?: Position;   // For restore from maximize
  previousSize?: Size;           // For restore from maximize
  isMoving: boolean;
  isResizing: boolean;
  transformScale: number;        // 0=hidden, 1=normal (for open/close animation)
  contentOpacity: number;        // 0=hidden, 1=visible (staggered reveal)
  title: string;
  icon?: string;
}
```

**Step 2: Create windowStore**

Create `web-ui/frontend/src/system/window/store.ts`:

```typescript
import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import { DEFAULT_WINDOW_SIZE, TASKBAR_HEIGHT } from '../theme/constants';
import type { Position, Size, WindowInstance, WindowState } from './types';

interface WindowStoreState {
  windows: Map<string, WindowInstance>;
  focused: string[];    // Focus stack: last element = most focused
  opened: string[];     // All open window IDs

  // Getters
  getWindow: (id: string) => WindowInstance | undefined;
  getPosition: (id: string) => Position;
  getSize: (id: string) => Size;
  getWindowState: (id: string) => WindowState;
  isFocused: (id: string) => boolean;
  getZIndex: (id: string) => number;
  isMoving: (id: string) => boolean;
  isResizing: (id: string) => boolean;
  getOpenedIds: () => string[];

  // Actions
  openWindow: (id: string, appId: string, title: string, defaultSize?: Size, icon?: string) => void;
  closeWindow: (id: string) => void;
  focusWindow: (id: string) => void;
  minimizeWindow: (id: string) => void;
  toggleMinimize: (id: string) => void;
  maximizeWindow: (id: string) => void;
  toggleMaximize: (id: string) => void;
  restoreWindow: (id: string) => void;
  setPosition: (id: string, pos: Position) => void;
  setSize: (id: string, size: Size) => void;
  setMoving: (id: string, moving: boolean) => void;
  setResizing: (id: string, resizing: boolean) => void;
  setTransformScale: (id: string, scale: number) => void;
  setContentOpacity: (id: string, opacity: number) => void;
  setTitle: (id: string, title: string) => void;
}

function randomOffset(): number {
  return Math.floor(Math.random() * 100) - 50;
}

function centerPosition(size: Size): Position {
  return {
    x: Math.max(0, (window.innerWidth - size.width) / 2 + randomOffset()),
    y: Math.max(0, (window.innerHeight - TASKBAR_HEIGHT - size.height) / 2 + randomOffset()),
  };
}

export const useWindowStore = create<WindowStoreState>()(
  immer((set, get) => ({
    windows: new Map(),
    focused: [],
    opened: [],

    // Getters
    getWindow: (id) => get().windows.get(id),
    getPosition: (id) => get().windows.get(id)?.position ?? { x: 0, y: 0 },
    getSize: (id) => {
      const win = get().windows.get(id);
      if (!win) return { width: 0, height: 0 };
      // Clamp to viewport
      return {
        width: Math.min(win.size.width, window.innerWidth),
        height: Math.min(win.size.height, window.innerHeight - TASKBAR_HEIGHT),
      };
    },
    getWindowState: (id) => get().windows.get(id)?.state ?? 'normal',
    isFocused: (id) => {
      const { focused } = get();
      return focused.length > 0 && focused[focused.length - 1] === id;
    },
    getZIndex: (id) => {
      const win = get().windows.get(id);
      if (win?.state === 'maximized') return 1;
      const idx = get().focused.indexOf(id);
      return idx >= 0 ? idx + 2 : 0;
    },
    isMoving: (id) => get().windows.get(id)?.isMoving ?? false,
    isResizing: (id) => get().windows.get(id)?.isResizing ?? false,
    getOpenedIds: () => get().opened,

    // Actions
    openWindow: (id, appId, title, defaultSize, icon) => {
      set((state) => {
        if (state.windows.has(id)) {
          // Already open — just focus
          state.focused = state.focused.filter((fid) => fid !== id);
          state.focused.push(id);
          const win = state.windows.get(id)!;
          if (win.state === 'minimized') {
            win.state = 'normal';
            win.transformScale = 1;
            win.contentOpacity = 1;
          }
          return;
        }
        const size = defaultSize ?? DEFAULT_WINDOW_SIZE;
        const win: WindowInstance = {
          id,
          appId,
          position: centerPosition(size),
          size: { ...size },
          defaultSize: { ...size },
          state: 'normal',
          isMoving: false,
          isResizing: false,
          transformScale: 0,  // Will animate to 1
          contentOpacity: 0,  // Will animate to 1
          title,
          icon,
        };
        state.windows.set(id, win);
        state.opened.push(id);
        state.focused = state.focused.filter((fid) => fid !== id);
        state.focused.push(id);
      });
    },

    closeWindow: (id) => {
      set((state) => {
        state.windows.delete(id);
        state.opened = state.opened.filter((oid) => oid !== id);
        state.focused = state.focused.filter((fid) => fid !== id);
      });
    },

    focusWindow: (id) => {
      set((state) => {
        if (!state.windows.has(id)) return;
        state.focused = state.focused.filter((fid) => fid !== id);
        state.focused.push(id);
      });
    },

    minimizeWindow: (id) => {
      set((state) => {
        const win = state.windows.get(id);
        if (!win) return;
        win.state = 'minimized';
        win.transformScale = 0;
        win.contentOpacity = 0;
        state.focused = state.focused.filter((fid) => fid !== id);
      });
    },

    toggleMinimize: (id) => {
      const win = get().windows.get(id);
      if (!win) return;
      if (win.state === 'minimized') {
        set((state) => {
          const w = state.windows.get(id)!;
          w.state = 'normal';
          w.transformScale = 1;
          w.contentOpacity = 1;
          state.focused = state.focused.filter((fid) => fid !== id);
          state.focused.push(id);
        });
      } else {
        get().minimizeWindow(id);
      }
    },

    maximizeWindow: (id) => {
      set((state) => {
        const win = state.windows.get(id);
        if (!win) return;
        win.previousPosition = { ...win.position };
        win.previousSize = { ...win.size };
        win.position = { x: 0, y: 0 };
        win.size = { width: window.innerWidth, height: window.innerHeight - TASKBAR_HEIGHT };
        win.state = 'maximized';
      });
    },

    toggleMaximize: (id) => {
      const win = get().windows.get(id);
      if (!win) return;
      if (win.state === 'maximized') {
        get().restoreWindow(id);
      } else {
        get().maximizeWindow(id);
      }
    },

    restoreWindow: (id) => {
      set((state) => {
        const win = state.windows.get(id);
        if (!win) return;
        if (win.previousPosition) win.position = { ...win.previousPosition };
        if (win.previousSize) win.size = { ...win.previousSize };
        win.state = 'normal';
        win.previousPosition = undefined;
        win.previousSize = undefined;
      });
    },

    setPosition: (id, pos) => {
      set((state) => {
        const win = state.windows.get(id);
        if (win) win.position = pos;
      });
    },

    setSize: (id, size) => {
      set((state) => {
        const win = state.windows.get(id);
        if (win) win.size = size;
      });
    },

    setMoving: (id, moving) => {
      set((state) => {
        const win = state.windows.get(id);
        if (win) win.isMoving = moving;
      });
    },

    setResizing: (id, resizing) => {
      set((state) => {
        const win = state.windows.get(id);
        if (win) win.isResizing = resizing;
      });
    },

    setTransformScale: (id, scale) => {
      set((state) => {
        const win = state.windows.get(id);
        if (win) win.transformScale = scale;
      });
    },

    setContentOpacity: (id, opacity) => {
      set((state) => {
        const win = state.windows.get(id);
        if (win) win.contentOpacity = opacity;
      });
    },

    setTitle: (id, title) => {
      set((state) => {
        const win = state.windows.get(id);
        if (win) win.title = title;
      });
    },
  })),
);
```

**Step 3: Commit**

```bash
git add web-ui/frontend/src/system/window/types.ts web-ui/frontend/src/system/window/store.ts
git commit -m "feat(claraos): add windowStore with Zustand+Immer"
```

---

### Task 3: Create useWindowMove hook

**Files:**
- Create: `web-ui/frontend/src/system/window/hooks/useWindowMove.ts`
- Create: `web-ui/frontend/src/system/window/utils.ts`

**Step 1: Create window utils (bounds clamping)**

Create `web-ui/frontend/src/system/window/utils.ts`:

```typescript
import type { Position, Size } from './types';
import { TASKBAR_HEIGHT, WINDOW_HEADER_HEIGHT } from '../theme/constants';

/**
 * Clamp window position so the header stays accessible.
 * At minimum, WINDOW_HEADER_HEIGHT pixels of the top must remain visible,
 * and the window must not go below the taskbar.
 */
export function clampToBounds(pos: Position, size: Size): Position {
  const maxX = window.innerWidth - 50; // At least 50px visible horizontally
  const maxY = window.innerHeight - TASKBAR_HEIGHT - WINDOW_HEADER_HEIGHT;
  return {
    x: Math.max(-size.width + 50, Math.min(pos.x, maxX)),
    y: Math.max(0, Math.min(pos.y, maxY)),
  };
}
```

**Step 2: Create useWindowMove hook**

Create `web-ui/frontend/src/system/window/hooks/useWindowMove.ts`:

```typescript
import { useCallback, useRef } from 'react';
import { useWindowStore } from '../store';
import { clampToBounds } from '../utils';

export function useWindowMove(windowId: string) {
  const offsetRef = useRef({ x: 0, y: 0 });

  const handleMoveStart = useCallback(
    (event: React.MouseEvent) => {
      event.preventDefault();
      const pos = useWindowStore.getState().getPosition(windowId);
      offsetRef.current = {
        x: event.clientX - pos.x,
        y: event.clientY - pos.y,
      };
      useWindowStore.getState().setMoving(windowId, true);
      useWindowStore.getState().focusWindow(windowId);

      const handleMouseMove = (e: MouseEvent) => {
        const x = e.clientX - offsetRef.current.x;
        const y = e.clientY - offsetRef.current.y;
        useWindowStore.getState().setPosition(windowId, { x, y });
      };

      const handleMouseUp = () => {
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleMouseUp);
        useWindowStore.getState().setMoving(windowId, false);
        const pos = useWindowStore.getState().getPosition(windowId);
        const size = useWindowStore.getState().getSize(windowId);
        const clamped = clampToBounds(pos, size);
        if (clamped.x !== pos.x || clamped.y !== pos.y) {
          useWindowStore.getState().setPosition(windowId, clamped);
        }
      };

      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    },
    [windowId],
  );

  return { handleMoveStart };
}
```

**Step 3: Commit**

```bash
git add web-ui/frontend/src/system/window/utils.ts web-ui/frontend/src/system/window/hooks/useWindowMove.ts
git commit -m "feat(claraos): add useWindowMove hook with bounds clamping"
```

---

### Task 4: Create useWindowResize hook

**Files:**
- Create: `web-ui/frontend/src/system/window/hooks/useWindowResize.ts`

**Step 1: Create useWindowResize hook**

Create `web-ui/frontend/src/system/window/hooks/useWindowResize.ts`:

```typescript
import { useCallback, useRef } from 'react';
import { useWindowStore } from '../store';
import { TASKBAR_HEIGHT } from '../theme/constants';

export type ResizeDirection =
  | 'left' | 'right' | 'top' | 'bottom'
  | 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right';

export function useWindowResize(windowId: string) {
  const directionRef = useRef<ResizeDirection | null>(null);

  const handleResizeStart = useCallback(
    (event: React.MouseEvent, direction: ResizeDirection) => {
      event.preventDefault();
      event.stopPropagation();
      directionRef.current = direction;
      useWindowStore.getState().setResizing(windowId, true);
      useWindowStore.getState().focusWindow(windowId);

      const handleMouseMove = (e: MouseEvent) => {
        const dir = directionRef.current;
        if (!dir) return;

        const state = useWindowStore.getState();
        const { x: posX, y: posY } = state.getPosition(windowId);
        const { width: curW, height: curH } = state.getSize(windowId);
        const win = state.getWindow(windowId);
        const minW = win?.defaultSize.width ?? 200;
        const minH = win?.defaultSize.height ?? 150;

        let newX = posX, newY = posY, newW = curW, newH = curH;

        if (dir.includes('right')) {
          newW = Math.max(e.clientX - posX, minW);
        }
        if (dir.includes('bottom')) {
          newH = Math.max(e.clientY - posY, minH);
        }
        if (dir.includes('left')) {
          newX = Math.min(e.clientX, posX + curW - minW);
          newX = Math.max(0, newX);
          newW = curW + posX - newX;
        }
        if (dir.includes('top')) {
          newY = Math.min(e.clientY, posY + curH - minH);
          newY = Math.max(0, newY);
          newH = curH + posY - newY;
        }

        // Viewport bounds
        newW = Math.min(newW, window.innerWidth - newX);
        newH = Math.min(newH, window.innerHeight - TASKBAR_HEIGHT - newY);

        state.setSize(windowId, { width: newW, height: newH });
        state.setPosition(windowId, { x: newX, y: newY });
      };

      const handleMouseUp = () => {
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleMouseUp);
        directionRef.current = null;
        useWindowStore.getState().setResizing(windowId, false);
      };

      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    },
    [windowId],
  );

  return { handleResizeStart };
}
```

**Step 2: Commit**

```bash
git add web-ui/frontend/src/system/window/hooks/useWindowResize.ts
git commit -m "feat(claraos): add useWindowResize hook with 8-direction resize"
```

---

### Task 5: Create ResizeHandles component

**Files:**
- Create: `web-ui/frontend/src/system/window/ResizeHandles.tsx`

**Step 1: Create ResizeHandles component**

Create `web-ui/frontend/src/system/window/ResizeHandles.tsx`:

```tsx
import { useWindowResize, type ResizeDirection } from './hooks/useWindowResize';

interface ResizeHandlesProps {
  windowId: string;
}

const HANDLE_SIZE = 6;
const CORNER_SIZE = 12;

interface HandleConfig {
  direction: ResizeDirection;
  className: string;
  style: React.CSSProperties;
}

const handles: HandleConfig[] = [
  // Edges
  { direction: 'left',   className: 'cursor-ew-resize',   style: { left: -HANDLE_SIZE/2, top: CORNER_SIZE, width: HANDLE_SIZE, bottom: CORNER_SIZE } },
  { direction: 'right',  className: 'cursor-ew-resize',   style: { right: -HANDLE_SIZE/2, top: CORNER_SIZE, width: HANDLE_SIZE, bottom: CORNER_SIZE } },
  { direction: 'top',    className: 'cursor-ns-resize',   style: { top: -HANDLE_SIZE/2, left: CORNER_SIZE, height: HANDLE_SIZE, right: CORNER_SIZE } },
  { direction: 'bottom', className: 'cursor-ns-resize',   style: { bottom: -HANDLE_SIZE/2, left: CORNER_SIZE, height: HANDLE_SIZE, right: CORNER_SIZE } },
  // Corners
  { direction: 'top-left',     className: 'cursor-nwse-resize', style: { top: -HANDLE_SIZE/2, left: -HANDLE_SIZE/2, width: CORNER_SIZE, height: CORNER_SIZE } },
  { direction: 'top-right',    className: 'cursor-nesw-resize', style: { top: -HANDLE_SIZE/2, right: -HANDLE_SIZE/2, width: CORNER_SIZE, height: CORNER_SIZE } },
  { direction: 'bottom-left',  className: 'cursor-nesw-resize', style: { bottom: -HANDLE_SIZE/2, left: -HANDLE_SIZE/2, width: CORNER_SIZE, height: CORNER_SIZE } },
  { direction: 'bottom-right', className: 'cursor-nwse-resize', style: { bottom: -HANDLE_SIZE/2, right: -HANDLE_SIZE/2, width: CORNER_SIZE, height: CORNER_SIZE } },
];

export function ResizeHandles({ windowId }: ResizeHandlesProps) {
  const { handleResizeStart } = useWindowResize(windowId);

  return (
    <>
      {handles.map((h) => (
        <div
          key={h.direction}
          className={`absolute z-50 ${h.className}`}
          style={{ ...h.style, position: 'absolute' }}
          onMouseDown={(e) => handleResizeStart(e, h.direction)}
        />
      ))}
    </>
  );
}
```

**Step 2: Commit**

```bash
git add web-ui/frontend/src/system/window/ResizeHandles.tsx
git commit -m "feat(claraos): add ResizeHandles component"
```

---

### Task 6: Create WindowHeader component (Windows-style)

**Files:**
- Create: `web-ui/frontend/src/system/window/WindowHeader.tsx`

**Step 1: Create WindowHeader component**

Create `web-ui/frontend/src/system/window/WindowHeader.tsx`:

```tsx
import { useWindowStore } from './store';
import { useWindowMove } from './hooks/useWindowMove';
import { COLORS, WINDOW_HEADER_HEIGHT, CLOSE_ANIMATION_DURATION } from '../theme/constants';

interface WindowHeaderProps {
  windowId: string;
  onClose?: () => void;  // Override close behavior (e.g., minimize-on-close for Clara)
}

export function WindowHeader({ windowId, onClose }: WindowHeaderProps) {
  const { handleMoveStart } = useWindowMove(windowId);
  const title = useWindowStore((s) => s.getWindow(windowId)?.title ?? '');
  const icon = useWindowStore((s) => s.getWindow(windowId)?.icon);
  const isFocused = useWindowStore((s) => s.isFocused(windowId));
  const windowState = useWindowStore((s) => s.getWindowState(windowId));

  const handleMinimize = () => {
    useWindowStore.getState().minimizeWindow(windowId);
  };

  const handleMaximize = () => {
    useWindowStore.getState().toggleMaximize(windowId);
  };

  const handleClose = () => {
    if (onClose) {
      onClose();
    } else {
      // Animate close
      useWindowStore.getState().setTransformScale(windowId, 0);
      setTimeout(() => {
        useWindowStore.getState().closeWindow(windowId);
      }, CLOSE_ANIMATION_DURATION);
    }
  };

  const handleDoubleClick = () => {
    handleMaximize();
  };

  return (
    <div
      className="flex items-center select-none shrink-0"
      style={{
        height: WINDOW_HEADER_HEIGHT,
        backgroundColor: isFocused ? COLORS.windowChromeActive : COLORS.windowChrome,
        borderTopLeftRadius: windowState === 'maximized' ? 0 : 8,
        borderTopRightRadius: windowState === 'maximized' ? 0 : 8,
        borderBottom: `1px solid ${COLORS.surfaceLighter}`,
      }}
      onMouseDown={handleMoveStart}
      onDoubleClick={handleDoubleClick}
    >
      {/* Title area */}
      <div className="flex items-center gap-2 flex-1 min-w-0 pl-3">
        {icon && <span className="text-sm">{icon}</span>}
        <span
          className="text-sm truncate"
          style={{ color: isFocused ? COLORS.text : COLORS.textMuted }}
        >
          {title}
        </span>
      </div>

      {/* Windows-style buttons: — □ × */}
      <div className="flex items-center h-full" onMouseDown={(e) => e.stopPropagation()}>
        {/* Minimize */}
        <button
          className="flex items-center justify-center h-full px-3 transition-colors hover:bg-white/10"
          onClick={handleMinimize}
          title="Minimize"
        >
          <svg width="10" height="1" viewBox="0 0 10 1">
            <rect width="10" height="1" fill={COLORS.textMuted} />
          </svg>
        </button>

        {/* Maximize/Restore */}
        <button
          className="flex items-center justify-center h-full px-3 transition-colors hover:bg-white/10"
          onClick={handleMaximize}
          title={windowState === 'maximized' ? 'Restore' : 'Maximize'}
        >
          {windowState === 'maximized' ? (
            // Restore icon (overlapping squares)
            <svg width="10" height="10" viewBox="0 0 10 10">
              <rect x="2" y="0" width="8" height="8" rx="1" fill="none" stroke={COLORS.textMuted} strokeWidth="1" />
              <rect x="0" y="2" width="8" height="8" rx="1" fill={COLORS.windowChromeActive} stroke={COLORS.textMuted} strokeWidth="1" />
            </svg>
          ) : (
            // Maximize icon (square)
            <svg width="10" height="10" viewBox="0 0 10 10">
              <rect x="0" y="0" width="10" height="10" rx="1" fill="none" stroke={COLORS.textMuted} strokeWidth="1" />
            </svg>
          )}
        </button>

        {/* Close */}
        <button
          className="flex items-center justify-center h-full px-3 transition-colors"
          style={{ borderTopRightRadius: windowState === 'maximized' ? 0 : 8 }}
          onClick={handleClose}
          title="Close"
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLElement).style.backgroundColor = COLORS.closeBtn;
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent';
          }}
        >
          <svg width="10" height="10" viewBox="0 0 10 10">
            <line x1="0" y1="0" x2="10" y2="10" stroke={COLORS.textMuted} strokeWidth="1.5" />
            <line x1="10" y1="0" x2="0" y2="10" stroke={COLORS.textMuted} strokeWidth="1.5" />
          </svg>
        </button>
      </div>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add web-ui/frontend/src/system/window/WindowHeader.tsx
git commit -m "feat(claraos): add WindowHeader with Windows-style controls"
```

---

### Task 7: Create Window container component

**Files:**
- Create: `web-ui/frontend/src/system/window/Window.tsx`

**Step 1: Create Window component**

Create `web-ui/frontend/src/system/window/Window.tsx`:

```tsx
import { Suspense, useEffect, useMemo, useState } from 'react';
import { useWindowStore } from './store';
import { WindowHeader } from './WindowHeader';
import { ResizeHandles } from './ResizeHandles';
import { useAppRegistry } from '../apps/registry';
import { COLORS, WINDOW_BORDER_RADIUS, WINDOW_OPEN_STAGGER } from '../theme/constants';

interface WindowProps {
  windowId: string;
  onClose?: () => void;
}

function WindowLoading() {
  return (
    <div className="flex items-center justify-center h-full" style={{ color: COLORS.textMuted }}>
      Loading...
    </div>
  );
}

export function Window({ windowId, onClose }: WindowProps) {
  const win = useWindowStore((s) => s.getWindow(windowId));
  const isFocused = useWindowStore((s) => s.isFocused(windowId));
  const zIndex = useWindowStore((s) => s.getZIndex(windowId));
  const isMoving = useWindowStore((s) => s.isMoving(windowId));
  const isResizing = useWindowStore((s) => s.isResizing(windowId));
  const { getComponent } = useAppRegistry();
  const [isReady, setIsReady] = useState(false);

  // Open animation: stagger scale → ready → opacity
  useEffect(() => {
    const t1 = setTimeout(() => useWindowStore.getState().setTransformScale(windowId, 1), WINDOW_OPEN_STAGGER[0]);
    const t2 = setTimeout(() => setIsReady(true), WINDOW_OPEN_STAGGER[1]);
    const t3 = setTimeout(() => useWindowStore.getState().setContentOpacity(windowId, 1), WINDOW_OPEN_STAGGER[2]);
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); };
  }, [windowId]);

  const Component = useMemo(() => {
    if (!win) return null;
    return getComponent(win.appId);
  }, [win?.appId, getComponent]);

  if (!win) return null;

  const isMaximized = win.state === 'maximized';
  const useTransition = !isMoving && !isResizing;

  return (
    <div
      className="absolute"
      style={{
        width: win.size.width,
        height: win.size.height,
        transform: `translate(${win.position.x}px, ${win.state === 'minimized' ? window.innerHeight : win.position.y}px) scale(${win.transformScale})`,
        transition: useTransition ? 'transform 200ms ease-out, opacity 200ms ease-out' : 'none',
        zIndex,
        borderRadius: isMaximized ? 0 : WINDOW_BORDER_RADIUS,
        overflow: 'hidden',
        boxShadow: isFocused
          ? `0 8px 32px rgba(0,0,0,0.4), 0 0 0 1px ${COLORS.surfaceLighter}, 0 0 20px ${COLORS.accentGlow}`
          : `0 4px 16px rgba(0,0,0,0.3), 0 0 0 1px ${COLORS.surfaceLighter}`,
        backgroundColor: COLORS.surface,
      }}
      onMouseDown={() => useWindowStore.getState().focusWindow(windowId)}
    >
      {/* Resize handles (not when maximized) */}
      {!isMaximized && <ResizeHandles windowId={windowId} />}

      {/* Header */}
      {!isMaximized && <WindowHeader windowId={windowId} onClose={onClose} />}

      {/* Content */}
      <div
        className="flex-1 overflow-auto"
        style={{
          height: isMaximized ? '100%' : `calc(100% - 36px)`,
          opacity: win.contentOpacity,
          transition: useTransition ? 'opacity 200ms ease-out' : 'none',
        }}
      >
        {isReady && Component && (
          <Suspense fallback={<WindowLoading />}>
            <Component windowId={windowId} />
          </Suspense>
        )}
      </div>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add web-ui/frontend/src/system/window/Window.tsx
git commit -m "feat(claraos): add Window container with animations and lazy content"
```

---

### Task 8: Create WindowSystem renderer and app registry

**Files:**
- Create: `web-ui/frontend/src/system/window/WindowSystem.tsx`
- Create: `web-ui/frontend/src/system/apps/registry.tsx`

**Step 1: Create app registry**

Create `web-ui/frontend/src/system/apps/registry.tsx`:

```tsx
import { createContext, useContext, type LazyExoticComponent, type ComponentType } from 'react';

export interface AppDefinition {
  id: string;
  name: string;
  icon: string;
  defaultWindowSize: { width: number; height: number };
  component: LazyExoticComponent<ComponentType<{ windowId: string }>>;
  singleton?: boolean;
  closeBehavior?: 'close' | 'minimize';
}

interface AppRegistryContextValue {
  apps: Map<string, AppDefinition>;
  getComponent: (appId: string) => LazyExoticComponent<ComponentType<{ windowId: string }>> | null;
  getApp: (appId: string) => AppDefinition | undefined;
}

const AppRegistryContext = createContext<AppRegistryContextValue>({
  apps: new Map(),
  getComponent: () => null,
  getApp: () => undefined,
});

export function AppRegistryProvider({
  apps,
  children,
}: {
  apps: Map<string, AppDefinition>;
  children: React.ReactNode;
}) {
  const value: AppRegistryContextValue = {
    apps,
    getComponent: (appId) => apps.get(appId)?.component ?? null,
    getApp: (appId) => apps.get(appId),
  };

  return (
    <AppRegistryContext.Provider value={value}>
      {children}
    </AppRegistryContext.Provider>
  );
}

export function useAppRegistry() {
  return useContext(AppRegistryContext);
}
```

**Step 2: Create WindowSystem renderer**

Create `web-ui/frontend/src/system/window/WindowSystem.tsx`:

```tsx
import { useWindowStore } from './store';
import { Window } from './Window';
import { useAppRegistry } from '../apps/registry';

export function WindowSystem() {
  const openedIds = useWindowStore((s) => s.getOpenedIds());
  const { getApp } = useAppRegistry();

  return (
    <>
      {openedIds.map((id) => {
        const win = useWindowStore.getState().getWindow(id);
        if (!win) return null;
        const app = getApp(win.appId);
        const onClose = app?.closeBehavior === 'minimize'
          ? () => useWindowStore.getState().minimizeWindow(id)
          : undefined;
        return <Window key={id} windowId={id} onClose={onClose} />;
      })}
    </>
  );
}
```

**Step 3: Commit**

```bash
git add web-ui/frontend/src/system/apps/registry.tsx web-ui/frontend/src/system/window/WindowSystem.tsx
git commit -m "feat(claraos): add app registry and WindowSystem renderer"
```

---

### Task 9: Create Taskbar with clock

**Files:**
- Create: `web-ui/frontend/src/system/taskbar/Taskbar.tsx`
- Create: `web-ui/frontend/src/system/taskbar/TaskbarEntry.tsx`
- Create: `web-ui/frontend/src/system/taskbar/Clock.tsx`

**Step 1: Create Clock component**

Create `web-ui/frontend/src/system/taskbar/Clock.tsx`:

```tsx
import { useEffect, useState } from 'react';
import { COLORS } from '../theme/constants';

export function Clock() {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const interval = setInterval(() => setTime(new Date()), 60_000);
    return () => clearInterval(interval);
  }, []);

  const formatted = time.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });

  return (
    <span className="text-xs px-2 whitespace-nowrap" style={{ color: COLORS.textMuted }}>
      {formatted}
    </span>
  );
}
```

**Step 2: Create TaskbarEntry component**

Create `web-ui/frontend/src/system/taskbar/TaskbarEntry.tsx`:

```tsx
import { useWindowStore } from '../window/store';
import { COLORS, TASKBAR_ENTRY_WIDTH, TASKBAR_ENTRY_HEIGHT } from '../theme/constants';

interface TaskbarEntryProps {
  windowId: string;
}

export function TaskbarEntry({ windowId }: TaskbarEntryProps) {
  const win = useWindowStore((s) => s.getWindow(windowId));
  const isFocused = useWindowStore((s) => s.isFocused(windowId));
  const windowState = useWindowStore((s) => s.getWindowState(windowId));

  if (!win) return null;

  const isMinimized = windowState === 'minimized';

  const handleClick = () => {
    if (isFocused && !isMinimized) {
      useWindowStore.getState().minimizeWindow(windowId);
    } else {
      useWindowStore.getState().toggleMinimize(windowId);
      useWindowStore.getState().focusWindow(windowId);
    }
  };

  return (
    <button
      className="flex items-center gap-1.5 px-2 rounded text-xs transition-colors truncate"
      style={{
        width: TASKBAR_ENTRY_WIDTH,
        height: TASKBAR_ENTRY_HEIGHT,
        backgroundColor: isFocused
          ? 'rgba(255,255,255,0.15)'
          : isMinimized
            ? 'rgba(255,255,255,0.05)'
            : 'rgba(255,255,255,0.08)',
        color: isFocused ? COLORS.text : COLORS.textMuted,
        borderBottom: isFocused ? `2px solid ${COLORS.primary}` : '2px solid transparent',
      }}
      onClick={handleClick}
      title={win.title}
    >
      {win.icon && <span>{win.icon}</span>}
      <span className="truncate">{win.title}</span>
    </button>
  );
}
```

**Step 3: Create Taskbar component**

Create `web-ui/frontend/src/system/taskbar/Taskbar.tsx`:

```tsx
import { useWindowStore } from '../window/store';
import { TaskbarEntry } from './TaskbarEntry';
import { Clock } from './Clock';
import { COLORS, TASKBAR_HEIGHT } from '../theme/constants';

export function Taskbar() {
  const openedIds = useWindowStore((s) => s.getOpenedIds());

  return (
    <footer
      className="fixed bottom-0 left-0 right-0 flex items-center px-2 gap-1 backdrop-blur-xl"
      style={{
        height: TASKBAR_HEIGHT,
        backgroundColor: COLORS.taskbar,
        borderTop: `1px solid ${COLORS.surfaceLighter}`,
        zIndex: 9999,
      }}
    >
      {/* Clara logo / start area */}
      <div className="flex items-center px-2" style={{ color: COLORS.primary }}>
        <span className="text-lg font-bold">C</span>
      </div>

      {/* Window entries */}
      <div className="flex items-center gap-1 flex-1 overflow-x-auto">
        {openedIds.map((id) => (
          <TaskbarEntry key={id} windowId={id} />
        ))}
      </div>

      {/* Right side: clock */}
      <Clock />
    </footer>
  );
}
```

**Step 4: Commit**

```bash
git add web-ui/frontend/src/system/taskbar/Clock.tsx web-ui/frontend/src/system/taskbar/TaskbarEntry.tsx web-ui/frontend/src/system/taskbar/Taskbar.tsx
git commit -m "feat(claraos): add Taskbar with window entries and clock"
```

---

### Task 10: Create Wallpaper and wire up root ClaraOS App

**Files:**
- Create: `web-ui/frontend/src/system/theme/Wallpaper.tsx`
- Create: `web-ui/frontend/src/system/apps/defaultApps.ts`
- Modify: `web-ui/frontend/src/App.tsx`

**Step 1: Create Wallpaper**

Create `web-ui/frontend/src/system/theme/Wallpaper.tsx`:

```tsx
import { COLORS, TASKBAR_HEIGHT } from './constants';

export function Wallpaper({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="fixed inset-0 overflow-hidden"
      style={{
        background: `linear-gradient(135deg, ${COLORS.surface} 0%, #1a1145 40%, ${COLORS.surface} 100%)`,
        paddingBottom: TASKBAR_HEIGHT,
      }}
    >
      {children}
    </div>
  );
}
```

**Step 2: Create defaultApps registry**

Create `web-ui/frontend/src/system/apps/defaultApps.ts`:

```typescript
import { lazy } from 'react';
import type { AppDefinition } from './registry';

// Placeholder app for initial testing — will be replaced with real apps in Phase 3
const PlaceholderApp = lazy(() =>
  Promise.resolve({
    default: ({ windowId }: { windowId: string }) => {
      return (
        <div style={{ padding: 16, color: '#94a3b8' }}>
          <p>App placeholder for window: {windowId}</p>
        </div>
      );
    },
  }),
);

export const defaultApps = new Map<string, AppDefinition>([
  [
    'clara-chat',
    {
      id: 'clara-chat',
      name: 'Clara',
      icon: '💬',
      defaultWindowSize: { width: 700, height: 550 },
      component: PlaceholderApp,
      singleton: true,
      closeBehavior: 'minimize',
    },
  ],
  [
    'settings',
    {
      id: 'settings',
      name: 'Settings',
      icon: '⚙️',
      defaultWindowSize: { width: 500, height: 400 },
      component: PlaceholderApp,
      singleton: true,
    },
  ],
]);
```

**Step 3: Update App.tsx — new ClaraOS root**

This is a rewrite of `web-ui/frontend/src/App.tsx`. The current App.tsx (95 lines) uses React Router with pages. The new version uses the OS desktop. Keep the auth flow but replace the router interior with ClaraOS.

Note: We preserve the existing App.tsx content in a comment block initially, but the new root renders the desktop OS. Auth still wraps everything.

Rewrite `web-ui/frontend/src/App.tsx`:

```tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './auth/AuthProvider';
import { OAuthCallback } from './auth/OAuthCallback';
import { default as LoginPage } from './pages/Login';
import { default as PendingApproval } from './pages/PendingApproval';
import { default as SuspendedPage } from './pages/Suspended';

import { AppRegistryProvider } from './system/apps/registry';
import { defaultApps } from './system/apps/defaultApps';
import { Wallpaper } from './system/theme/Wallpaper';
import { WindowSystem } from './system/window/WindowSystem';
import { Taskbar } from './system/taskbar/Taskbar';
import { useEffect } from 'react';
import { useWindowStore } from './system/window/store';

const queryClient = new QueryClient();

function ClaraOSDesktop() {
  // Open Clara Chat on boot
  useEffect(() => {
    const app = defaultApps.get('clara-chat');
    if (app) {
      useWindowStore.getState().openWindow('clara-chat', 'clara-chat', app.name, app.defaultWindowSize, app.icon);
    }
  }, []);

  return (
    <AppRegistryProvider apps={defaultApps}>
      <Wallpaper>
        <WindowSystem />
      </Wallpaper>
      <Taskbar />
    </AppRegistryProvider>
  );
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  if (user.status === 'pending') return <Navigate to="/pending" replace />;
  if (user.status === 'suspended') return <Navigate to="/suspended" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/auth/callback/:provider" element={<OAuthCallback />} />
            <Route path="/pending" element={<PendingApproval />} />
            <Route path="/suspended" element={<SuspendedPage />} />
            <Route
              path="/*"
              element={
                <ProtectedRoute>
                  <ClaraOSDesktop />
                </ProtectedRoute>
              }
            />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
```

**Step 4: Verify it compiles**

Run: `cd web-ui/frontend && npm run build`
Expected: Build succeeds (may have unused import warnings from old components, that's fine)

**Step 5: Verify it runs**

Run: `cd web-ui/frontend && npm run dev`
Expected: ClaraOS desktop with wallpaper gradient, one Clara Chat window (placeholder content), taskbar at bottom with Clara entry and clock.

**Step 6: Commit**

```bash
git add web-ui/frontend/src/system/theme/Wallpaper.tsx web-ui/frontend/src/system/apps/defaultApps.ts web-ui/frontend/src/App.tsx
git commit -m "feat(claraos): wire up ClaraOS desktop with wallpaper, window system, taskbar"
```

---

## Phase 2: Desktop, File System, Context Menus

### Task 11: Create fileSystemStore

**Files:**
- Create: `web-ui/frontend/src/system/filesystem/types.ts`
- Create: `web-ui/frontend/src/system/filesystem/store.ts`

**Step 1: Create filesystem types**

Create `web-ui/frontend/src/system/filesystem/types.ts`:

```typescript
export type EntryId = string;

export interface Position {
  x: number;
  y: number;
}

export type FSEntryType = 'file' | 'directory' | 'app-shortcut';

interface BaseEntry {
  id: EntryId;
  name: string;
  parentId: EntryId | null;
  type: FSEntryType;
  iconPosition: Position;
  createdAt: Date;
  updatedAt: Date;
  disableDelete?: boolean;
  disableCopy?: boolean;
  icon?: string;
}

export interface FSFile extends BaseEntry {
  type: 'file';
  extension: string;
  content: string;
}

export interface FSDirectory extends BaseEntry {
  type: 'directory';
  children: EntryId[];
}

export interface FSAppShortcut extends BaseEntry {
  type: 'app-shortcut';
  appId: string;
  extension: '.app';
}

export type FSEntry = FSFile | FSDirectory | FSAppShortcut;
```

**Step 2: Create fileSystemStore**

Create `web-ui/frontend/src/system/filesystem/store.ts`:

```typescript
import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import { GRID_CELL_SIZE } from '../theme/constants';
import type { EntryId, FSEntry, FSDirectory, FSFile, FSAppShortcut, Position } from './types';

interface FileSystemStoreState {
  lookup: Map<EntryId, FSEntry>;
  selected: EntryId[];
  clipboard: EntryId[];
  renaming: EntryId | null;

  // Getters
  getEntry: (id: EntryId) => FSEntry | undefined;
  getChildren: (parentId: EntryId) => FSEntry[];
  getDesktopEntries: () => FSEntry[];

  // Selection
  select: (id: EntryId) => void;
  deselect: (id: EntryId) => void;
  toggleSelect: (id: EntryId) => void;
  selectAll: (parentId: EntryId) => void;
  clearSelection: () => void;
  isSelected: (id: EntryId) => boolean;

  // Clipboard
  copySelected: () => void;
  paste: (parentId: EntryId) => void;

  // File operations
  createDirectory: (parentId: EntryId, name: string) => EntryId;
  createFile: (parentId: EntryId, name: string, extension: string, content?: string) => EntryId;
  deleteEntry: (id: EntryId) => void;
  renameEntry: (id: EntryId, name: string) => void;
  moveEntry: (id: EntryId, newParentId: EntryId) => void;
  setIconPosition: (id: EntryId, pos: Position) => void;
  setRenaming: (id: EntryId | null) => void;

  // Initialization
  initDesktop: (apps: Map<string, { id: string; name: string; icon: string }>) => void;
}

function generateId(): string {
  return crypto.randomUUID();
}

function findEmptyGridPosition(
  entries: FSEntry[],
  layout: 'column' | 'row' = 'column',
): Position {
  const occupied = new Set(entries.map((e) => `${e.iconPosition.x},${e.iconPosition.y}`));
  const maxCols = Math.floor(window.innerWidth / GRID_CELL_SIZE);
  const maxRows = Math.floor((window.innerHeight - 44) / GRID_CELL_SIZE); // minus taskbar

  if (layout === 'column') {
    for (let col = 0; col < maxCols; col++) {
      for (let row = 0; row < maxRows; row++) {
        const x = col * GRID_CELL_SIZE;
        const y = row * GRID_CELL_SIZE;
        if (!occupied.has(`${x},${y}`)) return { x, y };
      }
    }
  } else {
    for (let row = 0; row < maxRows; row++) {
      for (let col = 0; col < maxCols; col++) {
        const x = col * GRID_CELL_SIZE;
        const y = row * GRID_CELL_SIZE;
        if (!occupied.has(`${x},${y}`)) return { x, y };
      }
    }
  }
  // Fallback
  return { x: entries.length * GRID_CELL_SIZE, y: 0 };
}

function snapToGrid(pos: Position): Position {
  return {
    x: Math.round(pos.x / GRID_CELL_SIZE) * GRID_CELL_SIZE,
    y: Math.round(pos.y / GRID_CELL_SIZE) * GRID_CELL_SIZE,
  };
}

export const useFileSystemStore = create<FileSystemStoreState>()(
  immer((set, get) => ({
    lookup: new Map(),
    selected: [],
    clipboard: [],
    renaming: null,

    getEntry: (id) => get().lookup.get(id),
    getChildren: (parentId) => {
      const parent = get().lookup.get(parentId);
      if (!parent || parent.type !== 'directory') return [];
      return (parent as FSDirectory).children
        .map((childId) => get().lookup.get(childId))
        .filter(Boolean) as FSEntry[];
    },
    getDesktopEntries: () => get().getChildren('desktop'),

    select: (id) => {
      set((state) => {
        if (!state.selected.includes(id)) state.selected.push(id);
      });
    },
    deselect: (id) => {
      set((state) => {
        state.selected = state.selected.filter((sid) => sid !== id);
      });
    },
    toggleSelect: (id) => {
      const isSelected = get().selected.includes(id);
      if (isSelected) get().deselect(id);
      else get().select(id);
    },
    selectAll: (parentId) => {
      const children = get().getChildren(parentId);
      set((state) => {
        state.selected = children.map((c) => c.id);
      });
    },
    clearSelection: () => {
      set((state) => {
        state.selected = [];
      });
    },
    isSelected: (id) => get().selected.includes(id),

    copySelected: () => {
      set((state) => {
        state.clipboard = [...state.selected];
      });
    },
    paste: (parentId) => {
      const clipboard = get().clipboard;
      for (const id of clipboard) {
        const entry = get().lookup.get(id);
        if (!entry || entry.disableCopy) continue;
        // Deep copy would go here — simplified for now
        // TODO: implement deep copy for directories
        if (entry.type === 'file') {
          get().createFile(parentId, `${entry.name} (copy)`, (entry as FSFile).extension, (entry as FSFile).content);
        } else if (entry.type === 'directory') {
          get().createDirectory(parentId, `${entry.name} (copy)`);
        }
      }
    },

    createDirectory: (parentId, name) => {
      const id = generateId();
      set((state) => {
        const parent = state.lookup.get(parentId) as FSDirectory | undefined;
        if (!parent || parent.type !== 'directory') return;

        const siblings = parent.children
          .map((cid) => state.lookup.get(cid))
          .filter(Boolean) as FSEntry[];

        const dir: FSDirectory = {
          id,
          name,
          parentId,
          type: 'directory',
          iconPosition: findEmptyGridPosition(siblings),
          createdAt: new Date(),
          updatedAt: new Date(),
          children: [],
          icon: '📁',
        };
        state.lookup.set(id, dir);
        parent.children.push(id);
      });
      return id;
    },

    createFile: (parentId, name, extension, content = '') => {
      const id = generateId();
      set((state) => {
        const parent = state.lookup.get(parentId) as FSDirectory | undefined;
        if (!parent || parent.type !== 'directory') return;

        const siblings = parent.children
          .map((cid) => state.lookup.get(cid))
          .filter(Boolean) as FSEntry[];

        const file: FSFile = {
          id,
          name,
          parentId,
          type: 'file',
          extension,
          content,
          iconPosition: findEmptyGridPosition(siblings),
          createdAt: new Date(),
          updatedAt: new Date(),
          icon: '📄',
        };
        state.lookup.set(id, file);
        parent.children.push(id);
      });
      return id;
    },

    deleteEntry: (id) => {
      set((state) => {
        const entry = state.lookup.get(id);
        if (!entry || entry.disableDelete) return;

        // Recursive delete for directories
        if (entry.type === 'directory') {
          const dir = entry as FSDirectory;
          for (const childId of dir.children) {
            // Recurse via direct mutation
            const child = state.lookup.get(childId);
            if (child) state.lookup.delete(childId);
          }
        }

        // Remove from parent
        if (entry.parentId) {
          const parent = state.lookup.get(entry.parentId) as FSDirectory | undefined;
          if (parent && parent.type === 'directory') {
            parent.children = parent.children.filter((cid) => cid !== id);
          }
        }

        state.lookup.delete(id);
        state.selected = state.selected.filter((sid) => sid !== id);
      });
    },

    renameEntry: (id, name) => {
      set((state) => {
        const entry = state.lookup.get(id);
        if (entry) {
          entry.name = name;
          entry.updatedAt = new Date();
        }
      });
    },

    moveEntry: (id, newParentId) => {
      set((state) => {
        const entry = state.lookup.get(id);
        if (!entry) return;

        // Remove from old parent
        if (entry.parentId) {
          const oldParent = state.lookup.get(entry.parentId) as FSDirectory | undefined;
          if (oldParent && oldParent.type === 'directory') {
            oldParent.children = oldParent.children.filter((cid) => cid !== id);
          }
        }

        // Add to new parent
        const newParent = state.lookup.get(newParentId) as FSDirectory | undefined;
        if (newParent && newParent.type === 'directory') {
          newParent.children.push(id);
          entry.parentId = newParentId;

          const siblings = newParent.children
            .map((cid) => state.lookup.get(cid))
            .filter((e) => e && e.id !== id) as FSEntry[];
          entry.iconPosition = findEmptyGridPosition(siblings);
        }
      });
    },

    setIconPosition: (id, pos) => {
      set((state) => {
        const entry = state.lookup.get(id);
        if (entry) entry.iconPosition = snapToGrid(pos);
      });
    },

    setRenaming: (id) => {
      set((state) => {
        state.renaming = id;
      });
    },

    initDesktop: (apps) => {
      set((state) => {
        // Create root and desktop directories
        const root: FSDirectory = {
          id: 'root',
          name: 'Root',
          parentId: null,
          type: 'directory',
          iconPosition: { x: 0, y: 0 },
          createdAt: new Date(),
          updatedAt: new Date(),
          children: ['desktop'],
          disableDelete: true,
        };

        const desktop: FSDirectory = {
          id: 'desktop',
          name: 'Desktop',
          parentId: 'root',
          type: 'directory',
          iconPosition: { x: 0, y: 0 },
          createdAt: new Date(),
          updatedAt: new Date(),
          children: [],
          disableDelete: true,
        };

        state.lookup.set('root', root);
        state.lookup.set('desktop', desktop);

        // Create app shortcuts on desktop
        let idx = 0;
        for (const [appId, app] of apps) {
          const shortcut: FSAppShortcut = {
            id: `shortcut-${appId}`,
            name: app.name,
            parentId: 'desktop',
            type: 'app-shortcut',
            appId,
            extension: '.app',
            iconPosition: { x: 0, y: idx * GRID_CELL_SIZE },
            createdAt: new Date(),
            updatedAt: new Date(),
            disableDelete: true,
            disableCopy: true,
            icon: app.icon,
          };
          state.lookup.set(shortcut.id, shortcut);
          desktop.children.push(shortcut.id);
          idx++;
        }

        // Create My Files directory
        const myFiles: FSDirectory = {
          id: generateId(),
          name: 'My Files',
          parentId: 'desktop',
          type: 'directory',
          iconPosition: { x: 0, y: idx * GRID_CELL_SIZE },
          createdAt: new Date(),
          updatedAt: new Date(),
          children: [],
          icon: '📁',
        };
        state.lookup.set(myFiles.id, myFiles);
        desktop.children.push(myFiles.id);
      });
    },
  })),
);
```

**Step 3: Commit**

```bash
git add web-ui/frontend/src/system/filesystem/types.ts web-ui/frontend/src/system/filesystem/store.ts
git commit -m "feat(claraos): add fileSystemStore with CRUD, selection, clipboard"
```

---

### Task 12: Create Desktop Icon component and Desktop view

**Files:**
- Create: `web-ui/frontend/src/system/filesystem/Icon.tsx`
- Create: `web-ui/frontend/src/system/filesystem/Desktop.tsx`

**Step 1: Create Icon component**

Create `web-ui/frontend/src/system/filesystem/Icon.tsx`:

```tsx
import { useCallback, useRef, useState } from 'react';
import { useFileSystemStore } from './store';
import { useWindowStore } from '../window/store';
import { useAppRegistry } from '../apps/registry';
import { COLORS, GRID_CELL_SIZE, ICON_SIZE } from '../theme/constants';
import type { FSEntry, FSAppShortcut } from './types';

interface IconProps {
  entry: FSEntry;
}

export function DesktopIcon({ entry }: IconProps) {
  const isSelected = useFileSystemStore((s) => s.isSelected(entry.id));
  const isRenaming = useFileSystemStore((s) => s.renaming === entry.id);
  const [renameValue, setRenameValue] = useState(entry.name);
  const inputRef = useRef<HTMLInputElement>(null);
  const { getApp } = useAppRegistry();

  const handleDoubleClick = useCallback(() => {
    if (entry.type === 'app-shortcut') {
      const shortcut = entry as FSAppShortcut;
      const app = getApp(shortcut.appId);
      if (app) {
        useWindowStore.getState().openWindow(
          app.singleton ? shortcut.appId : `${shortcut.appId}-${Date.now()}`,
          shortcut.appId,
          app.name,
          app.defaultWindowSize,
          app.icon,
        );
      }
    } else if (entry.type === 'directory') {
      // Open directory in a window
      useWindowStore.getState().openWindow(
        entry.id,
        'file-explorer',
        entry.name,
        { width: 500, height: 400 },
        '📁',
      );
    } else if (entry.type === 'file') {
      // Open file in text editor
      useWindowStore.getState().openWindow(
        entry.id,
        'text-editor',
        entry.name,
        { width: 600, height: 450 },
        '📄',
      );
    }
  }, [entry, getApp]);

  const handleClick = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      if (e.shiftKey || e.metaKey || e.ctrlKey) {
        useFileSystemStore.getState().toggleSelect(entry.id);
      } else {
        useFileSystemStore.getState().clearSelection();
        useFileSystemStore.getState().select(entry.id);
      }
    },
    [entry.id],
  );

  const handleRenameSubmit = () => {
    if (renameValue.trim() && renameValue !== entry.name) {
      useFileSystemStore.getState().renameEntry(entry.id, renameValue.trim());
    }
    useFileSystemStore.getState().setRenaming(null);
  };

  return (
    <div
      className="absolute flex flex-col items-center justify-center cursor-pointer select-none"
      style={{
        left: entry.iconPosition.x,
        top: entry.iconPosition.y,
        width: ICON_SIZE.width,
        height: ICON_SIZE.height,
      }}
      onClick={handleClick}
      onDoubleClick={handleDoubleClick}
    >
      {/* Icon */}
      <div
        className="flex items-center justify-center rounded-lg text-3xl"
        style={{
          width: 48,
          height: 48,
          backgroundColor: isSelected ? `${COLORS.primary}33` : 'transparent',
          border: isSelected ? `1px solid ${COLORS.primary}` : '1px solid transparent',
        }}
      >
        {entry.icon || (entry.type === 'directory' ? '📁' : '📄')}
      </div>

      {/* Label */}
      {isRenaming ? (
        <input
          ref={inputRef}
          className="text-xs text-center bg-black/50 border border-blue-400 rounded px-1 mt-1 outline-none"
          style={{ color: COLORS.text, width: ICON_SIZE.width - 8 }}
          value={renameValue}
          onChange={(e) => setRenameValue(e.target.value)}
          onBlur={handleRenameSubmit}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleRenameSubmit();
            if (e.key === 'Escape') useFileSystemStore.getState().setRenaming(null);
          }}
          autoFocus
        />
      ) : (
        <span
          className="text-xs text-center mt-1 leading-tight"
          style={{
            color: COLORS.text,
            maxWidth: ICON_SIZE.width - 4,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            textShadow: '0 1px 2px rgba(0,0,0,0.8)',
          }}
        >
          {entry.name}
        </span>
      )}
    </div>
  );
}
```

**Step 2: Create Desktop component**

Create `web-ui/frontend/src/system/filesystem/Desktop.tsx`:

```tsx
import { useEffect } from 'react';
import { useFileSystemStore } from './store';
import { DesktopIcon } from './Icon';
import { TASKBAR_HEIGHT } from '../theme/constants';
import { defaultApps } from '../apps/defaultApps';

export function Desktop() {
  const desktopEntries = useFileSystemStore((s) => s.getDesktopEntries());

  // Initialize desktop on mount
  useEffect(() => {
    const lookup = useFileSystemStore.getState().lookup;
    if (lookup.size === 0) {
      useFileSystemStore.getState().initDesktop(defaultApps);
    }
  }, []);

  const handleDesktopClick = () => {
    useFileSystemStore.getState().clearSelection();
  };

  return (
    <div
      className="absolute inset-0 p-4"
      style={{ paddingBottom: TASKBAR_HEIGHT }}
      onClick={handleDesktopClick}
      onContextMenu={(e) => {
        e.preventDefault();
        // Context menu will be added in Task 13
      }}
    >
      {desktopEntries.map((entry) => (
        <DesktopIcon key={entry.id} entry={entry} />
      ))}
    </div>
  );
}
```

**Step 3: Update App.tsx to include Desktop**

In `web-ui/frontend/src/App.tsx`, add the Desktop import and render it inside the Wallpaper alongside WindowSystem.

Add import:
```typescript
import { Desktop } from './system/filesystem/Desktop';
```

In `ClaraOSDesktop`, update Wallpaper children:
```tsx
<Wallpaper>
  <Desktop />
  <WindowSystem />
</Wallpaper>
```

**Step 4: Verify**

Run: `cd web-ui/frontend && npm run dev`
Expected: Desktop shows app shortcut icons (Clara, Settings) and My Files folder. Double-clicking opens windows.

**Step 5: Commit**

```bash
git add web-ui/frontend/src/system/filesystem/Icon.tsx web-ui/frontend/src/system/filesystem/Desktop.tsx web-ui/frontend/src/App.tsx
git commit -m "feat(claraos): add Desktop with icons and file system initialization"
```

---

### Task 13: Create context menu system

**Files:**
- Create: `web-ui/frontend/src/system/contextmenu/types.ts`
- Create: `web-ui/frontend/src/system/contextmenu/store.ts`
- Create: `web-ui/frontend/src/system/contextmenu/ContextMenu.tsx`
- Create: `web-ui/frontend/src/system/contextmenu/menuBuilder.ts`

**Step 1: Create context menu types and store**

Create `web-ui/frontend/src/system/contextmenu/types.ts`:

```typescript
export interface ContextMenuItem {
  label: string;
  action: () => void;
  disabled?: boolean;
  dividerAfter?: boolean;
}

export interface ContextMenuState {
  items: ContextMenuItem[];
  position: { x: number; y: number };
  visible: boolean;
}
```

Create `web-ui/frontend/src/system/contextmenu/store.ts`:

```typescript
import { create } from 'zustand';
import type { ContextMenuItem, ContextMenuState } from './types';

interface ContextMenuStore extends ContextMenuState {
  show: (items: ContextMenuItem[], position: { x: number; y: number }) => void;
  hide: () => void;
}

export const useContextMenuStore = create<ContextMenuStore>((set) => ({
  items: [],
  position: { x: 0, y: 0 },
  visible: false,
  show: (items, position) => set({ items, position, visible: true }),
  hide: () => set({ visible: false }),
}));
```

**Step 2: Create menu builder**

Create `web-ui/frontend/src/system/contextmenu/menuBuilder.ts`:

```typescript
import type { ContextMenuItem } from './types';
import { useFileSystemStore } from '../filesystem/store';

export function buildDesktopMenu(parentId: string): ContextMenuItem[] {
  return [
    {
      label: 'New Folder',
      action: () => useFileSystemStore.getState().createDirectory(parentId, 'New Folder'),
    },
    {
      label: 'New Text File',
      action: () => useFileSystemStore.getState().createFile(parentId, 'New File', '.txt'),
      dividerAfter: true,
    },
    {
      label: 'Paste',
      action: () => useFileSystemStore.getState().paste(parentId),
      disabled: useFileSystemStore.getState().clipboard.length === 0,
      dividerAfter: true,
    },
    {
      label: 'Select All',
      action: () => useFileSystemStore.getState().selectAll(parentId),
    },
  ];
}

export function buildIconMenu(entryId: string): ContextMenuItem[] {
  const entry = useFileSystemStore.getState().getEntry(entryId);
  if (!entry) return [];

  return [
    {
      label: 'Open',
      action: () => {
        // Trigger double-click behavior — handled by the Icon component
        const el = document.querySelector(`[data-entry-id="${entryId}"]`);
        if (el) (el as HTMLElement).dispatchEvent(new MouseEvent('dblclick', { bubbles: true }));
      },
      dividerAfter: true,
    },
    {
      label: 'Copy',
      action: () => {
        useFileSystemStore.getState().clearSelection();
        useFileSystemStore.getState().select(entryId);
        useFileSystemStore.getState().copySelected();
      },
      disabled: entry.disableCopy,
    },
    {
      label: 'Rename',
      action: () => useFileSystemStore.getState().setRenaming(entryId),
      dividerAfter: true,
    },
    {
      label: 'Delete',
      action: () => useFileSystemStore.getState().deleteEntry(entryId),
      disabled: entry.disableDelete,
    },
  ];
}
```

**Step 3: Create ContextMenu component**

Create `web-ui/frontend/src/system/contextmenu/ContextMenu.tsx`:

```tsx
import { useEffect, useRef } from 'react';
import { useContextMenuStore } from './store';
import { COLORS, CONTEXT_MENU_WIDTH, CONTEXT_MENU_ITEM_HEIGHT } from '../theme/constants';

export function ContextMenu() {
  const { items, position, visible, hide } = useContextMenuStore();
  const ref = useRef<HTMLUListElement>(null);

  useEffect(() => {
    if (!visible) return;
    const handler = () => hide();
    window.addEventListener('click', handler);
    window.addEventListener('contextmenu', handler);
    return () => {
      window.removeEventListener('click', handler);
      window.removeEventListener('contextmenu', handler);
    };
  }, [visible, hide]);

  if (!visible || items.length === 0) return null;

  // Clamp position to viewport
  const menuHeight = items.length * CONTEXT_MENU_ITEM_HEIGHT + 8;
  const x = Math.min(position.x, window.innerWidth - CONTEXT_MENU_WIDTH - 4);
  const y = Math.min(position.y, window.innerHeight - menuHeight - 4);

  return (
    <ul
      ref={ref}
      className="fixed py-1 rounded-lg shadow-xl"
      style={{
        left: x,
        top: y,
        width: CONTEXT_MENU_WIDTH,
        backgroundColor: COLORS.surfaceLight,
        border: `1px solid ${COLORS.surfaceLighter}`,
        zIndex: 99999,
      }}
    >
      {items.map((item, idx) => (
        <li key={idx}>
          <button
            className="w-full text-left text-sm px-3 py-1.5 transition-colors"
            style={{
              color: item.disabled ? COLORS.textDim : COLORS.text,
              cursor: item.disabled ? 'default' : 'pointer',
              height: CONTEXT_MENU_ITEM_HEIGHT,
            }}
            disabled={item.disabled}
            onClick={() => {
              if (!item.disabled) {
                item.action();
                hide();
              }
            }}
            onMouseEnter={(e) => {
              if (!item.disabled) {
                (e.currentTarget as HTMLElement).style.backgroundColor = `${COLORS.primary}66`;
              }
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent';
            }}
          >
            {item.label}
          </button>
          {item.dividerAfter && (
            <hr style={{ borderColor: COLORS.surfaceLighter, margin: '2px 8px' }} />
          )}
        </li>
      ))}
    </ul>
  );
}
```

**Step 4: Wire context menus into Desktop and Icon**

Update `web-ui/frontend/src/system/filesystem/Desktop.tsx` — add context menu trigger on right-click:

```tsx
// Add imports at top:
import { useContextMenuStore } from '../contextmenu/store';
import { buildDesktopMenu } from '../contextmenu/menuBuilder';

// Replace the onContextMenu handler:
onContextMenu={(e) => {
  e.preventDefault();
  useContextMenuStore.getState().show(
    buildDesktopMenu('desktop'),
    { x: e.clientX, y: e.clientY },
  );
}}
```

Update `web-ui/frontend/src/system/filesystem/Icon.tsx` — add right-click on icons:

```tsx
// Add imports:
import { useContextMenuStore } from '../contextmenu/store';
import { buildIconMenu } from '../contextmenu/menuBuilder';

// Add data attribute to root div:
data-entry-id={entry.id}

// Add onContextMenu to root div:
onContextMenu={(e) => {
  e.preventDefault();
  e.stopPropagation();
  useFileSystemStore.getState().clearSelection();
  useFileSystemStore.getState().select(entry.id);
  useContextMenuStore.getState().show(
    buildIconMenu(entry.id),
    { x: e.clientX, y: e.clientY },
  );
}}
```

Update `web-ui/frontend/src/App.tsx` — add ContextMenu to the render:

```tsx
import { ContextMenu } from './system/contextmenu/ContextMenu';

// Inside ClaraOSDesktop, after Taskbar:
<ContextMenu />
```

**Step 5: Verify**

Run: `cd web-ui/frontend && npm run dev`
Expected: Right-click desktop shows "New Folder", "New Text File", "Paste", "Select All". Right-click icon shows "Open", "Copy", "Rename", "Delete".

**Step 6: Commit**

```bash
git add web-ui/frontend/src/system/contextmenu/ web-ui/frontend/src/system/filesystem/Desktop.tsx web-ui/frontend/src/system/filesystem/Icon.tsx web-ui/frontend/src/App.tsx
git commit -m "feat(claraos): add context menu system with desktop and icon menus"
```

---

## Phase 3: Migrate Existing Apps Into ClaraOS Windows

### Task 14: Register all current apps in the app registry

**Files:**
- Modify: `web-ui/frontend/src/system/apps/defaultApps.ts`

**Step 1: Update defaultApps with all real app definitions**

Replace the placeholder defaultApps with lazy imports of the real page components. Each page component needs a thin wrapper to accept `{ windowId: string }` instead of its current props.

Update `web-ui/frontend/src/system/apps/defaultApps.ts`:

```typescript
import { lazy } from 'react';
import type { AppDefinition } from './registry';

export const defaultApps = new Map<string, AppDefinition>([
  ['clara-chat', {
    id: 'clara-chat',
    name: 'Clara',
    icon: '💬',
    defaultWindowSize: { width: 700, height: 550 },
    component: lazy(() => import('../../apps/clara-chat')),
    singleton: true,
    closeBehavior: 'minimize',
  }],
  ['knowledge-base', {
    id: 'knowledge-base',
    name: 'Knowledge Base',
    icon: '🧠',
    defaultWindowSize: { width: 800, height: 550 },
    component: lazy(() => import('../../apps/knowledge-base')),
    singleton: true,
  }],
  ['graph-explorer', {
    id: 'graph-explorer',
    name: 'Graph Explorer',
    icon: '🕸️',
    defaultWindowSize: { width: 900, height: 600 },
    component: lazy(() => import('../../apps/graph-explorer')),
    singleton: true,
  }],
  ['intentions', {
    id: 'intentions',
    name: 'Intentions',
    icon: '🎯',
    defaultWindowSize: { width: 650, height: 500 },
    component: lazy(() => import('../../apps/intentions')),
    singleton: true,
  }],
  ['settings', {
    id: 'settings',
    name: 'Settings',
    icon: '⚙️',
    defaultWindowSize: { width: 500, height: 400 },
    component: lazy(() => import('../../apps/settings')),
    singleton: true,
  }],
  ['admin', {
    id: 'admin',
    name: 'Admin',
    icon: '🛡️',
    defaultWindowSize: { width: 700, height: 500 },
    component: lazy(() => import('../../apps/admin')),
    singleton: true,
  }],
  ['blackjack', {
    id: 'blackjack',
    name: 'Blackjack',
    icon: '🃏',
    defaultWindowSize: { width: 800, height: 600 },
    component: lazy(() => import('../../apps/blackjack')),
  }],
  ['checkers', {
    id: 'checkers',
    name: 'Checkers',
    icon: '♟️',
    defaultWindowSize: { width: 700, height: 650 },
    component: lazy(() => import('../../apps/checkers')),
  }],
  ['game-lobby', {
    id: 'game-lobby',
    name: 'Games',
    icon: '🎮',
    defaultWindowSize: { width: 650, height: 500 },
    component: lazy(() => import('../../apps/game-lobby')),
    singleton: true,
  }],
  ['text-editor', {
    id: 'text-editor',
    name: 'Text Editor',
    icon: '📝',
    defaultWindowSize: { width: 600, height: 450 },
    component: lazy(() => import('../../apps/text-editor')),
  }],
]);
```

**Step 2: Commit**

```bash
git add web-ui/frontend/src/system/apps/defaultApps.ts
git commit -m "feat(claraos): register all app definitions in app registry"
```

---

### Task 15: Create Clara Chat app wrapper

**Files:**
- Create: `web-ui/frontend/src/apps/clara-chat/index.tsx`

**Step 1: Create Clara Chat app**

This wraps the existing chat components (`Thread`, `ChatRuntimeProvider`, `chatStore`) into a ClaraOS window app.

Create `web-ui/frontend/src/apps/clara-chat/index.tsx`:

```tsx
import { useEffect } from 'react';
import { useChatStore } from '../../stores/chatStore';
import { useAuth } from '../../auth/AuthProvider';
import { ChatRuntimeProvider } from '../../components/chat/ChatRuntimeProvider';
import { Thread } from '../../components/assistant-ui/thread';

export default function ClaraChatApp({ windowId }: { windowId: string }) {
  const { user } = useAuth();
  const connected = useChatStore((s) => s.connected);

  // Connect WebSocket when app mounts
  useEffect(() => {
    if (user && !connected) {
      const token = sessionStorage.getItem('token') || '';
      useChatStore.getState().connect(token);
    }
    return () => {
      // Don't disconnect on unmount — Clara chat persists
    };
  }, [user, connected]);

  if (!user) return null;

  return (
    <ChatRuntimeProvider>
      <div className="h-full flex flex-col">
        <Thread />
      </div>
    </ChatRuntimeProvider>
  );
}
```

**Step 2: Verify**

Run: `cd web-ui/frontend && npm run dev`
Expected: Clara Chat window opens on boot with the real chat UI (Thread component). May need backend running to fully test.

**Step 3: Commit**

```bash
git add web-ui/frontend/src/apps/clara-chat/index.tsx
git commit -m "feat(claraos): create Clara Chat app wrapper"
```

---

### Task 16: Create remaining app wrappers

Each existing page gets a thin wrapper in `src/apps/`. These are straightforward — wrap the existing page component, pass no props (the pages already fetch their own data).

**Files:**
- Create: `web-ui/frontend/src/apps/knowledge-base/index.tsx`
- Create: `web-ui/frontend/src/apps/graph-explorer/index.tsx`
- Create: `web-ui/frontend/src/apps/intentions/index.tsx`
- Create: `web-ui/frontend/src/apps/settings/index.tsx`
- Create: `web-ui/frontend/src/apps/admin/index.tsx`
- Create: `web-ui/frontend/src/apps/blackjack/index.tsx`
- Create: `web-ui/frontend/src/apps/checkers/index.tsx`
- Create: `web-ui/frontend/src/apps/game-lobby/index.tsx`
- Create: `web-ui/frontend/src/apps/text-editor/index.tsx`

**Step 1: Create each app wrapper**

Each follows this pattern:

```tsx
// web-ui/frontend/src/apps/knowledge-base/index.tsx
import KnowledgeBasePage from '../../pages/KnowledgeBase';

export default function KnowledgeBaseApp({ windowId }: { windowId: string }) {
  return <KnowledgeBasePage />;
}
```

Repeat for all apps. The game apps need special handling since they receive a `game` prop from the router — the game-lobby app will handle game creation and opening game windows.

For `text-editor/index.tsx`, create a minimal text editor that reads from fileSystemStore:

```tsx
// web-ui/frontend/src/apps/text-editor/index.tsx
import { useState, useEffect } from 'react';
import { useFileSystemStore } from '../../system/filesystem/store';
import { COLORS } from '../../system/theme/constants';
import type { FSFile } from '../../system/filesystem/types';

export default function TextEditorApp({ windowId }: { windowId: string }) {
  const entry = useFileSystemStore((s) => s.getEntry(windowId)) as FSFile | undefined;
  const [content, setContent] = useState(entry?.content ?? '');

  useEffect(() => {
    if (entry?.type === 'file') setContent(entry.content);
  }, [entry]);

  if (!entry || entry.type !== 'file') {
    return (
      <div className="h-full flex items-center justify-center" style={{ color: COLORS.textMuted }}>
        No file selected
      </div>
    );
  }

  return (
    <textarea
      className="w-full h-full p-4 resize-none outline-none font-mono text-sm"
      style={{
        backgroundColor: COLORS.surface,
        color: COLORS.text,
        border: 'none',
      }}
      value={content}
      onChange={(e) => {
        setContent(e.target.value);
        // TODO: debounce save to fileSystemStore
      }}
      onBlur={() => {
        // Save on blur
        if (entry.type === 'file') {
          useFileSystemStore.getState().renameEntry(entry.id, entry.name);
          // Need a setContent action on store — add in future task
        }
      }}
    />
  );
}
```

For `game-lobby/index.tsx`, the lobby opens game windows:

```tsx
// web-ui/frontend/src/apps/game-lobby/index.tsx
import Lobby from '../../pages/Lobby';

export default function GameLobbyApp({ windowId }: { windowId: string }) {
  // TODO: Override game navigation to open new windows instead of router navigation
  return <Lobby />;
}
```

**Step 2: Verify build**

Run: `cd web-ui/frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add web-ui/frontend/src/apps/
git commit -m "feat(claraos): create all app wrappers for windowed rendering"
```

---

### Task 17: Update defaultApps desktop layout for all apps

**Files:**
- Modify: `web-ui/frontend/src/system/filesystem/store.ts` (initDesktop method)

**Step 1: Update initDesktop to create a Games folder**

In the `initDesktop` method, after creating individual app shortcuts, add a Games folder containing Blackjack, Checkers, and Game Lobby shortcuts. The desktop should have: Clara, Knowledge Base, Graph Explorer, Intentions, Settings, Games (folder), My Files.

Admin shortcut should only appear for admin users — handle this by passing user role to initDesktop or conditionally creating it.

For now, create all shortcuts and we'll conditionally show admin later.

**Step 2: Commit**

```bash
git add web-ui/frontend/src/system/filesystem/store.ts
git commit -m "feat(claraos): organize desktop with Games folder"
```

---

## Phase 4: Remove Old SPA Routes and Clean Up

### Task 18: Remove old SPA infrastructure

**Files:**
- Remove: `web-ui/frontend/src/components/layout/AppLayout.tsx`
- Remove: `web-ui/frontend/src/components/layout/UnifiedSidebar.tsx`
- Remove: `web-ui/frontend/src/hooks/useWebSocket.ts` (WebSocket now managed by claraStore/chatStore)
- Keep: All pages (they're now used by app wrappers)
- Keep: All components (used by pages)
- Keep: All stores (used by apps)
- Keep: API client and auth

**Step 1: Remove unused layout files**

Delete `AppLayout.tsx` and `UnifiedSidebar.tsx` — these are the old SPA shell that's replaced by ClaraOS desktop.

**Step 2: Clean up unused router imports**

Ensure `App.tsx` only imports what's needed for auth routes + ClaraOS desktop.

**Step 3: Verify build**

Run: `cd web-ui/frontend && npm run build`
Expected: Build succeeds with no errors

**Step 4: Commit**

```bash
git add -A
git commit -m "refactor(claraos): remove old SPA layout, sidebar, and router shell"
```

---

## Phase 5: Rails Filesystem Endpoints

### Task 19: Add FileSystemEntry model to Rails

**Files:**
- Create migration: `web-ui/backend/db/migrate/..._create_file_system_entries.rb`
- Create model: `web-ui/backend/app/models/file_system_entry.rb`

**Step 1: Generate migration**

```bash
cd web-ui/backend && rails generate migration CreateFileSystemEntries
```

Migration content:
```ruby
class CreateFileSystemEntries < ActiveRecord::Migration[8.1]
  def change
    create_table :file_system_entries, id: :uuid do |t|
      t.references :user, null: false, foreign_key: true
      t.string :name, null: false
      t.uuid :parent_id
      t.string :entry_type, null: false  # 'file', 'directory', 'app-shortcut'
      t.string :extension
      t.string :app_id
      t.text :content
      t.jsonb :icon_position, default: { x: 0, y: 0 }
      t.string :icon
      t.boolean :disable_delete, default: false
      t.boolean :disable_copy, default: false
      t.timestamps
    end

    add_index :file_system_entries, [:user_id, :parent_id]
    add_index :file_system_entries, [:user_id, :name, :parent_id], unique: true
    add_foreign_key :file_system_entries, :file_system_entries, column: :parent_id
  end
end
```

**Step 2: Create model**

```ruby
# web-ui/backend/app/models/file_system_entry.rb
class FileSystemEntry < ApplicationRecord
  belongs_to :user
  belongs_to :parent, class_name: 'FileSystemEntry', optional: true
  has_many :children, class_name: 'FileSystemEntry', foreign_key: :parent_id, dependent: :destroy

  validates :name, presence: true
  validates :entry_type, inclusion: { in: %w[file directory app-shortcut] }
  validates :name, uniqueness: { scope: [:user_id, :parent_id] }

  scope :for_user, ->(user) { where(user: user) }
end
```

**Step 3: Run migration**

```bash
cd web-ui/backend && rails db:migrate
```

**Step 4: Commit**

```bash
cd web-ui/backend && git add db/migrate/ app/models/file_system_entry.rb db/schema.rb
git commit -m "feat(claraos): add FileSystemEntry model and migration"
```

---

### Task 20: Add filesystem controller and routes

**Files:**
- Create: `web-ui/backend/app/controllers/api/v1/filesystem_controller.rb`
- Modify: `web-ui/backend/config/routes.rb`

**Step 1: Create controller**

```ruby
# web-ui/backend/app/controllers/api/v1/filesystem_controller.rb
module Api
  module V1
    class FilesystemController < ApplicationController
      def tree
        entries = FileSystemEntry.for_user(current_user).order(:created_at)
        render json: entries.map { |e| serialize(e) }
      end

      def create
        entry = current_user.file_system_entries.build(entry_params)
        if entry.save
          render json: serialize(entry), status: :created
        else
          render json: { errors: entry.errors.full_messages }, status: :unprocessable_entity
        end
      end

      def update
        entry = current_user.file_system_entries.find(params[:id])
        if entry.update(entry_params)
          render json: serialize(entry)
        else
          render json: { errors: entry.errors.full_messages }, status: :unprocessable_entity
        end
      end

      def destroy
        entry = current_user.file_system_entries.find(params[:id])
        entry.destroy!
        head :no_content
      end

      private

      def entry_params
        params.permit(:name, :parent_id, :entry_type, :extension, :app_id,
                       :content, :icon, :disable_delete, :disable_copy,
                       icon_position: [:x, :y])
      end

      def serialize(entry)
        {
          id: entry.id,
          name: entry.name,
          parent_id: entry.parent_id,
          type: entry.entry_type,
          extension: entry.extension,
          app_id: entry.app_id,
          content: entry.content,
          icon_position: entry.icon_position,
          icon: entry.icon,
          disable_delete: entry.disable_delete,
          disable_copy: entry.disable_copy,
          children: entry.children.pluck(:id),
          created_at: entry.created_at,
          updated_at: entry.updated_at,
        }
      end
    end
  end
end
```

**Step 2: Add routes**

In `web-ui/backend/config/routes.rb`, inside the `namespace :api do namespace :v1 do` block, add:

```ruby
get 'filesystem/tree', to: 'filesystem#tree'
resources :filesystem, only: [:create, :update, :destroy]
```

**Step 3: Add association to User model**

In `web-ui/backend/app/models/user.rb`, add:

```ruby
has_many :file_system_entries, dependent: :destroy
```

**Step 4: Commit**

```bash
cd web-ui/backend && git add app/controllers/api/v1/filesystem_controller.rb config/routes.rb app/models/user.rb
git commit -m "feat(claraos): add filesystem CRUD endpoints"
```

---

### Task 21: Add filesystem API to frontend client

**Files:**
- Modify: `web-ui/frontend/src/api/client.ts`

**Step 1: Add filesystem namespace to API client**

Add a new `filesystem` namespace to the API client:

```typescript
filesystem: {
  tree: () => request<FSEntryResponse[]>('/filesystem/tree'),
  create: (body: CreateFSEntryBody) => request<FSEntryResponse>('/filesystem', { method: 'POST', body: JSON.stringify(body) }),
  update: (id: string, body: UpdateFSEntryBody) => request<FSEntryResponse>(`/filesystem/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  delete: (id: string) => request<void>(`/filesystem/${id}`, { method: 'DELETE' }),
},
```

Also add the relevant TypeScript interfaces for the request/response types.

**Step 2: Commit**

```bash
git add web-ui/frontend/src/api/client.ts
git commit -m "feat(claraos): add filesystem API client methods"
```

---

### Task 22: Connect fileSystemStore to backend persistence

**Files:**
- Modify: `web-ui/frontend/src/system/filesystem/store.ts`

**Step 1: Add API calls to store mutations**

Add optimistic update pattern: mutate store immediately, then fire API call. On error, revert.

Key changes:
- `initDesktop` → first try `api.filesystem.tree()`. If empty (new user), create defaults and POST each to API.
- `createDirectory` / `createFile` → POST to API after local mutation
- `deleteEntry` → DELETE from API after local mutation
- `renameEntry` → PUT to API after local mutation
- `moveEntry` → PUT to API after local mutation

**Step 2: Commit**

```bash
git add web-ui/frontend/src/system/filesystem/store.ts
git commit -m "feat(claraos): connect filesystem store to Rails API persistence"
```

---

## Phase 6: Polish and Integration

### Task 23: Add keyboard shortcuts (GlobalEvents)

**Files:**
- Create: `web-ui/frontend/src/system/GlobalEvents.tsx`

**Step 1: Create GlobalEvents component**

Handles:
- `Cmd/Ctrl+A` → select all icons on desktop
- `Cmd/Ctrl+C` → copy selected
- `Cmd/Ctrl+V` → paste
- `Delete/Backspace` → delete selected
- `F2` → rename selected
- `Escape` → clear selection, close context menu

**Step 2: Wire into App.tsx**

**Step 3: Commit**

```bash
git add web-ui/frontend/src/system/GlobalEvents.tsx web-ui/frontend/src/App.tsx
git commit -m "feat(claraos): add keyboard shortcuts for file operations"
```

---

### Task 24: Add window header for maximized windows

**Files:**
- Create: `web-ui/frontend/src/system/window/MaximizedWindowHeader.tsx`

When a window is maximized, the normal header is hidden (per bogdan-os pattern). We need a special header that appears at the top of the viewport on mouse hover.

**Step 1: Create MaximizedWindowHeader**

Shows on mouse hover near top of screen when any window is maximized. Contains the title + Windows-style buttons.

**Step 2: Wire into App.tsx**

**Step 3: Commit**

```bash
git add web-ui/frontend/src/system/window/MaximizedWindowHeader.tsx web-ui/frontend/src/App.tsx
git commit -m "feat(claraos): add maximized window header on hover"
```

---

### Task 25: Clara avatar integration

**Files:**
- Add exported PNG/WebP versions of Clara's avatar to `web-ui/frontend/public/clara/`
- Modify: `web-ui/frontend/src/system/taskbar/Taskbar.tsx` (Clara icon in start area)

**Prerequisite:** Joshua needs to export the PSD files to PNG/WebP format.

**Step 1: Ask Joshua for exported avatar files**

The PSDs are at `/Users/heidornj/Code/art/FREE_clara_original_normal/`. Need PNG exports at multiple sizes:
- 32x64 (taskbar icon)
- 64x128 (window icon / desktop)
- 256x512 (boot screen)

**Step 2: Place in public/clara/**

**Step 3: Update Taskbar to show Clara avatar instead of "C" text**

**Step 4: Commit**

```bash
git add web-ui/frontend/public/clara/ web-ui/frontend/src/system/taskbar/Taskbar.tsx
git commit -m "feat(claraos): integrate Clara avatar into taskbar"
```

---

### Task 26: Final cleanup and verification

**Files:**
- Various cleanup across frontend

**Step 1: Remove dead code**

- Delete any unused old page imports
- Remove React Router routes that are no longer needed (games/:id, knowledge, etc.)
- Clean up unused CSS

**Step 2: Verify full build**

```bash
cd web-ui/frontend && npm run build
```

**Step 3: Manual testing checklist**

- [ ] Desktop renders with wallpaper gradient
- [ ] App shortcut icons appear on desktop
- [ ] Double-click opens windows
- [ ] Windows can be moved by dragging header
- [ ] Windows can be resized from edges/corners
- [ ] Minimize/maximize/close buttons work
- [ ] Clara Chat opens on boot, close → minimize
- [ ] Taskbar shows open windows
- [ ] Click taskbar entry focuses/minimizes window
- [ ] Right-click desktop → context menu
- [ ] Right-click icon → context menu
- [ ] New Folder creates folder on desktop
- [ ] Rename works (F2 or right-click)
- [ ] Delete works (right-click)
- [ ] Multiple windows stack correctly (z-index)
- [ ] Clara Chat connects and streams messages

**Step 4: Final commit**

```bash
git add -A
git commit -m "refactor(claraos): final cleanup and dead code removal"
```

---

## Execution Notes

- **Phase 1 (Tasks 1-10)**: Foundation. Must be done first and sequentially. End result: working window system with placeholder apps on a desktop wallpaper.
- **Phase 2 (Tasks 11-13)**: File system and context menus. Adds the "OS" feel. Sequential.
- **Phase 3 (Tasks 14-17)**: App migration. Can partially parallelize — each app wrapper is independent.
- **Phase 4 (Task 18)**: Cleanup. Quick pass after Phase 3.
- **Phase 5 (Tasks 19-22)**: Backend persistence. Can run in parallel with Phase 3-4 frontend work (different directories).
- **Phase 6 (Tasks 23-26)**: Polish. Order doesn't matter much.

**Total tasks: 26**
**Dependencies between phases are linear. Within phases, some tasks can parallelize.**
