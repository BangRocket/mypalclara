interface CardProps {
  card: string; // e.g. "A♠", "10♥", "K♦"
  faceDown?: boolean;
  size?: "sm" | "md" | "lg";
}

// Size dimensions for the image tags
const sizes = {
  sm: { width: 50, height: 72 },
  md: { width: 70, height: 100 },
  lg: { width: 90, height: 128 },
};

// Map card suits to asset naming convention
const suitToAsset: Record<string, string> = {
  "S": "spade",  // ♠
  "C": "clubs",  // ♣
  "H": "heart",  // ♥
  "D": "diamond", // ♦
};

// Map card ranks to asset numbering (1=Ace, 11=J, 12=Q, 13=K)
const rankToAsset: Record<string, number> = {
  "A": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "10": 10,
  "J": 11, "Q": 12, "K": 13,
};

// Import the card back image
import cardBack from "@/assets/game-assets/cards/playing/playing-cards/card-backs/blue_back_suits.png";

function getCardImagePath(card: string): string {
  const suit = card.slice(-1);
  const rank = card.slice(0, -1);
  
  const suitAsset = suitToAsset[suit];
  const rankAsset = rankToAsset[rank];
  
  if (!suitAsset || !rankAsset) {
    throw new Error(`Invalid card format: ${card}`);
  }
  
  return new URL(
    `../../assets/game-assets/cards/playing/playing-cards/card_${suitAsset}_${rankAsset}.png`,
    import.meta.url
  ).href;
}

export default function Card({ card, faceDown = false, size = "md" }: CardProps) {
  const dim = sizes[size];

  if (faceDown) {
    return (
      <img
        src={cardBack}
        alt="Card back"
        style={{
          width: dim.width,
          height: dim.height,
          imageRendering: "pixelated",
          boxShadow: "3px 3px 0 rgba(0,0,0,0.4)",
        }}
      />
    );
  }

  const cardSrc = getCardImagePath(card);

  return (
    <img
      src={cardSrc}
      alt={card}
      style={{
        width: dim.width,
        height: dim.height,
        imageRendering: "pixelated",
        boxShadow: "3px 3px 0 rgba(0,0,0,0.4)",
      }}
    />
  );
}
