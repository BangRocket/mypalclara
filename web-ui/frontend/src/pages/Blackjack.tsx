import { useNavigate } from "react-router-dom";
import { useEffect, useState, useCallback } from "react";
import DealerArea from "@/components/games/DealerArea";
import PlayerHand from "@/components/games/PlayerHand";
import SpeechBubble from "@/components/games/SpeechBubble";
import { createConsumer } from "@rails/actioncable";
import { api } from "@/api/client";

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
  action: { type: string };
  clara_commentary: string | null;
  game_player_id: number;
}

interface GameData {
  deck?: string[];
  dealer_hand?: string[];
  hands?: Record<string, string[]>;
  stood?: string[];
  phase?: string;
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

interface BlackjackPageProps {
  game: GameProps;
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

function playerIdentifier(p: Player): string {
  return p.ai_personality || `player-${p.user_id}`;
}

export default function Blackjack({ game: initialGame }: BlackjackPageProps) {
  const navigate = useNavigate();
  const [game, setGame] = useState(initialGame);
  const [commentary, setCommentary] = useState<string | null>(null);
  const [mood, setMood] = useState<"happy" | "thinking" | "excited" | "neutral" | "sad">("neutral");
  const [loading, setLoading] = useState(false);
  const [aiThinking, setAiThinking] = useState<number | null>(null);

  // Re-sync when initialGame prop changes
  useEffect(() => {
    setGame(initialGame);
  }, [initialGame]);

  // Find the human player
  const humanPlayer = game.players.find((p) => p.user_id !== null);
  const humanId = humanPlayer ? playerIdentifier(humanPlayer) : "";
  const humanHand = game.game_data.hands?.[humanId] || [];
  const humanValue = handValue(humanHand);
  const isHumanBusted = humanValue > 21;
  const humanStood = (game.game_data.stood || []).includes(humanId);
  const isGameOver = game.state === "resolved";
  const canAct = !isGameOver && !isHumanBusted && !humanStood && !loading;

  const dealerHand = game.game_data.dealer_hand || [];
  const dealerValue = handValue(dealerHand);
  const gamePhase = game.game_data.phase || "player_turns";

  // Get last commentary from moves
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
        received(data: { type: string; game?: GameProps; commentary?: string; mood?: string }) {
          if (data.type === "game_update" && data.game) {
            setGame(data.game);
            if (data.commentary) setCommentary(data.commentary);
            if (data.mood) setMood(data.mood as typeof mood);
          }
        },
      }
    );

