import { Key, Star } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Memory } from "@/api/client";

const CATEGORY_COLORS: Record<string, string> = {
  personal: "bg-blue-500/15 text-blue-400",
  professional: "bg-green-500/15 text-green-400",
  preferences: "bg-purple-500/15 text-purple-400",
  goals: "bg-orange-500/15 text-orange-400",
  emotional: "bg-pink-500/15 text-pink-400",
  temporal: "bg-cyan-500/15 text-cyan-400",
};

interface MemoryCardProps {
  memory: Memory;
  onClick: () => void;
}

export function MemoryCard({ memory, onClick }: MemoryCardProps) {
  const dyn = memory.dynamics;
  const category = dyn?.category || "uncategorized";
  const colorClass = CATEGORY_COLORS[category] || "bg-surface-overlay text-text-muted";

  return (
    <button
      onClick={onClick}
      className="w-full text-left bg-surface-raised border border-border rounded-xl p-4 hover:border-accent/40 transition group"
    >
      {/* Header */}
      <div className="flex items-center gap-2 mb-2">
        <span className={cn("px-2 py-0.5 rounded text-xs font-medium", colorClass)}>{category}</span>
        {dyn?.is_key && <span title="Key memory"><Key size={14} className="text-key" /></span>}
        {dyn && dyn.stability !== null && dyn.stability >= 30 && (
          <span title="High stability"><Star size={14} className="text-success" /></span>
        )}
      </div>

      {/* Content */}
      <p className="text-sm text-text-primary line-clamp-3">{memory.content}</p>

      {/* Footer */}
      <div className="flex items-center gap-3 mt-3 text-xs text-text-muted">
        {dyn && <span>S: {dyn.stability?.toFixed(1) ?? "–"}</span>}
        {dyn && <span>A: {dyn.access_count}</span>}
        {memory.created_at && <span>{new Date(memory.created_at).toLocaleDateString()}</span>}
      </div>
    </button>
  );
}
