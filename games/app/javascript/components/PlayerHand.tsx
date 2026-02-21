import Card from "./Card";

interface PlayerHandProps {
  name: string;
  cards: string[];
  handValue: number;
  isCurrentPlayer: boolean;
  isAI: boolean;
  state: string; // "active", "stood", "busted"
  result?: string | null;
}

export default function PlayerHand({
  name,
  cards,
  handValue,
  isCurrentPlayer,
  isAI,
  state,
  result,
}: PlayerHandProps) {
  const isBusted = handValue > 21;
  const borderColor = isCurrentPlayer ? "#4ade80" : isBusted ? "#ef4444" : "#333";

  let statusText = "";
  let statusColor = "#9ca3af";
  if (result) {
    statusText = result.toUpperCase();
    statusColor = result === "won" ? "#4ade80" : result === "lost" ? "#ef4444" : "#facc15";
  } else if (isBusted) {
    statusText = "BUST";
    statusColor = "#ef4444";
  } else if (state === "stood") {
    statusText = "STAND";
    statusColor = "#60a5fa";
  }

  return (
    <div
      style={{
        border: `2px solid ${borderColor}`,
        borderRadius: 4,
        padding: 16,
        background: isCurrentPlayer ? "rgba(34,197,94,0.05)" : "rgba(0,0,0,0.3)",
        minWidth: 180,
      }}
    >
      {/* Player name */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 12,
        }}
      >
        <span
          style={{
            fontFamily: "monospace",
            fontSize: 14,
            color: isCurrentPlayer ? "#4ade80" : "#e5e7eb",
            textTransform: "uppercase",
            letterSpacing: 1,
          }}
        >
          {isAI ? `${name} (AI)` : name}
        </span>
        {statusText && (
          <span
            style={{
              fontFamily: "monospace",
              fontSize: 11,
              color: statusColor,
              fontWeight: "bold",
              letterSpacing: 1,
            }}
          >
            {statusText}
          </span>
        )}
      </div>

      {/* Cards */}
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 8 }}>
        {cards.map((card, i) => (
          <Card key={i} card={card} size="sm" />
        ))}
      </div>

      {/* Hand value */}
      <div
        style={{
          fontFamily: "monospace",
          fontSize: 16,
          fontWeight: "bold",
          color: isBusted ? "#ef4444" : "#facc15",
          textAlign: "right",
        }}
      >
        {handValue}
      </div>
    </div>
  );
}