    return () => {
      subscription.unsubscribe();
      cable.disconnect();
    };
  }, [game.id]);

  // Auto-trigger AI moves after human acts
  const triggerAIMoves = useCallback(async () => {
    const aiPlayers = game.players.filter(
      (p) => p.ai_personality && p.player_state === "active"
    );

    for (const aiPlayer of aiPlayers) {
      const aiId = playerIdentifier(aiPlayer);
      const aiHand = game.game_data.hands?.[aiId] || [];
      const aiVal = handValue(aiHand);
      const aiStood = (game.game_data.stood || []).includes(aiId);

      if (aiVal > 21 || aiStood) continue;

      setAiThinking(aiPlayer.id);
      try {
        const data = await api.games.aiMove(game.id, { game_player_id: aiPlayer.id });
        if (data.game) {
          setGame(data.game);
          if (data.commentary) setCommentary(data.commentary);
          if (data.mood) setMood(data.mood as typeof mood);
        }
      } catch {
        // Silently handle - game state will be updated via ActionCable
      }
      setAiThinking(null);
    }
  }, [game]);

  function makeMove(moveType: string) {
    if (!canAct) return;
    setLoading(true);

    api.games
      .move(game.id, { move_type: moveType })
      .then((data) => {
        if (data.game) {
          setGame(data.game);
          setLoading(false);

          // Trigger AI moves after a short delay
          if (data.game.state === "in_progress") {
            setTimeout(() => triggerAIMoves(), 800);
          }
        }
      })
      .catch(() => setLoading(false));
  }

  // Legal moves for the human player
  const legalMoves: string[] = [];
  if (canAct) {
    legalMoves.push("hit", "stand");
    if (humanHand.length === 2) legalMoves.push("double_down");
  }

  const moveLabels: Record<string, string> = {
    hit: "Hit",
    stand: "Stand",
    double_down: "Double Down",
  };

  const moveColors: Record<string, string> = {
    hit: "#22c55e",
    stand: "#3b82f6",
    double_down: "#eab308",
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "radial-gradient(ellipse at center, #1a3a1a 0%, #0a1a0a 70%)",
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
          borderBottom: "2px solid #2d5a2d",
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
            color: "#4ade80",
            textTransform: "uppercase",
            letterSpacing: 3,
          }}
        >
          Blackjack
        </span>
        <span
          style={{
            fontSize: 11,
            color: isGameOver ? "#ef4444" : "#4ade80",
            textTransform: "uppercase",
            letterSpacing: 1,
          }}
        >
          {isGameOver ? "Game Over" : "In Progress"}
        </span>
      </header>

      {/* Dealer area */}
      <DealerArea
        dealerHand={dealerHand}
        dealerValue={dealerValue}
        gamePhase={gamePhase}
        commentary={commentary}
        mood={mood}
      />

      {/* Divider */}
      <div
        style={{
          height: 2,
          background: "linear-gradient(90deg, transparent, #2d5a2d, transparent)",
          margin: "0 32px",
        }}
      />

      {/* Player hands */}
      <div
        style={{
          flex: 1,
          padding: "24px 32px",
          display: "flex",
          flexDirection: "column",
          gap: 16,
        }}
      >
        {/* AI Player hands with speech bubbles */}
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", justifyContent: "center" }}>
          {game.players
            .filter((p) => p.ai_personality)
            .map((p) => {
              const pid = playerIdentifier(p);
              const cards = game.game_data.hands?.[pid] || [];
              const val = handValue(cards);
              const stood = (game.game_data.stood || []).includes(pid);
              const lastAIComment = game.moves
                .filter((m) => m.game_player_id === p.id && m.clara_commentary)
                .slice(-1)[0];

              return (
                <div key={p.id} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
                  {aiThinking === p.id && (
                    <SpeechBubble text="Hmm, let me think..." speaker={p.ai_personality || "AI"} />
                  )}
                  {!aiThinking && lastAIComment?.clara_commentary && (
                    <SpeechBubble
                      text={lastAIComment.clara_commentary}
                      speaker={p.ai_personality || "AI"}
                    />
                  )}
                  <PlayerHand
                    name={p.ai_personality || "AI"}
                    cards={cards}
                    handValue={val}
                    isCurrentPlayer={false}
                    isAI={true}
                    state={val > 21 ? "busted" : stood ? "stood" : "active"}
                    result={p.result}
                  />
                </div>
              );
            })}
        </div>

        {/* Human player hand */}
        {humanPlayer && (
          <div style={{ display: "flex", justifyContent: "center", marginTop: 16 }}>
            <PlayerHand
              name="You"
              cards={humanHand}
              handValue={humanValue}
              isCurrentPlayer={true}
              isAI={false}
              state={isHumanBusted ? "busted" : humanStood ? "stood" : "active"}
              result={humanPlayer.result}
            />
          </div>
        )}
      </div>

      {/* Action buttons */}
      <div
        style={{
          padding: "16px 32px 32px",
          display: "flex",
          justifyContent: "center",
          gap: 16,
        }}
      >
        {isGameOver ? (
          <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
            <span
              style={{
                fontSize: 20,
                fontWeight: "bold",
                color: humanPlayer?.result === "won" ? "#4ade80" : humanPlayer?.result === "draw" ? "#facc15" : "#ef4444",
                textTransform: "uppercase",
                letterSpacing: 2,
              }}
            >
              {humanPlayer?.result === "won" ? "You Win!" : humanPlayer?.result === "draw" ? "Push" : "You Lose"}
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
        ) : (
          legalMoves.map((move) => (
            <button
              key={move}
              onClick={() => makeMove(move)}
              disabled={!canAct || loading}
              style={{
                padding: "12px 32px",
                background: canAct
                  ? `linear-gradient(180deg, ${moveColors[move]} 0%, ${moveColors[move]}cc 100%)`
                  : "#333",
                color: canAct ? "#000" : "#666",
                border: "3px solid #000",
                borderRadius: 2,
                fontFamily: "monospace",
                fontSize: 16,
                fontWeight: "bold",
                cursor: canAct ? "pointer" : "not-allowed",
                textTransform: "uppercase",
                letterSpacing: 2,
                boxShadow: canAct ? "3px 3px 0 rgba(0,0,0,0.5)" : "none",
                opacity: loading ? 0.7 : 1,
              }}
            >
              {moveLabels[move] || move}
            </button>
          ))
        )}
      </div>
    </div>
  );
}
