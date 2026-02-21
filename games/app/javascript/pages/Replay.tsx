import { Head, router } from "@inertiajs/react";
import { useState } from "react";
import ClaraSprite from "../components/ClaraSprite";
import SpeechBubble from "../components/SpeechBubble";
import Card from "../components/Card";

interface PlayerInfo {
  id: number;
  name: string;
  seat: number;
  is_ai: boolean;
}

interface MoveData {
  number: number;
  player: string;
  action: Record<string, unknown>;
  commentary: string | null;
  game_data: Record<string, unknown> | null;
}

interface GameInfo {
  id: number;
  game_type: string;
  state: string;
  game_data: Record<string, unknown>;
  players: PlayerInfo[];
}

interface ReplayProps {
  game: GameInfo;
  moves: MoveData[];
}

function handValue(cards: string[]): number {
  let total = 0;
  let aces = 0;
  for (const card of cards) {
    const rank = card.slice(0, -1);
    if (rank === "A") {
      total += 11;
      aces += 1;
    } else if (["K", "Q", "J"].includes(rank)) {
      total += 10;
    } else {
      total += parseInt(rank, 10);
    }
  }
  while (total > 21 && aces > 0) {
    total -= 10;
    aces -= 1;
  }
  return total;
}

type PieceType = "r" | "b" | "R" | "B" | null;

