import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import { GRID_CELL_SIZE, TASKBAR_HEIGHT } from '../theme/constants';
import type { AppDefinition } from '../apps/registry';
import type {
  EntryId,
  FSAppShortcut,
  FSDirectory,
  FSEntry,
  FSFile,
  Position,
} from './types';

// --- Helpers ---

function snapToGrid(pos: Position): Position {
  return {
    x: Math.round(pos.x / GRID_CELL_SIZE) * GRID_CELL_SIZE,
    y: Math.round(pos.y / GRID_CELL_SIZE) * GRID_CELL_SIZE,
  };
}

/** Find the first empty grid cell, scanning column-major (top-to-bottom, then left-to-right). */
function findEmptyGridPosition(
  occupiedPositions: Position[],
  layout: { columns: number; rows: number },
): Position {
  const occupied = new Set(
    occupiedPositions.map((p) => `${p.x},${p.y}`),
  );

  for (let col = 0; col < layout.columns; col++) {
    for (let row = 0; row < layout.rows; row++) {
      const x = col * GRID_CELL_SIZE;
      const y = row * GRID_CELL_SIZE;
      if (!occupied.has(`${x},${y}`)) {
        return { x, y };
      }
    }
  }

  // Fallback: place beyond current grid
  return {
    x: layout.columns * GRID_CELL_SIZE,
    y: 0,
  };
}

function getDesktopLayout(): { columns: number; rows: number } {
  const availableHeight = window.innerHeight - TASKBAR_HEIGHT;
  return {
    columns: Math.floor(window.innerWidth / GRID_CELL_SIZE),
    rows: Math.floor(availableHeight / GRID_CELL_SIZE),
  };
}

function now(): Date {
  return new Date();
}

// --- Store ---

interface FileSystemStoreState {
  lookup: Map<EntryId, FSEntry>;
  selected: EntryId[];
  clipboard: EntryId[];
  renaming: EntryId | null;

  // Getters
  getEntry: (id: EntryId) => FSEntry | undefined;
  getChildren: (parentId: EntryId) => FSEntry[];
  getDesktopEntries: () => FSEntry[];
  isSelected: (id: EntryId) => boolean;

  // Selection
  select: (id: EntryId) => void;
  deselect: (id: EntryId) => void;
  toggleSelect: (id: EntryId) => void;
  selectAll: (parentId: EntryId) => void;
  clearSelection: () => void;

  // Clipboard
  copySelected: () => void;
  paste: (parentId: EntryId) => void;

  // File operations
  createDirectory: (parentId: EntryId, name: string) => EntryId;
  createFile: (
    parentId: EntryId,
    name: string,
    extension: string,
    content?: string,
  ) => EntryId;
  deleteEntry: (id: EntryId) => void;
  renameEntry: (id: EntryId, name: string) => void;
  moveEntry: (id: EntryId, newParentId: EntryId) => void;
  setIconPosition: (id: EntryId, pos: Position) => void;
  setRenaming: (id: EntryId | null) => void;

  // Init
  initDesktop: (apps: Map<string, AppDefinition>) => void;
}

