import { useState, useEffect, useCallback } from 'react';
import { useFileSystemStore } from '@/system/filesystem/store';
import { useWindowStore } from '@/system/window/store';
import type { FSFile } from '@/system/filesystem/types';

/**
 * Minimal text editor app. When opened with a windowId that maps to a file in
 * the filesystem store, it loads and lets you edit/save the file content.
 * Otherwise it starts as a blank scratch pad.
 */
export default function TextEditorApp({ windowId }: { windowId: string }) {
  const getEntry = useFileSystemStore((s) => s.getEntry);
  const setTitle = useWindowStore((s) => s.setTitle);

  // Try to find a file entry matching the windowId (e.g. "text-editor-<fileId>")
  const fileId = windowId.startsWith('text-editor-')
    ? windowId.slice('text-editor-'.length)
    : null;

  const file = fileId ? getEntry(fileId) : undefined;
  const isFile = file?.type === 'file';
  const initialContent = isFile ? (file as FSFile).content : '';
  const fileName = isFile ? file.name : 'Untitled';

  const [content, setContent] = useState(initialContent);
  const [dirty, setDirty] = useState(false);

  // Set window title
  useEffect(() => {
    setTitle(windowId, `${fileName}${dirty ? ' *' : ''} - Text Editor`);
  }, [windowId, fileName, dirty, setTitle]);

  const handleChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setContent(e.target.value);
    setDirty(true);
  }, []);

  const handleSave = useCallback(() => {
    if (fileId && isFile) {
      // Update file content through the store
      useFileSystemStore.getState().renameEntry(fileId, fileName); // touch updatedAt
      // Directly update content in the lookup
      useFileSystemStore.setState((state) => {
        const entry = state.lookup.get(fileId);
        if (entry && entry.type === 'file') {
          (entry as FSFile).content = content;
          entry.updatedAt = new Date();
        }
      });
      setDirty(false);
    }
  }, [fileId, isFile, fileName, content]);

  return (
    <div className="flex h-full flex-col bg-background">
      {/* Toolbar */}
      <div className="flex items-center gap-2 border-b border-border px-3 py-1.5">
        <span className="text-xs text-muted-foreground truncate flex-1">{fileName}</span>
        {fileId && isFile && (
          <button
            onClick={handleSave}
            disabled={!dirty}
            className="rounded px-2.5 py-1 text-xs font-medium transition-colors disabled:opacity-40 bg-primary/10 text-primary hover:bg-primary/20 disabled:hover:bg-primary/10"
          >
            Save
          </button>
        )}
      </div>

      {/* Editor */}
      <textarea
        value={content}
        onChange={handleChange}
        spellCheck={false}
        className="flex-1 resize-none bg-transparent p-4 font-mono text-sm text-foreground outline-none placeholder:text-muted-foreground/50"
        placeholder="Start typing..."
      />
    </div>
  );
}
