interface ClaraSpriteProps {
  mood?: "happy" | "thinking" | "excited" | "neutral" | "sad";
  talking?: boolean;
  size?: "sm" | "md" | "lg";
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

export default function ClaraSprite({
  mood = "neutral",
  talking = false,
  size = "md",
}: ClaraSpriteProps) {
  const px = sizes[size];
  const color = moodColors[mood] || moodColors.neutral;
  const emote = moodEmotes[mood] || moodEmotes.neutral;

  return (
    <div
      style={{
        display: "inline-flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 4,
      }}
    >
      <div
        style={{
          width: px,
          height: px,
          backgroundColor: color,
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
        {emote}
      </div>
      <span
        style={{
          fontFamily: "monospace",
          fontSize: 10,
          color: "#9ca3af",
          textTransform: "uppercase",
          letterSpacing: 1,
        }}
      >
        Clara
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
