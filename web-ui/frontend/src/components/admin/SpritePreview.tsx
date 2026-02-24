import { useEffect, useRef } from "react";
import { compositeSprite, type SpriteLayer } from "@/lib/spriteCompositor";

interface SpritePreviewProps {
  layers: SpriteLayer[];
  size?: number;
}

export function SpritePreview({ layers, size = 120 }: SpritePreviewProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    compositeSprite(canvas, layers, size);
  }, [layers, size]);

  return (
    <canvas
      ref={canvasRef}
      width={size}
      height={size}
      style={{
        width: size,
        height: size,
        imageRendering: "pixelated",
        border: "2px solid var(--border)",
        borderRadius: 8,
        background: "var(--muted)",
      }}
    />
  );
}
