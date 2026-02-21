import { useNavigate } from "react-router-dom";
import { useEffect, useState, useCallback } from "react";
import CheckerBoard from "@/components/games/CheckerBoard";
import ClaraSprite from "@/components/games/ClaraSprite";
import SpeechBubble from "@/components/games/SpeechBubble";
import { createConsumer } from "@rails/actioncable";
import { api } from "@/api/client";

type PieceType = "r" | "b" | "R" | "B" | null;

interface LegalMove {
  from: [number, number];
  to: [number, number];
  captures?: [number, number][];
}

interface Player {
  id: number;
  user_id: number | null;
  ai_personality: string | null;
  seat_position: number;
  player_state: string;
  hand_data: Record<string, unknown>;
  result: string | null;
}

interface MoveEntry {
  id: number;
  move_number: number;
  action: Record<string, unknown>;
  clara_commentary: string | null;
  game_player_id: number;
}

interface GameData {
  board?: PieceType[][];
  captured?: Record<string, number>;
  current_color?: string;
}

export interface GameProps {
  id: number;
  game_type: string;
  state: string;
  game_data: GameData;
  move_count: number;
  current_turn: string | null;
  started_at: string | null;
  finished_at: string | null;
  players: Player[];
  moves: MoveEntry[];
}

interface CheckersPageProps {
  game: GameProps;
}

function countPieces(board: PieceType[][]): { red: number; black: number } {
  let red = 0;
  let black = 0;
  for (const row of board) {
    for (const cell of row) {
      if (cell === "r" || cell === "R") red++;
      if (cell === "b" || cell === "B") black++;
    }
  }
  return { red, black };
}

