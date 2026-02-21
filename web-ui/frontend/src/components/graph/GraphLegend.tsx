import { TYPE_COLORS } from "./EntityNode";

interface GraphLegendProps {
  typeCounts: Record<string, number>;
}

export function GraphLegend({ typeCounts }: GraphLegendProps) {
  const entries = Object.entries(typeCounts).filter(([, count]) => count > 0);
  if (entries.length === 0) return null;

  return (
    <div className="absolute bottom-14 left-3 z-10 bg-card/90 backdrop-blur-sm border border-border rounded-lg p-2.5 shadow-md">
      <div className="flex flex-col gap-1.5">
        {entries.map(([type, count]) => (
          <div key={type} className="flex items-center gap-2 text-xs text-foreground">
            <span
              className="w-2.5 h-2.5 rounded-full shrink-0"
              style={{ backgroundColor: TYPE_COLORS[type] || TYPE_COLORS.default }}
            />
            <span className="capitalize">{type}</span>
            <span className="text-muted-foreground ml-auto tabular-nums">{count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
