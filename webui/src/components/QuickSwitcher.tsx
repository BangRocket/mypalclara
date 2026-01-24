import { Command } from 'cmdk';
import { useState, useEffect, useCallback } from 'react';
import Fuse from 'fuse.js';
import { commands, type NoteTitle } from '../lib/bindings';
import { useUiStore } from '../stores';

export function QuickSwitcher() {
  const [open, setOpen] = useState(false);
  const [notes, setNotes] = useState<NoteTitle[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);

  const selectNote = useUiStore((s) => s.selectNote);

  // Keyboard shortcut: Cmd+P (Mac) or Ctrl+P (Windows/Linux)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'p' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Load notes when opened
  useEffect(() => {
    if (open) {
      setLoading(true);
      commands.getAllNoteTitles().then((result) => {
        if (result.status === 'ok') {
          setNotes(result.data);
        }
        setLoading(false);
      });
    } else {
      setSearch(''); // Reset search on close
    }
  }, [open]);

  // Fuzzy search
  const fuse = new Fuse(notes, {
    keys: ['title'],
    threshold: 0.3,
    distance: 100,
  });

  const filtered = search
    ? fuse.search(search).map((r) => r.item)
    : notes;

  const handleSelect = useCallback((noteId: string) => {
    selectNote(Number(noteId));
    setOpen(false);
  }, [selectNote]);

  if (!open) return null;

  return (
    <Command.Dialog
      open={open}
      onOpenChange={setOpen}
      label="Quick Switcher"
      className="fixed inset-0 z-50"
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50"
        onClick={() => setOpen(false)}
      />

      {/* Modal */}
      <div className="fixed left-1/2 top-1/4 -translate-x-1/2 w-full max-w-lg bg-white rounded-xl shadow-2xl overflow-hidden">
        <Command.Input
          value={search}
          onValueChange={setSearch}
          placeholder="Search notes..."
          className="w-full px-4 py-3 text-lg border-b border-gray-200 outline-none"
          autoFocus
        />

        <Command.List className="max-h-80 overflow-y-auto p-2">
          {loading && (
            <Command.Loading className="px-4 py-2 text-sm text-gray-500">
              Loading notes...
            </Command.Loading>
          )}

          <Command.Empty className="px-4 py-8 text-center text-sm text-gray-500">
            No notes found.
          </Command.Empty>

          <Command.Group heading="Notes">
            {filtered.map((note) => (
              <Command.Item
                key={note.id}
                value={String(note.id)}
                onSelect={handleSelect}
                className="px-4 py-2 text-sm rounded-lg cursor-pointer data-[selected=true]:bg-blue-100 hover:bg-gray-100"
              >
                {note.title}
              </Command.Item>
            ))}
          </Command.Group>
        </Command.List>

        {/* Footer with keyboard hints */}
        <div className="px-4 py-2 border-t border-gray-200 bg-gray-50 text-xs text-gray-500 flex gap-4">
          <span><kbd className="px-1 py-0.5 bg-gray-200 rounded">Enter</kbd> to select</span>
          <span><kbd className="px-1 py-0.5 bg-gray-200 rounded">Esc</kbd> to close</span>
        </div>
      </div>
    </Command.Dialog>
  );
}