export default function Replay({ game, moves }: ReplayProps) {
  const [currentMove, setCurrentMove] = useState(0);
  const totalMoves = moves.length;

  // Get the game state at current move
  const currentMoveData = currentMove > 0 ? moves[currentMove - 1] : null;
  const currentGameData = currentMoveData?.game_data || null;
  const commentary = currentMoveData?.commentary || null;
  const playerName = currentMoveData?.player || null;

  function goToMove(n: number) {
    setCurrentMove(Math.max(0, Math.min(n, totalMoves)));
  }

  // Render based on game type
  function renderBlackjackState() {
    const data = currentGameData as Record<string, unknown> | null;
    if (!data) {
      return (
        <div style={{ color: "#9ca3af", textAlign: "center", padding: 32 }}>
          Initial state. Press Next to step through moves.
        </div>
      );
    }

    const dealerHand = (data.dealer_hand || []) as string[];
    const hands = (data.hands || {}) as Record<string, string[]>;
    const phase = (data.phase || "player_turns") as string;

    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 24 }}>
        {/* Dealer */}
        <div>
          <div
            style={{
              fontSize: 12,
              color: "#9ca3af",
              textTransform: "uppercase",
              letterSpacing: 2,
              textAlign: "center",
              marginBottom: 8,
            }}
          >
            Dealer ({phase === "resolving" ? handValue(dealerHand) : "?"})
          </div>
          <div style={{ display: "flex", gap: 6, justifyContent: "center" }}>
            {dealerHand.map((card, i) => (
              <Card key={i} card={card} size="sm" faceDown={i === 1 && phase !== "resolving"} />
            ))}
          </div>
        </div>

        {/* Players */}
        <div style={{ display: "flex", gap: 24, flexWrap: "wrap", justifyContent: "center" }}>
          {Object.entries(hands).map(([pid, cards]) => {
            const player = game.players.find(
              (p) => p.name === pid || `player-${p.id}` === pid
            );
            const val = handValue(cards as string[]);
            return (
              <div
                key={pid}
                style={{
                  border: "2px solid #333",
                  borderRadius: 4,
                  padding: 12,
                  background: "rgba(0,0,0,0.3)",
                  minWidth: 140,
                }}
              >
                <div
                  style={{
                    fontSize: 12,
                    color: "#e5e7eb",
                    textTransform: "uppercase",
                    letterSpacing: 1,
                    marginBottom: 8,
                  }}
                >
                  {player?.name || pid}
                </div>
                <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginBottom: 6 }}>
                  {(cards as string[]).map((card, i) => (
                    <Card key={i} card={card} size="sm" />
                  ))}
                </div>
                <div
                  style={{
                    fontSize: 14,
                    fontWeight: "bold",
                    color: val > 21 ? "#ef4444" : "#facc15",
                    textAlign: "right",
                  }}
                >
                  {val}
                  {val > 21 && <span style={{ fontSize: 11, marginLeft: 4 }}>BUST</span>}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  function renderCheckersState() {
    const data = currentGameData as Record<string, unknown> | null;
    if (!data || !data.board) {
      return (
        <div style={{ color: "#9ca3af", textAlign: "center", padding: 32 }}>
          Initial state. Press Next to step through moves.
        </div>
      );
    }

    const board = data.board as PieceType[][];

    return (
      <div style={{ display: "flex", justifyContent: "center" }}>
        <div
          style={{
            display: "inline-block",
            border: "4px solid #000",
            boxShadow: "6px 6px 0 rgba(0,0,0,0.5)",
          }}
        >
          {board.map((row, rowIdx) => (
            <div key={rowIdx} style={{ display: "flex" }}>
              {row.map((cell, colIdx) => {
                const isDark = (rowIdx + colIdx) % 2 === 1;
                return (
                  <div
                    key={colIdx}
                    style={{
                      width: 40,
                      height: 40,
                      backgroundColor: isDark ? "#5c3d2e" : "#d4a574",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    {cell && (
                      <div
                        style={{
                          width: 28,
                          height: 28,
                          borderRadius: "50%",
                          background:
                            cell === "r" || cell === "R"
                              ? "#dc2626"
                              : "#1f2937",
                          border: "2px solid #000",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          fontSize: 12,
                          color: "#facc15",
                          fontWeight: "bold",
                        }}
                      >
                        {(cell === "R" || cell === "B") && "K"}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <>
      <Head title={`Replay - ${game.game_type}`} />
      <div
        style={{
          minHeight: "100vh",
          background: "linear-gradient(180deg, #0a0a0a 0%, #1a1a2e 100%)",
          fontFamily: "monospace",
          color: "#e5e7eb",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* Header */}
        <header
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "12px 24px",
            borderBottom: "2px solid #2d5a2d",
            background: "rgba(0,0,0,0.3)",
          }}
        >
          <button
            onClick={() => router.visit("/history")}
            style={{
              background: "transparent",
              border: "2px solid #555",
              borderRadius: 2,
              color: "#9ca3af",
              fontFamily: "monospace",
              fontSize: 12,
              padding: "6px 14px",
              cursor: "pointer",
              textTransform: "uppercase",
              letterSpacing: 1,
            }}
          >
            &lt; History
          </button>
          <span
            style={{
              fontSize: 18,
              color: "#4ade80",
              textTransform: "uppercase",
              letterSpacing: 3,
            }}
          >
            Replay: {game.game_type}
          </span>
          <span style={{ fontSize: 11, color: "#9ca3af" }}>
            {game.players.map((p) => p.name).join(" vs ")}
          </span>
        </header>

        {/* Game view area */}
        <div style={{ flex: 1, padding: 32 }}>
          {/* Commentary */}
          <div
            style={{
              display: "flex",
              justifyContent: "center",
              alignItems: "flex-start",
              gap: 16,
              marginBottom: 24,
              minHeight: 60,
            }}
          >
            <ClaraSprite mood="neutral" size="sm" />
            {commentary ? (
              <SpeechBubble text={commentary} speaker="Clara" direction="left" />
            ) : playerName ? (
              <SpeechBubble
                text={`${playerName} made a move.`}
                direction="left"
              />
            ) : null}
          </div>

          {/* Game state visualization */}
          {game.game_type === "blackjack" ? renderBlackjackState() : renderCheckersState()}
        </div>

        {/* Move controls */}
        <div
          style={{
            padding: "16px 32px 32px",
            borderTop: "2px solid #222",
            background: "rgba(0,0,0,0.3)",
          }}
        >
          {/* Progress bar */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              marginBottom: 16,
            }}
          >
            <span style={{ fontSize: 12, color: "#9ca3af", minWidth: 60 }}>
              Move {currentMove} / {totalMoves}
            </span>
            <div
              style={{
                flex: 1,
                height: 8,
                background: "#222",
                borderRadius: 4,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: totalMoves > 0 ? `${(currentMove / totalMoves) * 100}%` : "0%",
                  height: "100%",
                  background: "#4ade80",
                  transition: "width 0.2s",
                  borderRadius: 4,
                }}
              />
            </div>
          </div>

          {/* Move info */}
          {currentMoveData && (
            <div
              style={{
                fontSize: 13,
                color: "#9ca3af",
                textAlign: "center",
                marginBottom: 16,
              }}
            >
              <span style={{ color: "#e5e7eb", fontWeight: "bold" }}>{currentMoveData.player}</span>
              {" "}played{" "}
              <span style={{ color: "#facc15" }}>
                {typeof currentMoveData.action === "object"
                  ? (currentMoveData.action as Record<string, string>).type || JSON.stringify(currentMoveData.action)
                  : String(currentMoveData.action)}
              </span>
            </div>
          )}

          {/* Navigation buttons */}
          <div style={{ display: "flex", justifyContent: "center", gap: 12 }}>
            <button
              onClick={() => goToMove(0)}
              disabled={currentMove === 0}
              style={{
                padding: "8px 16px",
                background: currentMove === 0 ? "#222" : "#333",
                border: "2px solid #555",
                borderRadius: 2,
                color: currentMove === 0 ? "#555" : "#e5e7eb",
                fontFamily: "monospace",
                fontSize: 14,
                cursor: currentMove === 0 ? "not-allowed" : "pointer",
              }}
            >
              |&lt;
            </button>
            <button
              onClick={() => goToMove(currentMove - 1)}
              disabled={currentMove === 0}
              style={{
                padding: "8px 20px",
                background: currentMove === 0 ? "#222" : "#333",
                border: "2px solid #555",
                borderRadius: 2,
                color: currentMove === 0 ? "#555" : "#e5e7eb",
                fontFamily: "monospace",
                fontSize: 14,
                cursor: currentMove === 0 ? "not-allowed" : "pointer",
              }}
            >
              &lt; Prev
            </button>
            <button
              onClick={() => goToMove(currentMove + 1)}
              disabled={currentMove === totalMoves}
              style={{
                padding: "8px 20px",
                background: currentMove === totalMoves ? "#222" : "linear-gradient(180deg, #22c55e 0%, #16a34a 100%)",
                border: "2px solid #000",
                borderRadius: 2,
                color: currentMove === totalMoves ? "#555" : "#000",
                fontFamily: "monospace",
                fontSize: 14,
                fontWeight: "bold",
                cursor: currentMove === totalMoves ? "not-allowed" : "pointer",
                boxShadow: currentMove === totalMoves ? "none" : "3px 3px 0 rgba(0,0,0,0.5)",
              }}
            >
              Next &gt;
            </button>
            <button
              onClick={() => goToMove(totalMoves)}
              disabled={currentMove === totalMoves}
              style={{
                padding: "8px 16px",
                background: currentMove === totalMoves ? "#222" : "#333",
                border: "2px solid #555",
                borderRadius: 2,
                color: currentMove === totalMoves ? "#555" : "#e5e7eb",
                fontFamily: "monospace",
                fontSize: 14,
                cursor: currentMove === totalMoves ? "not-allowed" : "pointer",
              }}
            >
              &gt;|
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
