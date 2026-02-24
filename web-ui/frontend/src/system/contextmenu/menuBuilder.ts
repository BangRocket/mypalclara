import { useFileSystemStore } from '../filesystem/store';
import type { ContextMenuItem } from './types';
import type { EntryId } from '../filesystem/types';

export function buildDesktopMenu(parentId: EntryId): ContextMenuItem[] {
  const store = useFileSystemStore.getState();

  return [
    {
      label: 'New Folder',
      action: () => {
        const id = store.createDirectory(parentId, 'New Folder');
        store.setRenaming(id);
      },
    },
    {
      label: 'New Text File',
      action: () => {
        const id = store.createFile(parentId, 'New File', '.txt');
        store.setRenaming(id);
      },
      dividerAfter: true,
    },
    {
      label: 'Paste',
      action: () => store.paste(parentId),
      disabled: store.clipboard.length === 0,
    },
    {
      label: 'Select All',
      action: () => store.selectAll(parentId),
    },
  ];
}

export function buildIconMenu(entryId: EntryId): ContextMenuItem[] {
  const store = useFileSystemStore.getState();
  const entry = store.getEntry(entryId);
  if (!entry) return [];

  return [
    {
      label: 'Open',
      action: () => {
        // Trigger a synthetic double-click by dispatching through the DOM
        const el = document.querySelector(`[data-entry-id="${entryId}"]`);
        if (el) {
          el.dispatchEvent(new MouseEvent('dblclick', { bubbles: true }));
        }
      },
      dividerAfter: true,
    },
    {
      label: 'Copy',
      action: () => {
        if (!store.isSelected(entryId)) {
          store.select(entryId);
        }
        store.copySelected();
      },
      disabled: entry.disableCopy === true,
    },
    {
      label: 'Rename',
      action: () => store.setRenaming(entryId),
      dividerAfter: true,
    },
    {
      label: 'Delete',
      action: () => store.deleteEntry(entryId),
      disabled: entry.disableDelete === true,
    },
  ];
}
