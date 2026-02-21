import { Key } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Memory } from "@/api/client";

interface MemoryListProps {
  memories: Memory[];
  onSelect: (memory: Memory) => void;
}

export function MemoryList({ memories, onSelect }: MemoryListProps) {
  if (memories.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-text-muted text-sm">
        No memories found.
      </div>
    );
  }

  return (
    <div className="divide-y divide-border">
      {/* Header */}
      <div className="grid grid-cols-12 gap-2 px-4 py-2 text-xs font-medium text-text-muted uppercase tracking-wide">
        <div className="col-span-5">Content</div>
        <div className="col-span-2">Category</div>
        <div className="col-span-1 text-center">Key</div>
        <div className="col-span-1 text-right">Stability</div>
        <div className="col-span-1 text-right">Access</div>
        <div className="col-span-2 text-right">Created</div>
      </div>

      {/* Rows */}
      {memories.map((m) => {
        const dyn = m.dynamics;
        return (
          <button
            key={m.id}
            onClick={() => onSelect(m)}
            className="grid grid-cols-12 gap-2 px-4 py-3 text-sm hover:bg-surface-overlay transition w-full text-left"
          >
            <div className="col-span-5 truncate text-text-primary">{m.content}</div>
            <div className="col-span-2">
              <span className="px-2 py-0.5 rounded text-xs bg-surface-overlay text-text-secondary">
                {dyn?.category || "–"}
              </span>
            </div>
            <div className="col-span-1 text-center">
              {dyn?.is_key && <Key size={14} className="text-key inline" />}
            </div>
            <div className="col-span-1 text-right text-text-secondary">{dyn?.stability?.toFixed(1) ?? "–"}</div>
            <div className="col-span-1 text-right text-text-secondary">{dyn?.access_count ?? 0}</div>
            <div className="col-span-2 text-right text-text-muted">
              {m.created_at ? new Date(m.created_at).toLocaleDateString() : "–"}
            </div>
          </button>
        );
      })}
    </div>
  );
}
