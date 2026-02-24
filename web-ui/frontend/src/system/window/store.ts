import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import { DEFAULT_WINDOW_SIZE, TASKBAR_HEIGHT, TOP_PANEL_HEIGHT } from '../theme/constants';
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
  const usableHeight = window.innerHeight - TOP_PANEL_HEIGHT - TASKBAR_HEIGHT;
  return {
    x: Math.max(0, (window.innerWidth - size.width) / 2 + randomOffset()),
    y: Math.max(TOP_PANEL_HEIGHT, TOP_PANEL_HEIGHT + (usableHeight - size.height) / 2 + randomOffset()),
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
      return {
        width: Math.min(win.size.width, window.innerWidth),
        height: Math.min(win.size.height, window.innerHeight - TOP_PANEL_HEIGHT - TASKBAR_HEIGHT),
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
          transformScale: 0,
          contentOpacity: 0,
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
        win.position = { x: 0, y: TOP_PANEL_HEIGHT };
        win.size = { width: window.innerWidth, height: window.innerHeight - TOP_PANEL_HEIGHT - TASKBAR_HEIGHT };
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
