import { useMemo } from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { resolveSheetUrl, FRAME_SIZE, type SpriteLayerDef } from "@/lib/spriteManifest";

interface LayerSelection {
  sheet: string;
  row: number;
  col: number;
}

interface LayerPickerProps {
  layer: SpriteLayerDef;
  value: LayerSelection | null;
  onChange: (value: LayerSelection | null) => void;
}

export function LayerPicker({ layer, value, onChange }: LayerPickerProps) {
  const selectedSheet = value?.sheet || layer.sheets[0]?.filename || "";

  const sheetUrl = useMemo(
    () => resolveSheetUrl(layer.category, selectedSheet),
    [layer.category, selectedSheet]
  );

  const frames = useMemo(() => {
    const items: { row: number; col: number }[] = [];
    for (let r = 0; r < layer.rows; r++) {
      for (let c = 0; c < layer.cols; c++) {
        items.push({ row: r, col: c });
      }
    }
    return items;
  }, [layer.rows, layer.cols]);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-foreground">{layer.label}</span>
        {!layer.required && value && (
          <Button variant="ghost" size="sm" onClick={() => onChange(null)}>
            Clear
          </Button>
        )}
      </div>

      {layer.sheets.length > 1 && (
        <Select
          value={selectedSheet}
          onValueChange={(v) => {
            if (value) {
              onChange({ ...value, sheet: v });
            } else {
              onChange({ sheet: v, row: 0, col: 0 });
            }
          }}
        >
          <SelectTrigger className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {layer.sheets.map((s) => (
              <SelectItem key={s.filename} value={s.filename}>
                {s.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}

      {sheetUrl && (
        <div
          className="grid gap-1 p-2 rounded-md bg-muted/50 border border-border"
          style={{
            gridTemplateColumns: `repeat(${layer.cols}, 48px)`,
          }}
        >
          {frames.map(({ row, col }) => {
            const isSelected =
              value?.row === row &&
              value?.col === col &&
              (value?.sheet || layer.sheets[0]?.filename) === selectedSheet;

            return (
              <button
                key={`${row}-${col}`}
                type="button"
                onClick={() =>
                  onChange({ sheet: selectedSheet, row, col })
                }
                className="relative block"
                style={{
                  width: 48,
                  height: 48,
                  backgroundImage: `url(${sheetUrl})`,
                  backgroundPosition: `-${col * FRAME_SIZE * (48 / FRAME_SIZE)}px -${row * FRAME_SIZE * (48 / FRAME_SIZE)}px`,
                  backgroundSize: `${layer.cols * 48}px ${layer.rows * 48}px`,
                  imageRendering: "pixelated",
                  borderRadius: 4,
                  outline: isSelected ? "2px solid hsl(var(--primary))" : "1px solid transparent",
                  outlineOffset: -1,
                  cursor: "pointer",
                }}
                title={`Row ${row}, Col ${col}`}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
