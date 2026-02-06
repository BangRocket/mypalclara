import { useEffect, useState } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import { X, Save, Trash2, Key } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Memory } from "@/api/client";
import { memories as memoriesApi } from "@/api/client";

interface MemoryEditorProps {
  memory: Memory;
  onClose: () => void;
  onSaved: () => void;
  onDeleted: () => void;
}

export function MemoryEditor({ memory, onClose, onSaved, onDeleted }: MemoryEditorProps) {
  const [category, setCategory] = useState(memory.dynamics?.category || "");
  const [isKey, setIsKey] = useState(memory.dynamics?.is_key || false);
  const [saving, setSaving] = useState(false);

  const editor = useEditor({
    extensions: [
      StarterKit,
      Placeholder.configure({ placeholder: "Edit memory content..." }),
    ],
    content: `<p>${memory.content}</p>`,
  });

  const handleSave = async () => {
    if (!editor) return;
    setSaving(true);
    try {
      const content = editor.getText();
      await memoriesApi.update(memory.id, {
        content,
        category: category || undefined,
        is_key: isKey,
      });
      onSaved();
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm("Delete this memory permanently?")) return;
    await memoriesApi.delete(memory.id);
    onDeleted();
  };

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />

      {/* Panel */}
      <div className="relative ml-auto w-full max-w-2xl bg-surface-raised border-l border-border flex flex-col h-full">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-border">
          <h2 className="text-lg font-semibold">Edit Memory</h2>
          <div className="flex items-center gap-2">
            <button
              onClick={handleDelete}
              className="p-2 text-text-muted hover:text-danger transition rounded-lg hover:bg-surface-overlay"
              title="Delete"
            >
              <Trash2 size={16} />
            </button>
            <button
              onClick={onClose}
              className="p-2 text-text-muted hover:text-text-primary transition rounded-lg hover:bg-surface-overlay"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Editor */}
        <div className="flex-1 overflow-y-auto">
          <EditorContent editor={editor} className="tiptap" />
        </div>

        {/* Properties panel */}
        <div className="border-t border-border p-4 space-y-3">
          <div className="flex items-center gap-3">
            <label className="text-xs text-text-muted w-20">Category</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="flex-1 bg-surface-overlay border border-border rounded-lg px-3 py-1.5 text-sm"
            >
              <option value="">Uncategorized</option>
              <option value="personal">Personal</option>
              <option value="professional">Professional</option>
              <option value="preferences">Preferences</option>
              <option value="goals">Goals</option>
              <option value="emotional">Emotional</option>
              <option value="temporal">Temporal</option>
            </select>
          </div>
          <div className="flex items-center gap-3">
            <label className="text-xs text-text-muted w-20">Key Memory</label>
            <button
              onClick={() => setIsKey(!isKey)}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition",
                isKey ? "bg-key/15 text-key" : "bg-surface-overlay text-text-muted",
              )}
            >
              <Key size={14} />
              {isKey ? "Key" : "Normal"}
            </button>
          </div>
          {memory.dynamics && (
            <div className="flex items-center gap-4 text-xs text-text-muted">
              <span>Stability: {memory.dynamics.stability?.toFixed(1) ?? "–"}</span>
              <span>Difficulty: {memory.dynamics.difficulty?.toFixed(1) ?? "–"}</span>
              <span>Accessed: {memory.dynamics.access_count}x</span>
            </div>
          )}
        </div>

        {/* Save button */}
        <div className="p-4 border-t border-border">
          <button
            onClick={handleSave}
            disabled={saving}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-accent hover:bg-accent-hover disabled:opacity-50 rounded-lg text-white text-sm font-medium transition"
          >
            <Save size={16} />
            {saving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </div>
    </div>
  );
}
