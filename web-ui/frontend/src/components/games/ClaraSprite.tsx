import { useEffect, useRef, useMemo } from "react";
import { compositeSprite, type SpriteLayer } from "@/lib/spriteCompositor";
import { resolveSheetUrl, SPRITE_LAYERS } from "@/lib/spriteManifest";
import type { CharacterProfile, LayerRef } from "@/api/client";

interface ClaraSpriteProps {
  mood?: "happy" | "thinking" | "excited" | "neutral" | "sad";
  talking?: boolean;
  size?: "sm" | "md" | "lg";
  personality?: string;
  profile?: CharacterProfile;
}

const moodColors: Record<string, string> = {
  happy: "#4ade80",
  thinking: "#60a5fa",
  excited: "#facc15",
  neutral: "#a78bfa",
  sad: "#f87171",
};

const moodEmotes: Record<string, string> = {
  happy: "^_^",
  thinking: "o_o",
  excited: ">w<",
  neutral: "-_-",
  sad: "T_T",
};

const sizes: Record<string, number> = {
  sm: 48,
  md: 80,
  lg: 120,
};

function isLayerRef(v: unknown): v is LayerRef {
  return v != null && typeof v === "object" && "row" in v && "col" in v;
}

export default function ClaraSprite({
  mood = "neutral",
  talking = false,
  size = "md",
  personality,
  profile,
}: ClaraSpriteProps) {
  const px = sizes[size];
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const spriteLayers = useMemo<SpriteLayer[]>(() => {
    if (!profile) return [];
    const result: SpriteLayer[] = [];
    for (const layerDef of SPRITE_LAYERS) {
      const val = profile[layerDef.id as keyof CharacterProfile] as LayerRef | Record<string, never> | undefined;
      if (!isLayerRef(val)) continue;
      const sheet = val.sheet || layerDef.sheets[0]?.filename || "";
      const url = resolveSheetUrl(layerDef.category, sheet);
      if (!url) continue;
      result.push({ imageSrc: url, row: val.row, col: val.col });
    }
    return result;
  }, [profile]);

  const hasProfile = spriteLayers.length > 0;

  useEffect(() => {
    if (!hasProfile || !canvasRef.current) return;
    compositeSprite(canvasRef.current, spriteLayers, px);
  }, [spriteLayers, px, hasProfile]);

  const label = profile?.display_name || personality || "Clara";

  return (
    <div
      style={{
        display: "inline-flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 4,
      }}
    >
      {hasProfile ? (
        <canvas
          ref={canvasRef}
          width={px}
          height={px}
          style={{
            width: px,
            height: px,
            imageRendering: "pixelated",
            borderRadius: 4,
            boxShadow: "4px 4px 0 rgba(0,0,0,0.3)",
            animation: talking ? "clara-bounce 0.4s ease-in-out infinite alternate" : undefined,
          }}
        />
      ) : (
        <div
          style={{
            width: px,
            height: px,
            backgroundColor: moodColors[mood] || moodColors.neutral,
            border: "3px solid #000",
            borderRadius: 4,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: "monospace",
            fontSize: px * 0.25,
            color: "#000",
            imageRendering: "pixelated",
            boxShadow: "4px 4px 0 rgba(0,0,0,0.3)",
            animation: talking ? "clara-bounce 0.4s ease-in-out infinite alternate" : undefined,
          }}
        >
          {moodEmotes[mood] || moodEmotes.neutral}
        </div>
      )}
      <span
        style={{
          fontFamily: "monospace",
          fontSize: 10,
          color: "#9ca3af",
          textTransform: "uppercase",
          letterSpacing: 1,
        }}
      >
        {label}
      </span>
      <style>{`
        @keyframes clara-bounce {
          from { transform: translateY(0); }
          to { transform: translateY(-4px); }
        }
      `}</style>
    </div>
  );
}
