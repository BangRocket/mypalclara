import CheckerPiece from "./CheckerPiece";

type PieceType = "r" | "b" | "R" | "B" | null;

interface LegalMove {
  from: [number, number];
  to: [number, number];
  captures?: [number, number][];
}

interface CheckerBoardProps {
  board: PieceType[][];
  legalMoves: LegalMove[];
  playerColor: "red" | "black";
  selectedSquare: [number, number] | null;
  onSquareClick: (row: number, col: number) => void;
  disabled?: boolean;
}

export default function CheckerBoard({
  board,
  legalMoves,
  playerColor,
  selectedSquare,
  onSquareClick,
  disabled = false,
}: CheckerBoardProps) {
  const playerPieces = playerColor === "red" ? ["r", "R"] : ["b", "B"];

  // Calculate which squares are legal move targets from the selected piece
  const legalTargets = new Set<string>();
  if (selectedSquare) {
    for (const move of legalMoves) {
      if (move.from[0] === selectedSquare[0] && move.from[1] === selectedSquare[1]) {
        legalTargets.add(`${move.to[0]},${move.to[1]}`);
      }
    }
  }

  // Calculate which pieces can move
  const movablePieces = new Set<string>();
  for (const move of legalMoves) {
    movablePieces.add(`${move.from[0]},${move.from[1]}`);
  }

  return (
    <div
      style={{
        display: "inline-block",
        border: "4px solid #000",
        boxShadow: "6px 6px 0 rgba(0,0,0,0.5)",
        imageRendering: "pixelated",
      }}
    >
      {board.map((row, rowIdx) => (
        <div key={rowIdx} style={{ display: "flex" }}>
          {row.map((cell, colIdx) => {
            const isDark = (rowIdx + colIdx) % 2 === 1;
            const isSelected =
              selectedSquare !== null &&
              selectedSquare[0] === rowIdx &&
              selectedSquare[1] === colIdx;
            const isLegalTarget = legalTargets.has(`${rowIdx},${colIdx}`);
            const canMove = !disabled && cell !== null && playerPieces.includes(cell) && movablePieces.has(`${rowIdx},${colIdx}`);

            let bgColor: string;
            if (isSelected) {
              bgColor = "#a16207";
            } else if (isLegalTarget) {
              bgColor = "#365314";
            } else if (isDark) {
              bgColor = "#5c3d2e";
            } else {
              bgColor = "#d4a574";
            }

            return (
              <div
                key={colIdx}
                onClick={() => {
                  if (disabled) return;
                  onSquareClick(rowIdx, colIdx);
                }}
                style={{
                  width: 56,
                  height: 56,
                  backgroundColor: bgColor,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: (canMove || isLegalTarget) ? "pointer" : "default",
                  position: "relative",
                }}
              >
                {cell && (
                  <CheckerPiece
                    color={cell}
                    selected={isSelected}
                    onClick={canMove ? () => onSquareClick(rowIdx, colIdx) : undefined}
                  />
                )}
                {isLegalTarget && !cell && (
                  <div
                    style={{
                      width: 16,
                      height: 16,
                      borderRadius: "50%",
                      background: "rgba(74, 222, 128, 0.5)",
                      border: "2px solid rgba(74, 222, 128, 0.7)",
                    }}
                  />
                )}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
