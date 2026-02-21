interface CheckerPieceProps {
  color: "r" | "b" | "R" | "B";
  selected?: boolean;
  onClick?: () => void;
}

export default function CheckerPiece({ color, selected = false, onClick }: CheckerPieceProps) {
  const isRed = color === "r" || color === "R";
  const isKing = color === "R" || color === "B";
  const fillColor = isRed ? "#dc2626" : "#1f2937";
  const borderColor = isRed ? "#ef4444" : "#374151";
  const highlight = selected ? "#facc15" : "transparent";

  return (
    <div
      onClick={onClick}
      style={{
        width: 40,
        height: 40,
        borderRadius: "50%",
        background: `radial-gradient(circle at 35% 35%, ${borderColor}, ${fillColor})`,
        border: `3px solid ${selected ? "#facc15" : "#000"}`,
        boxShadow: selected
          ? `0 0 0 2px ${highlight}, 3px 3px 0 rgba(0,0,0,0.4)`
          : "3px 3px 0 rgba(0,0,0,0.4)",
        cursor: onClick ? "pointer" : "default",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        imageRendering: "pixelated",
        transition: "box-shadow 0.1s",
      }}
    >
      {isKing && (
        <span
          style={{
            fontSize: 18,
            color: "#facc15",
            fontWeight: "bold",
            textShadow: "1px 1px 0 #000",
            lineHeight: 1,
          }}
        >
          K
        </span>
      )}
    </div>
  );
}