export const useFileSystemStore = create<FileSystemStoreState>()(
  immer((set, get) => ({
    lookup: new Map(),
    selected: [],
    clipboard: [],
    renaming: null,

    // --- Getters ---

    getEntry: (id) => get().lookup.get(id),

    getChildren: (parentId) => {
      const parent = get().lookup.get(parentId);
      if (!parent || parent.type !== 'directory') return [];
      return (parent as FSDirectory).children
        .map((cid) => get().lookup.get(cid))
        .filter((e): e is FSEntry => e !== undefined);
    },

    getDesktopEntries: () => {
      const desktop = get().lookup.get('desktop');
      if (!desktop || desktop.type !== 'directory') return [];
      return (desktop as FSDirectory).children
        .map((cid) => get().lookup.get(cid))
        .filter((e): e is FSEntry => e !== undefined);
    },

    isSelected: (id) => get().selected.includes(id),

    // --- Selection ---

    select: (id) => {
      set((state) => {
        if (!state.selected.includes(id)) {
          state.selected = [id];
        }
      });
    },

    deselect: (id) => {
      set((state) => {
        state.selected = state.selected.filter((sid) => sid !== id);
      });
    },

    toggleSelect: (id) => {
      set((state) => {
        const idx = state.selected.indexOf(id);
        if (idx >= 0) {
          state.selected.splice(idx, 1);
        } else {
          state.selected.push(id);
        }
      });
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

    // --- Clipboard ---

    copySelected: () => {
      set((state) => {
        state.clipboard = [...state.selected].filter((id) => {
          const entry = state.lookup.get(id);
          return entry && !entry.disableCopy;
        });
      });
    },

    paste: (parentId) => {
      const { clipboard, lookup } = get();
      if (clipboard.length === 0) return;

      const parent = lookup.get(parentId);
      if (!parent || parent.type !== 'directory') return;

      set((state) => {
        const parentDir = state.lookup.get(parentId) as FSDirectory;
        const siblings = parentDir.children
          .map((cid) => state.lookup.get(cid))
          .filter((e): e is FSEntry => e !== undefined);
        const occupiedPositions = siblings.map((e) => e.iconPosition);
        const layout = getDesktopLayout();

        for (const sourceId of clipboard) {
          const source = state.lookup.get(sourceId);
          if (!source) continue;

          const newId = crypto.randomUUID();
          const position = findEmptyGridPosition(occupiedPositions, layout);
          occupiedPositions.push(position);

          const timestamp = now();
          const baseCopy = {
            id: newId,
            name: `${source.name} (copy)`,
            parentId,
            iconPosition: position,
            createdAt: timestamp,
            updatedAt: timestamp,
            icon: source.icon,
          };

          let newEntry: FSEntry;
          if (source.type === 'file') {
            newEntry = {
              ...baseCopy,
              type: 'file' as const,
              extension: source.extension,
              content: source.content,
            };
          } else if (source.type === 'app-shortcut') {
            newEntry = {
              ...baseCopy,
              type: 'app-shortcut' as const,
              appId: source.appId,
              extension: '.app' as const,
            };
          } else {
            // Copy directory as empty directory (no deep copy)
            newEntry = {
              ...baseCopy,
              type: 'directory' as const,
              children: [],
            };
          }

          state.lookup.set(newId, newEntry);
          parentDir.children.push(newId);
        }
      });
    },

    // --- File operations ---

    createDirectory: (parentId, name) => {
      const newId = crypto.randomUUID();

      set((state) => {
        const parent = state.lookup.get(parentId);
        if (!parent || parent.type !== 'directory') return;

        const parentDir = parent as FSDirectory;
        const siblings = parentDir.children
          .map((cid) => state.lookup.get(cid))
          .filter((e): e is FSEntry => e !== undefined);
        const occupiedPositions = siblings.map((e) => e.iconPosition);
        const layout = getDesktopLayout();

        const timestamp = now();
        const dir: FSDirectory = {
          id: newId,
          name,
          parentId,
          type: 'directory',
          iconPosition: findEmptyGridPosition(occupiedPositions, layout),
          createdAt: timestamp,
          updatedAt: timestamp,
          children: [],
          icon: '\uD83D\uDCC1',
        };

        state.lookup.set(newId, dir);
        parentDir.children.push(newId);
      });

      return newId;
    },

    createFile: (parentId, name, extension, content) => {
      const newId = crypto.randomUUID();

      set((state) => {
        const parent = state.lookup.get(parentId);
        if (!parent || parent.type !== 'directory') return;

        const parentDir = parent as FSDirectory;
        const siblings = parentDir.children
          .map((cid) => state.lookup.get(cid))
          .filter((e): e is FSEntry => e !== undefined);
        const occupiedPositions = siblings.map((e) => e.iconPosition);
        const layout = getDesktopLayout();

        const timestamp = now();
        const file: FSFile = {
          id: newId,
          name,
          parentId,
          type: 'file',
          extension,
          content: content ?? '',
          iconPosition: findEmptyGridPosition(occupiedPositions, layout),
          createdAt: timestamp,
          updatedAt: timestamp,
          icon: '\uD83D\uDCC4',
        };

        state.lookup.set(newId, file);
        parentDir.children.push(newId);
      });

      return newId;
    },

    deleteEntry: (id) => {
      set((state) => {
        const entry = state.lookup.get(id);
        if (!entry || entry.disableDelete) return;

        // Recursive delete for directories
        function removeRecursive(entryId: EntryId) {
          const e = state.lookup.get(entryId);
          if (!e) return;

          if (e.type === 'directory') {
            const dir = e as FSDirectory;
            for (const childId of [...dir.children]) {
              removeRecursive(childId);
            }
          }

          state.lookup.delete(entryId);
        }

        // Remove from parent
        if (entry.parentId) {
          const parent = state.lookup.get(entry.parentId);
          if (parent && parent.type === 'directory') {
            const parentDir = parent as FSDirectory;
            parentDir.children = parentDir.children.filter((cid) => cid !== id);
          }
        }

        removeRecursive(id);

        // Clean up selection/clipboard/renaming
        state.selected = state.selected.filter((sid) => sid !== id);
        state.clipboard = state.clipboard.filter((cid) => cid !== id);
        if (state.renaming === id) state.renaming = null;
      });
    },

    renameEntry: (id, name) => {
      set((state) => {
        const entry = state.lookup.get(id);
        if (!entry) return;
        entry.name = name;
        entry.updatedAt = now();
        state.renaming = null;
      });
    },

    moveEntry: (id, newParentId) => {
      set((state) => {
        const entry = state.lookup.get(id);
        if (!entry) return;

        const newParent = state.lookup.get(newParentId);
        if (!newParent || newParent.type !== 'directory') return;

        // Remove from old parent
        if (entry.parentId) {
          const oldParent = state.lookup.get(entry.parentId);
          if (oldParent && oldParent.type === 'directory') {
            const oldDir = oldParent as FSDirectory;
            oldDir.children = oldDir.children.filter((cid) => cid !== id);
          }
        }

        // Add to new parent
        const newDir = newParent as FSDirectory;
        newDir.children.push(id);
        entry.parentId = newParentId;
        entry.updatedAt = now();
      });
    },

    setIconPosition: (id, pos) => {
      set((state) => {
        const entry = state.lookup.get(id);
        if (!entry) return;
        entry.iconPosition = snapToGrid(pos);
        entry.updatedAt = now();
      });
    },

    setRenaming: (id) => {
      set((state) => {
        state.renaming = id;
      });
    },

    // --- Initialization ---

    initDesktop: (apps) => {
      set((state) => {
        // Already initialized
        if (state.lookup.size > 0) return;

        const timestamp = now();
        const layout = getDesktopLayout();
        const occupiedPositions: Position[] = [];

        // Create root directory
        const root: FSDirectory = {
          id: 'root',
          name: 'Root',
          parentId: null,
          type: 'directory',
          iconPosition: { x: 0, y: 0 },
          createdAt: timestamp,
          updatedAt: timestamp,
          children: ['desktop'],
          disableDelete: true,
          disableCopy: true,
        };
        state.lookup.set('root', root);

        // Create desktop directory
        const desktop: FSDirectory = {
          id: 'desktop',
          name: 'Desktop',
          parentId: 'root',
          type: 'directory',
          iconPosition: { x: 0, y: 0 },
          createdAt: timestamp,
          updatedAt: timestamp,
          children: [],
          disableDelete: true,
          disableCopy: true,
        };
        state.lookup.set('desktop', desktop);

        // Place app shortcuts on desktop
        for (const [appId, app] of apps) {
          const shortcutId = `shortcut-${appId}`;
          const position = findEmptyGridPosition(occupiedPositions, layout);
          occupiedPositions.push(position);

          const shortcut: FSAppShortcut = {
            id: shortcutId,
            name: app.name,
            parentId: 'desktop',
            type: 'app-shortcut',
            appId,
            extension: '.app',
            iconPosition: position,
            createdAt: timestamp,
            updatedAt: timestamp,
            disableDelete: true,
            disableCopy: true,
            icon: app.icon,
          };

          state.lookup.set(shortcutId, shortcut);
          desktop.children.push(shortcutId);
        }

        // Place "My Files" folder on desktop
        const myFilesId = 'my-files';
        const myFilesPosition = findEmptyGridPosition(occupiedPositions, layout);
        occupiedPositions.push(myFilesPosition);

        const myFiles: FSDirectory = {
          id: myFilesId,
          name: 'My Files',
          parentId: 'desktop',
          type: 'directory',
          iconPosition: myFilesPosition,
          createdAt: timestamp,
          updatedAt: timestamp,
          children: [],
          icon: '\uD83D\uDCC1',
        };

        state.lookup.set(myFilesId, myFiles);
        desktop.children.push(myFilesId);
      });
    },
  })),
);
