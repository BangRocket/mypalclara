import { useEffect, useCallback, useState, useRef } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Placeholder from '@tiptap/extension-placeholder';
import { useNote, useUpdateNote, useDeleteNote } from '../hooks';
import { useUiStore } from '../stores';
import { WikiLink, wikiLinkSuggestion } from '../editor/extensions';
import { WikiLinkPreview } from '../editor/components';

interface EditorToolbarProps {
  editor: ReturnType<typeof useEditor>;
  onExport: () => void;
  onDelete: () => void;
  isSaving: boolean;
}

function EditorToolbar({ editor, onExport, onDelete, isSaving }: EditorToolbarProps) {
  if (!editor) return null;

  const buttonClass = (active: boolean) =>
    `px-2 py-1 text-sm rounded ${
      active ? 'bg-gray-200 text-gray-900' : 'text-gray-600 hover:bg-gray-100'
    }`;

  return (
    <div className="flex items-center gap-1 p-2 border-b border-gray-200 bg-gray-50 flex-wrap">
      <button
        onClick={() => editor.chain().focus().toggleBold().run()}
        className={buttonClass(editor.isActive('bold'))}
        title="Bold (Cmd+B)"
      >
        <strong>B</strong>
      </button>
      <button
        onClick={() => editor.chain().focus().toggleItalic().run()}
        className={buttonClass(editor.isActive('italic'))}
        title="Italic (Cmd+I)"
      >
        <em>I</em>
      </button>
      <button
        onClick={() => editor.chain().focus().toggleStrike().run()}
        className={buttonClass(editor.isActive('strike'))}
        title="Strikethrough"
      >
        <s>S</s>
      </button>
      <button
        onClick={() => editor.chain().focus().toggleCode().run()}
        className={buttonClass(editor.isActive('code'))}
        title="Inline Code"
      >
        {'</>'}
      </button>

      <div className="w-px h-5 bg-gray-300 mx-1" />

      <button
        onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
        className={buttonClass(editor.isActive('heading', { level: 1 }))}
        title="Heading 1"
      >
        H1
      </button>
      <button
        onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
        className={buttonClass(editor.isActive('heading', { level: 2 }))}
        title="Heading 2"
      >
        H2
      </button>
      <button
        onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
        className={buttonClass(editor.isActive('heading', { level: 3 }))}
        title="Heading 3"
      >
        H3
      </button>

      <div className="w-px h-5 bg-gray-300 mx-1" />

      <button
        onClick={() => editor.chain().focus().toggleBulletList().run()}
        className={buttonClass(editor.isActive('bulletList'))}
        title="Bullet List"
      >
        • List
      </button>
      <button
        onClick={() => editor.chain().focus().toggleOrderedList().run()}
        className={buttonClass(editor.isActive('orderedList'))}
        title="Numbered List"
      >
        1. List
      </button>
      <button
        onClick={() => editor.chain().focus().toggleCodeBlock().run()}
        className={buttonClass(editor.isActive('codeBlock'))}
        title="Code Block"
      >
        {'```'}
      </button>
      <button
        onClick={() => editor.chain().focus().toggleBlockquote().run()}
        className={buttonClass(editor.isActive('blockquote'))}
        title="Quote"
      >
        &ldquo;
      </button>

      <div className="flex-1" />

      {/* Status indicator */}
      <span className="text-xs text-gray-400 mr-2">
        {isSaving ? 'Saving...' : 'Saved'}
      </span>

      {/* Export button */}
      <button
        onClick={onExport}
        className="px-2 py-1 text-sm text-gray-600 hover:bg-gray-100 rounded"
        title="Export as Markdown"
      >
        Export
      </button>

      {/* Delete button */}
      <button
        onClick={onDelete}
        className="px-2 py-1 text-sm text-red-600 hover:bg-red-50 rounded"
        title="Delete Note"
      >
        Delete
      </button>
    </div>
  );
}

interface NoteEditorProps {
  noteId: number;
  onExport: (noteId: number) => void;
}

export function NoteEditor({ noteId, onExport }: NoteEditorProps) {
  const { data: note, isLoading, error } = useNote(noteId);
  const updateNote = useUpdateNote();
  const deleteNote = useDeleteNote();
  const selectNote = useUiStore((state) => state.selectNote);
  const editorContainerRef = useRef<HTMLDivElement>(null);

  const [title, setTitle] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [saveTimeoutId, setSaveTimeoutId] = useState<number | null>(null);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
      }),
      Placeholder.configure({
        placeholder: 'Start writing...',
      }),
      WikiLink.configure({
        onWikiLinkClick: (noteId, _title) => {
          selectNote(noteId);
        },
        suggestion: wikiLinkSuggestion,
      }),
    ],
    content: '',
    editorProps: {
      attributes: {
        class: 'prose prose-sm max-w-none focus:outline-none min-h-[200px] p-4',
      },
    },
    onUpdate: ({ editor }) => {
      debouncedSave(title, editor.getHTML());
    },
  });

  // Load note content when note changes
  useEffect(() => {
    if (note) {
      setTitle(note.title);
      // Convert plain text/markdown to HTML for TipTap
      // For now, just set as paragraph - proper markdown parsing comes in wiki-links phase
      editor?.commands.setContent(note.content ? `<p>${note.content.replace(/\n/g, '</p><p>')}</p>` : '');
    }
  }, [note, editor]);

  // Debounced save function (inline implementation)
  const debouncedSave = useCallback(
    (newTitle: string, newContent: string) => {
      if (saveTimeoutId) {
        clearTimeout(saveTimeoutId);
      }

      const timeoutId = window.setTimeout(() => {
        setIsSaving(true);
        // Strip HTML tags for storage (we'll add proper markdown conversion later)
        const plainContent = newContent
          .replace(/<[^>]*>/g, '\n')
          .replace(/\n+/g, '\n')
          .trim();

        updateNote.mutate(
          { id: noteId, input: { title: newTitle || null, content: plainContent || null, folder_id: null } },
          {
            onSettled: () => {
              setIsSaving(false);
            },
          }
        );
      }, 1500); // 1.5 second debounce

      setSaveTimeoutId(timeoutId);
    },
    [noteId, updateNote, saveTimeoutId]
  );

  // Handle title change
  const handleTitleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newTitle = e.target.value;
    setTitle(newTitle);
    debouncedSave(newTitle, editor?.getHTML() || '');
  };

  // Handle delete
  const handleDelete = () => {
    if (confirm('Delete this note?')) {
      deleteNote.mutate(noteId, {
        onSuccess: () => {
          selectNote(null);
        },
      });
    }
  };

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (saveTimeoutId) {
        clearTimeout(saveTimeoutId);
      }
    };
  }, [saveTimeoutId]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500">
        Loading note...
      </div>
    );
  }

  if (error || !note) {
    return (
      <div className="flex items-center justify-center h-full text-red-500">
        Error loading note
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-white">
      {/* Toolbar */}
      <EditorToolbar
        editor={editor}
        onExport={() => onExport(noteId)}
        onDelete={handleDelete}
        isSaving={isSaving || updateNote.isPending}
      />

      {/* Title input */}
      <input
        type="text"
        value={title}
        onChange={handleTitleChange}
        className="text-2xl font-bold px-4 py-3 border-b border-gray-100 focus:outline-none"
        placeholder="Note title..."
      />

      {/* Editor */}
      <div ref={editorContainerRef} className="flex-1 overflow-auto">
        <EditorContent editor={editor} />
      </div>

      {/* Wiki link preview - invisible component managing hover tooltips */}
      <WikiLinkPreview editorRef={editorContainerRef} />
    </div>
  );
}
