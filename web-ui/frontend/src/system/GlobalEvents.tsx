import { useEffect } from 'react';
import { useFileSystemStore } from './filesystem/store';
import { useContextMenuStore } from './contextmenu/store';

/**
 * Global keyboard shortcut handler for ClaraOS.
 *
 * Listens on `window` for keydown events and dispatches to stores:
 *   Cmd/Ctrl+A  -> select all desktop icons
 *   Cmd/Ctrl+C  -> copy selected to clipboard
 *   Cmd/Ctrl+V  -> paste clipboard to desktop
 *   Delete/Backspace -> delete selected entries (respects disableDelete)
 *   F2          -> rename first selected entry
 *   Escape      -> clear selection + close context menu
 *
 * Skips handling when focus is inside an input, textarea, or contenteditable.
 */
export function GlobalEvents() {
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      // Don't intercept when the user is typing in a form field
      const tag = (e.target as HTMLElement)?.tagName?.toLowerCase();
      if (tag === 'input' || tag === 'textarea') return;
      if ((e.target as HTMLElement)?.isContentEditable) return;

      const mod = e.metaKey || e.ctrlKey;
      const fs = useFileSystemStore.getState();
      const ctx = useContextMenuStore.getState();

      // --- Escape: clear selection + close context menu ---
      if (e.key === 'Escape') {
        fs.clearSelection();
        ctx.hide();
        return;
      }

      // --- F2: rename first selected entry ---
      if (e.key === 'F2') {
        e.preventDefault();
        if (fs.selected.length > 0) {
          fs.setRenaming(fs.selected[0]);
        }
        return;
      }

      // --- Delete / Backspace: delete selected entries ---
      if (e.key === 'Delete' || e.key === 'Backspace') {
        e.preventDefault();
        // Copy the array since deletion mutates it
        const toDelete = [...fs.selected];
        for (const id of toDelete) {
          const entry = fs.getEntry(id);
          if (entry && !entry.disableDelete) {
            fs.deleteEntry(id);
          }
        }
        return;
      }

      if (!mod) return;

      // --- Cmd/Ctrl+A: select all desktop icons ---
      if (e.key === 'a') {
        e.preventDefault();
        fs.selectAll('desktop');
        return;
      }

      // --- Cmd/Ctrl+C: copy selected to clipboard ---
      if (e.key === 'c') {
        e.preventDefault();
        fs.copySelected();
        return;
      }

      // --- Cmd/Ctrl+V: paste clipboard to desktop ---
      if (e.key === 'v') {
        e.preventDefault();
        fs.paste('desktop');
        return;
      }
    }

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  return null;
}
