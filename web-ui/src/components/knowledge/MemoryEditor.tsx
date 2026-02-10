import { useEffect, useState } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import { X, Save, Trash2, Key } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Memory } from "@/api/client";
import { memories as memoriesApi } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";

interface MemoryEditorProps {
  memory: Memory;
  onClose: () => void;
  onSaved: () => void;
  onDeleted: () => void;
}

export function MemoryEditor({ memory, onClose, onSaved, onDeleted }: MemoryEditorProps) {
  const [category, setCategory] = useState(memory.dynamics?.category || "uncategorized");
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
        category: category === "uncategorized" ? undefined : category,
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
    <Sheet open onOpenChange={onClose}>
      <SheetContent side="right" className="w-full sm:max-w-2xl p-0 flex flex-col">
        <SheetHeader className="px-4 py-4 border-b">
          <div className="flex items-center justify-between">
            <SheetTitle>Edit Memory</SheetTitle>
            <Button
              variant="ghost"
              size="icon"
              onClick={handleDelete}
              title="Delete"
              className="hover:text-destructive"
            >
              <Trash2 size={16} />
            </Button>
          </div>
        </SheetHeader>

        {/* Editor */}
        <div className="flex-1 overflow-y-auto">
          <EditorContent editor={editor} className="tiptap" />
        </div>

        {/* Properties panel */}
        <div className="border-t border-border p-4 space-y-3">
          <div className="flex items-center gap-3">
            <label className="text-xs text-muted-foreground w-20">Category</label>
            <Select value={category} onValueChange={setCategory}>
              <SelectTrigger className="flex-1">
                <SelectValue placeholder="Uncategorized" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="uncategorized">Uncategorized</SelectItem>
                <SelectItem value="personal">Personal</SelectItem>
                <SelectItem value="professional">Professional</SelectItem>
                <SelectItem value="preferences">Preferences</SelectItem>
                <SelectItem value="goals">Goals</SelectItem>
                <SelectItem value="emotional">Emotional</SelectItem>
                <SelectItem value="temporal">Temporal</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center gap-3">
            <label className="text-xs text-muted-foreground w-20">Key Memory</label>
            <Button
              variant={isKey ? "secondary" : "outline"}
              onClick={() => setIsKey(!isKey)}
              className={cn(
                "gap-1.5",
                isKey && "bg-key/15 text-key hover:bg-key/20"
              )}
            >
              <Key size={14} />
              {isKey ? "Key" : "Normal"}
            </Button>
          </div>
          {memory.dynamics && (
            <div className="flex items-center gap-4 text-xs text-muted-foreground">
              <span>Stability: {memory.dynamics.stability?.toFixed(1) ?? "–"}</span>
              <span>Difficulty: {memory.dynamics.difficulty?.toFixed(1) ?? "–"}</span>
              <span>Accessed: {memory.dynamics.access_count}x</span>
            </div>
          )}
        </div>

        {/* Save button */}
        <div className="p-4 border-t border-border">
          <Button
            onClick={handleSave}
            disabled={saving}
            className="w-full gap-2"
          >
            <Save size={16} />
            {saving ? "Saving..." : "Save Changes"}
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
