import Card from "./Card";
import ClaraSprite from "./ClaraSprite";
import SpeechBubble from "./SpeechBubble";

interface DealerAreaProps {
  dealerHand: string[];
  dealerValue: number;
  gamePhase: string; // "dealing", "player_turns", "resolving"
  commentary?: string | null;
  mood?: "happy" | "thinking" | "excited" | "neutral" | "sad";
}

export default function DealerArea({
  dealerHand,
  dealerValue,
  gamePhase,
  commentary,
  mood = "neutral",
}: DealerAreaProps) {
  const showSecondCard = gamePhase === "resolving";
  const isBusted = dealerValue > 21 && showSecondCard;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 16,
        padding: "24px 0",
      }}
    >
      {/* Clara with speech bubble */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 16 }}>
        <ClaraSprite mood={mood} size="md" talking={!!commentary} />
        {commentary && <SpeechBubble text={commentary} speaker="Clara" direction="left" />}
      </div>

      {/* Dealer label */}
      <div
        style={{
          fontFamily: "monospace",
          fontSize: 12,
          color: "#9ca3af",
          textTransform: "uppercase",
          letterSpacing: 2,
        }}
      >
        Dealer
      </div>

      {/* Dealer cards */}
      <div style={{ display: "flex", gap: 8 }}>
        {dealerHand.map((card, i) => (
          <Card
            key={i}
            card={card}
            faceDown={i === 1 && !showSecondCard}
            size="md"
          />
        ))}
      </div>

      {/* Dealer value */}
      {showSecondCard && (
        <div
          style={{
            fontFamily: "monospace",
            fontSize: 18,
            fontWeight: "bold",
            color: isBusted ? "#ef4444" : "#facc15",
          }}
        >
          {dealerValue}
          {isBusted && (
            <span style={{ color: "#ef4444", fontSize: 14, marginLeft: 8 }}>BUST</span>
          )}
        </div>
      )}
      {!showSecondCard && dealerHand.length > 0 && (
        <div
          style={{
            fontFamily: "monospace",
            fontSize: 14,
            color: "#9ca3af",
          }}
        >
          Showing: {dealerHand[0]}
        </div>
      )}
    </div>
  );
}
