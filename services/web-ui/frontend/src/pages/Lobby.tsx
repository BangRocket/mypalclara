import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import ClaraSprite from "@/components/games/ClaraSprite";
import GameCard from "@/components/games/GameCard";
import { api } from "@/api/client";

interface GameStats {
  played: number;
  won: number;
}

interface RecentGame {
  id: number;
  game_type: string;
  state: string;
  created_at: string;
  players: string[];
}

interface LobbyData {
  user: { name: string; avatar: string | null };
  recent_games: RecentGame[];
  stats: {
    blackjack: GameStats;
    checkers: GameStats;
  };
}

type GameType = "blackjack" | "checkers";

const AI_PERSONALITIES = [
  { id: "clara", name: "Clara", desc: "Friendly & encouraging" },
  { id: "flo", name: "Flo", desc: "Competitive & sassy" },
  { id: "clarissa", name: "Clarissa", desc: "Analytical & calm" },
];

export default function Lobby() {
  const navigate = useNavigate();
  const { data, isLoading } = useQuery<LobbyData>({
    queryKey: ["lobby"],
    queryFn: () => api.games.lobby(),
  });

  const [showNewGame, setShowNewGame] = useState(false);
  const [selectedGame, setSelectedGame] = useState<GameType | null>(null);
  const [selectedAI, setSelectedAI] = useState<string[]>(["clara"]);
  const [creating, setCreating] = useState(false);

  if (isLoading || !data) {
    return (
      <div style={{ minHeight: "100vh", background: "#0a0a0a", display: "flex", alignItems: "center", justifyContent: "center", color: "#9ca3af", fontFamily: "monospace" }}>
        Loading...
      </div>
    );
  }

  const { user, recent_games, stats } = data;

  function startNewGame(gameType: GameType) {
    setSelectedGame(gameType);
    setSelectedAI(["clara"]);
    setShowNewGame(true);
  }

  function toggleAI(id: string) {
    setSelectedAI((prev) =>
      prev.includes(id) ? prev.filter((a) => a !== id) : [...prev, id]
    );
  }

  function createGame() {
    if (!selectedGame || selectedAI.length === 0) return;
    setCreating(true);
    api.games
      .create({ game_type: selectedGame, ai_players: selectedAI })
      .then((res: { game?: { id: number } }) => {
        if (res.game) {
          navigate(`/games/${res.game.id}`);
        }
      })
      .catch(() => setCreating(false));
  }

  function cancelNewGame() {
    setShowNewGame(false);
    setSelectedGame(null);
    setSelectedAI(["clara"]);
  }

  const stateLabels: Record<string, string> = {
    waiting: "Waiting",
    in_progress: "In Progress",
    resolved: "Finished",
  };

  const stateColors: Record<string, string> = {
    waiting: "#facc15",
    in_progress: "#4ade80",
    resolved: "#9ca3af",
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "linear-gradient(180deg, #0a0a0a 0%, #1a1a2e 100%)",
        fontFamily: "monospace",
        color: "#e5e7eb",
        imageRendering: "pixelated",
      }}
    >
      {/* Header */}
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "16px 32px",
          borderBottom: "2px solid #2d5a2d",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <ClaraSprite mood="happy" size="sm" />
          <h1
            style={{
              fontSize: 24,
              color: "#4ade80",
              margin: 0,
              textTransform: "uppercase",
              letterSpacing: 3,
            }}
          >
            Clara's Game Room
          </h1>
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            color: "#9ca3af",
            fontSize: 14,
          }}
        >
          <span>{user.name}</span>
        </div>
      </header>

      {/* Main content */}
      <main style={{ maxWidth: 900, margin: "0 auto", padding: 32 }}>
        {/* Game selection */}
        <section style={{ marginBottom: 48 }}>
          <h2
            style={{
              fontSize: 16,
              color: "#9ca3af",
              textTransform: "uppercase",
              letterSpacing: 2,
              marginBottom: 24,
            }}
          >
            Choose Your Game
          </h2>
          <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
            <GameCard
              gameType="blackjack"
              label="Blackjack"
              icon="\uD83C\uDCCF"
              stats={stats.blackjack}
              onPlay={() => startNewGame("blackjack")}
            />
            <GameCard
              gameType="checkers"
              label="Checkers"
              icon="\uD83C\uDFC1"
              stats={stats.checkers}
              onPlay={() => startNewGame("checkers")}
            />
          </div>
        </section>

        {/* New Game Modal */}
        {showNewGame && (
          <div
            style={{
              position: "fixed",
              inset: 0,
              background: "rgba(0,0,0,0.8)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 100,
            }}
          >
            <div
              style={{
                background: "#1a1a2e",
                border: "3px solid #2d5a2d",
                borderRadius: 4,
                padding: 32,
                maxWidth: 480,
                width: "90%",
                boxShadow: "8px 8px 0 rgba(0,0,0,0.5)",
              }}
            >
              <h3
                style={{
                  color: "#4ade80",
                  fontSize: 18,
                  textTransform: "uppercase",
                  letterSpacing: 2,
                  marginTop: 0,
                  marginBottom: 24,
                }}
              >
                New {selectedGame === "blackjack" ? "Blackjack" : "Checkers"} Game
              </h3>

              <p style={{ color: "#9ca3af", fontSize: 14, marginBottom: 16 }}>
                {selectedGame === "blackjack"
                  ? "Pick AI opponents to join your table:"
                  : "Pick an AI opponent:"}
              </p>

              <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 24 }}>
                {AI_PERSONALITIES.map((ai) => {
                  const isSelected = selectedAI.includes(ai.id);
                  return (
                    <button
                      key={ai.id}
                      onClick={() => {
                        if (selectedGame === "checkers") {
                          setSelectedAI([ai.id]);
                        } else {
                          toggleAI(ai.id);
                        }
                      }}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        padding: "12px 16px",
                        background: isSelected ? "#1a3a1a" : "#111",
                        border: `2px solid ${isSelected ? "#4ade80" : "#333"}`,
                        borderRadius: 2,
                        color: isSelected ? "#4ade80" : "#9ca3af",
                        fontFamily: "monospace",
                        fontSize: 14,
                        cursor: "pointer",
                        transition: "all 0.1s",
                      }}
                    >
                      <span style={{ fontWeight: "bold" }}>{ai.name}</span>
                      <span style={{ fontSize: 12 }}>{ai.desc}</span>
                    </button>
                  );
                })}
              </div>

              <div style={{ display: "flex", gap: 12, justifyContent: "flex-end" }}>
                <button
                  onClick={cancelNewGame}
                  style={{
                    padding: "8px 20px",
                    background: "transparent",
                    border: "2px solid #555",
                    borderRadius: 2,
                    color: "#9ca3af",
                    fontFamily: "monospace",
                    fontSize: 14,
                    cursor: "pointer",
                  }}
                >
                  Cancel
                </button>
                <button
                  onClick={createGame}
                  disabled={creating || selectedAI.length === 0}
                  style={{
                    padding: "8px 20px",
                    background: creating ? "#555" : "linear-gradient(180deg, #22c55e 0%, #16a34a 100%)",
                    border: "2px solid #000",
                    borderRadius: 2,
                    color: "#000",
                    fontFamily: "monospace",
                    fontSize: 14,
                    fontWeight: "bold",
                    cursor: creating ? "wait" : "pointer",
                    boxShadow: "3px 3px 0 rgba(0,0,0,0.5)",
                  }}
                >
                  {creating ? "Creating..." : "Start Game"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Recent Games */}
        <section>
          <h2
            style={{
              fontSize: 16,
              color: "#9ca3af",
              textTransform: "uppercase",
              letterSpacing: 2,
              marginBottom: 24,
            }}
          >
            Recent Games
          </h2>
          {recent_games.length === 0 ? (
            <p style={{ color: "#555", fontSize: 14 }}>
              No games yet. Pick a game above to get started!
            </p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {recent_games.map((game) => (
                <div
                  key={game.id}
                  onClick={() => {
                    if (game.state === "in_progress") {
                      navigate(`/games/${game.id}`);
                    } else {
                      navigate(`/games/history/${game.id}`);
                    }
                  }}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "12px 16px",
                    background: "#111",
                    border: "2px solid #222",
                    borderRadius: 2,
                    cursor: "pointer",
                    transition: "border-color 0.1s",
                  }}
                  onMouseEnter={(e) =>
                    ((e.currentTarget as HTMLDivElement).style.borderColor = "#2d5a2d")
                  }
                  onMouseLeave={(e) =>
                    ((e.currentTarget as HTMLDivElement).style.borderColor = "#222")
                  }
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                    <span style={{ fontSize: 20 }}>
                      {game.game_type === "blackjack" ? "\uD83C\uDCCF" : "\uD83C\uDFC1"}
                    </span>
                    <div>
                      <div style={{ fontSize: 14, color: "#e5e7eb", textTransform: "capitalize" }}>
                        {game.game_type}
                      </div>
                      <div style={{ fontSize: 11, color: "#6b7280" }}>
                        vs {game.players.filter((p) => p !== user.name).join(", ")}
                      </div>
                    </div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                    <span
                      style={{
                        fontSize: 11,
                        color: stateColors[game.state] || "#9ca3af",
                        textTransform: "uppercase",
                        letterSpacing: 1,
                      }}
                    >
                      {stateLabels[game.state] || game.state}
                    </span>
                    <span style={{ fontSize: 11, color: "#555" }}>
                      {new Date(game.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