export default function Checkers({ game: initialGame }: CheckersPageProps) {
  const navigate = useNavigate();
  const [game, setGame] = useState(initialGame);
  const [selectedSquare, setSelectedSquare] = useState<[number, number] | null>(null);
  const [commentary, setCommentary] = useState<string | null>(null);
  const [mood, setMood] = useState<"happy" | "thinking" | "excited" | "neutral" | "sad">("neutral");
  const [loading, setLoading] = useState(false);

  // Re-sync when initialGame prop changes
  useEffect(() => {
    setGame(initialGame);
  }, [initialGame]);

  const board: PieceType[][] = game.game_data.board || Array.from({ length: 8 }, () => Array(8).fill(null));
  const isGameOver = game.state === "resolved";

  // Determine player color: seat 0 = red, seat 1 = black
  const humanPlayer = game.players.find((p) => p.user_id !== null);
  const aiPlayer = game.players.find((p) => p.ai_personality !== null);
  const playerColor: "red" | "black" = humanPlayer?.seat_position === 0 ? "red" : "black";
  const playerPieces = playerColor === "red" ? ["r", "R"] : ["b", "B"];

  // Determine whose turn it is (simple alternation based on move count)
  // Red always goes first in checkers. Seat 0 = red = even moves, Seat 1 = black = odd moves.
  const isPlayerTurn = game.move_count % 2 === (playerColor === "red" ? 0 : 1);

  const lastCommentary = game.moves.filter((m) => m.clara_commentary).slice(-1)[0];

  useEffect(() => {
    if (lastCommentary?.clara_commentary) {
      setCommentary(lastCommentary.clara_commentary);
    }
  }, [lastCommentary?.clara_commentary]);

  // ActionCable subscription
  useEffect(() => {
    const cable = createConsumer();
    const subscription = cable.subscriptions.create(
      { channel: "GameChannel", game_id: game.id },
      {
        received(data: unknown) {
          const { type, game: updatedGame, commentary: newCommentary, mood: newMood } = data as { type: string; game?: GameProps; commentary?: string; mood?: string };
          if (type === "game_update" && updatedGame) {
            setGame(updatedGame);
            if (newCommentary) setCommentary(newCommentary);
            if (newMood) setMood(newMood as typeof mood);
            setLoading(false);
          }
        },
      }
    );

    return () => {
      subscription.unsubscribe();
      cable.disconnect();
    };
  }, [game.id]);

  // Fetch legal moves from game state
  // Since we don't have legal moves in props, we compute them client-side from the board
  // This mirrors the server-side CheckersEngine logic
  function computeLegalMoves(): LegalMove[] {
    const pieces = playerPieces;
    const jumps: LegalMove[] = [];
    const simpleMoves: LegalMove[] = [];

    for (let row = 0; row < 8; row++) {
      for (let col = 0; col < 8; col++) {
        const piece = board[row][col];
        if (!piece || !pieces.includes(piece)) continue;

        const directions = getMoveDirections(piece);
        const opponents = getOpponentPieces(piece);

        // Check jumps
        for (const [dr, dc] of directions) {
          const midRow = row + dr;
          const midCol = col + dc;
          const landRow = row + dr * 2;
          const landCol = col + dc * 2;

          if (
            landRow >= 0 && landRow < 8 && landCol >= 0 && landCol < 8 &&
            board[midRow]?.[midCol] && opponents.includes(board[midRow][midCol]!) &&
            board[landRow]?.[landCol] === null
          ) {
            jumps.push({
              from: [row, col],
              to: [landRow, landCol],
              captures: [[midRow, midCol]],
            });
          }
        }

        // Check simple moves
        for (const [dr, dc] of directions) {
          const newRow = row + dr;
          const newCol = col + dc;
          if (
            newRow >= 0 && newRow < 8 && newCol >= 0 && newCol < 8 &&
            board[newRow]?.[newCol] === null
          ) {
            simpleMoves.push({ from: [row, col], to: [newRow, newCol] });
          }
        }
      }
    }

    // Mandatory jumps
    return jumps.length > 0 ? jumps : simpleMoves;
  }

  function getMoveDirections(piece: string): [number, number][] {
    switch (piece) {
      case "r": return [[-1, -1], [-1, 1]];
      case "b": return [[1, -1], [1, 1]];
      case "R": case "B": return [[-1, -1], [-1, 1], [1, -1], [1, 1]];
      default: return [];
    }
  }

  function getOpponentPieces(piece: string): string[] {
    if (piece === "r" || piece === "R") return ["b", "B"];
    return ["r", "R"];
  }

  const legalMoves = isPlayerTurn && !isGameOver ? computeLegalMoves() : [];

  function handleSquareClick(row: number, col: number) {
    if (loading || isGameOver || !isPlayerTurn) return;

    const piece = board[row][col];

    // If clicking on own piece, select it
    if (piece && playerPieces.includes(piece)) {
      setSelectedSquare([row, col]);
      return;
    }

    // If a piece is selected and clicking a legal target, make the move
    if (selectedSquare) {
      const move = legalMoves.find(
        (m) =>
          m.from[0] === selectedSquare[0] &&
          m.from[1] === selectedSquare[1] &&
          m.to[0] === row &&
          m.to[1] === col
      );

      if (move) {
        makeMove(move);
        setSelectedSquare(null);
      } else {
        // Deselect if clicking empty non-target square
        setSelectedSquare(null);
      }
    }
  }

  const triggerAIMove = useCallback(() => {
    if (!aiPlayer || isGameOver) return;

    setLoading(true);
    api.games
      .aiMove(game.id, { game_player_id: aiPlayer.id })
      .then((data) => {
        if (data.game) {
          setGame(data.game);
          if (data.commentary) setCommentary(data.commentary);
          if (data.mood) setMood(data.mood as typeof mood);
        }
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [game.id, aiPlayer, isGameOver]);

  function makeMove(move: LegalMove) {
    setLoading(true);
    api.games
      .move(game.id, { move_type: JSON.stringify(move) })
      .then((data) => {
        if (data.game) {
          setGame(data.game);
          setLoading(false);

          // Trigger AI move after delay
          if (data.game.state === "in_progress") {
            setTimeout(() => triggerAIMove(), 1000);
          }
        }
      })
      .catch(() => setLoading(false));
  }

  const pieces = countPieces(board);

  // Determine winner
  let winnerText = "";
  if (isGameOver && humanPlayer?.result) {
    winnerText = humanPlayer.result === "won" ? "You Win!" : humanPlayer.result === "draw" ? "Draw" : "You Lose";
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "linear-gradient(180deg, #1a0a0a 0%, #0a0a1a 100%)",
        fontFamily: "monospace",
        color: "#e5e7eb",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Top bar */}
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "12px 24px",
          borderBottom: "2px solid #5c3d2e",
          background: "rgba(0,0,0,0.3)",
        }}
      >
        <button
          onClick={() => navigate("/games")}
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
          &lt; Lobby
        </button>
        <span
          style={{
            fontSize: 18,
            color: "#d4a574",
            textTransform: "uppercase",
            letterSpacing: 3,
          }}
        >
          Checkers
        </span>
        <span
          style={{
            fontSize: 11,
            color: isGameOver ? "#ef4444" : "#4ade80",
            textTransform: "uppercase",
            letterSpacing: 1,
          }}
        >
          {isGameOver ? "Game Over" : isPlayerTurn ? "Your Turn" : "AI Thinking..."}
        </span>
      </header>

      {/* Main game area */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 24,
          padding: 24,
        }}
      >
        {/* Clara with commentary */}
        <div style={{ display: "flex", alignItems: "flex-start", gap: 16 }}>
          <ClaraSprite mood={mood} size="sm" talking={loading} />
          {commentary && <SpeechBubble text={commentary} speaker="Clara" direction="left" />}
        </div>

        {/* Captured pieces display */}
        <div
          style={{
            display: "flex",
            gap: 32,
            fontSize: 13,
            color: "#9ca3af",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div
              style={{
                width: 16,
                height: 16,
                borderRadius: "50%",
                background: "#dc2626",
                border: "2px solid #000",
              }}
            />
            <span>Red: {pieces.red}</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div
              style={{
                width: 16,
                height: 16,
                borderRadius: "50%",
                background: "#1f2937",
                border: "2px solid #374151",
              }}
            />
            <span>Black: {pieces.black}</span>
          </div>
        </div>

        {/* Board */}
        <CheckerBoard
          board={board}
          legalMoves={legalMoves}
          playerColor={playerColor}
          selectedSquare={selectedSquare}
          onSquareClick={handleSquareClick}
          disabled={loading || isGameOver || !isPlayerTurn}
        />

        {/* Turn / status */}
        <div
          style={{
            textAlign: "center",
            fontSize: 14,
            color: "#9ca3af",
          }}
        >
          {isGameOver ? (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16 }}>
              <span
                style={{
                  fontSize: 24,
                  fontWeight: "bold",
                  color:
                    humanPlayer?.result === "won"
                      ? "#4ade80"
                      : humanPlayer?.result === "draw"
                      ? "#facc15"
                      : "#ef4444",
                  textTransform: "uppercase",
                  letterSpacing: 3,
                }}
              >
                {winnerText}
              </span>
              <button
                onClick={() => navigate("/games")}
                style={{
                  padding: "10px 24px",
                  background: "linear-gradient(180deg, #22c55e 0%, #16a34a 100%)",
                  color: "#000",
                  border: "3px solid #000",
                  borderRadius: 2,
                  fontFamily: "monospace",
                  fontSize: 14,
                  fontWeight: "bold",
                  cursor: "pointer",
                  textTransform: "uppercase",
                  letterSpacing: 2,
                  boxShadow: "3px 3px 0 rgba(0,0,0,0.5)",
                }}
              >
                Back to Lobby
              </button>
            </div>
          ) : loading ? (
            <span style={{ color: "#facc15" }}>Waiting for AI...</span>
          ) : isPlayerTurn ? (
            <span>
              You are playing{" "}
              <span style={{ color: playerColor === "red" ? "#ef4444" : "#9ca3af", fontWeight: "bold" }}>
                {playerColor}
              </span>
              . Select a piece to move.
            </span>
          ) : (
            <span>
              {aiPlayer?.ai_personality || "AI"} is thinking...
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
