import type { Memory } from "@/api/client";
import { MemoryCard } from "./MemoryCard";

interface MemoryGridProps {
  memories: Memory[];
  onSelect: (memory: Memory) => void;
}

export function MemoryGrid({ memories, onSelect }: MemoryGridProps) {
  if (memories.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-text-muted text-sm">
        No memories found.
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3 p-4">
      {memories.map((m) => (
        <MemoryCard key={m.id} memory={m} onClick={() => onSelect(m)} />
      ))}
    </div>
  );
}
