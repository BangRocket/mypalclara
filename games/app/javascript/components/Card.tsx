interface CardProps {
  card: string; // e.g. "A♠", "10♥", "K♦"
  faceDown?: boolean;
  size?: "sm" | "md" | "lg";
}

const suitColors: Record<string, string> = {
  "\u2660": "#e5e7eb", // spades - white
  "\u2663": "#e5e7eb", // clubs - white
  "\u2665": "#ef4444", // hearts - red
  "\u2666": "#ef4444", // diamonds - red
};

const sizes = {
  sm: { width: 50, height: 72, fontSize: 14, suitSize: 18 },
  md: { width: 70, height: 100, fontSize: 18, suitSize: 24 },
  lg: { width: 90, height: 128, fontSize: 22, suitSize: 30 },
};

export default function Card({ card, faceDown = false, size = "md" }: CardProps) {
  const dim = sizes[size];

  if (faceDown) {
    return (
      <div
        style={{
          width: dim.width,
          height: dim.height,
          background: "repeating-linear-gradient(45deg, #1e3a5f, #1e3a5f 4px, #254a73 4px, #254a73 8px)",
          border: "3px solid #000",
          borderRadius: 4,
          boxShadow: "3px 3px 0 rgba(0,0,0,0.4)",
          imageRendering: "pixelated",
        }}
      />
    );
  }

  // Parse card string: rank is everything except last char (suit)
  const suit = card.slice(-1);
  const rank = card.slice(0, -1);
  const color = suitColors[suit] || "#e5e7eb";

  return (
    <div
      style={{
        width: dim.width,
        height: dim.height,
        background: "#fefce8",
        border: "3px solid #000",
        borderRadius: 4,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "monospace",
        imageRendering: "pixelated",
        boxShadow: "3px 3px 0 rgba(0,0,0,0.4)",
        position: "relative",
        gap: 2,
      }}
    >
      {/* Top-left rank */}
      <div
        style={{
          position: "absolute",
          top: 3,
          left: 5,
          fontSize: dim.fontSize * 0.65,
          fontWeight: "bold",
          color: color,
          lineHeight: 1,
        }}
      >
        {rank}
      </div>
      {/* Center suit */}
      <div
        style={{
          fontSize: dim.suitSize,
          color: color,
          lineHeight: 1,
        }}
      >
        {suit}
      </div>
      {/* Center rank */}
      <div
        style={{
          fontSize: dim.fontSize,
          fontWeight: "bold",
          color: "#111",
          lineHeight: 1,
        }}
      >
        {rank}
      </div>
    </div>
  );
}
