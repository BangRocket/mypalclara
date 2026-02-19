import { useChatStore, type ModelTier } from "@/stores/chatStore";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Zap, Scale, Brain } from "lucide-react";

const tiers: { value: ModelTier; label: string; icon: typeof Zap }[] = [
  { value: "low", label: "Fast", icon: Zap },
  { value: "mid", label: "Balanced", icon: Scale },
  { value: "high", label: "Powerful", icon: Brain },
];

export function TierSelector() {
  const selectedTier = useChatStore((s) => s.selectedTier);
  const setTier = useChatStore((s) => s.setTier);

  const current = tiers.find((t) => t.value === selectedTier) ?? tiers[1];

  return (
    <Select value={selectedTier} onValueChange={(v) => setTier(v as ModelTier)}>
      <SelectTrigger className="h-8 w-auto gap-1.5 border-none bg-transparent px-2 text-xs text-muted-foreground shadow-none hover:text-foreground focus:ring-0">
        <current.icon className="size-3.5" />
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {tiers.map((t) => (
          <SelectItem key={t.value} value={t.value}>
            <div className="flex items-center gap-2">
              <t.icon className="size-3.5" />
              {t.label}
            </div>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
