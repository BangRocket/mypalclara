import { Key, Star } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Memory } from "@/api/client";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

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
    <Card
      onClick={onClick}
      className="p-4 cursor-pointer hover:border-primary/40 transition group"
    >
      {/* Header */}
      <div className="flex items-center gap-2 mb-2">
        <Badge variant="secondary" className={cn("text-xs", colorClass)}>{category}</Badge>
        {dyn?.is_key && <span title="Key memory"><Key size={14} className="text-key" /></span>}
        {dyn && dyn.stability !== null && dyn.stability >= 30 && (
          <span title="High stability"><Star size={14} className="text-success" /></span>
        )}
      </div>

      {/* Content */}
      <p className="text-sm line-clamp-3">{memory.content}</p>

      {/* Footer */}
      <div className="flex items-center gap-3 mt-3 text-xs text-muted-foreground">
        {dyn && <span>S: {dyn.stability?.toFixed(1) ?? "–"}</span>}
        {dyn && <span>A: {dyn.access_count}</span>}
        {memory.created_at && <span>{new Date(memory.created_at).toLocaleDateString()}</span>}
      </div>
    </Card>
  );
}
