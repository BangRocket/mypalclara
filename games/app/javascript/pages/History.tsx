import { Head, router } from "@inertiajs/react";
import { useState } from "react";
import ClaraSprite from "../components/ClaraSprite";

interface HistoryEntry {
  id: number;
  game_type: string;
  state: string;
  created_at: string;
  players: string[];
  move_count: number;
}

interface HistoryProps {
  games: HistoryEntry[];
}

export default function History({ games }: HistoryProps) {
  const [filter, setFilter] = useState<string>("all");

  const filtered = filter === "all" ? games : games.filter((g) => g.game_type === filter);

  const totalGames = games.length;
  const totalBlackjack = games.filter((g) => g.game_type === "blackjack").length;
  const totalCheckers = games.filter((g) => g.game_type === "checkers").length;

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
    <>
      <Head title="Game History" />
      <div
        style={{
          minHeight: "100vh",
          background: "linear-gradient(180deg, #0a0a0a 0%, #1a1a2e 100%)",
          fontFamily: "monospace",
          color: "#e5e7eb",
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
            <button
              onClick={() => router.visit("/")}
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
            <h1
              style={{
                fontSize: 20,
                color: "#4ade80",
                margin: 0,
                textTransform: "uppercase",
                letterSpacing: 3,
              }}
            >
              Game History
            </h1>
          </div>
          <ClaraSprite mood="thinking" size="sm" />
        </header>

        <main style={{ maxWidth: 800, margin: "0 auto", padding: 32 }}>
          {/* Stats bar */}
          <div
            style={{
              display: "flex",
              gap: 24,
              marginBottom: 32,
              padding: "16px 24px",
              background: "#111",
              border: "2px solid #222",
              borderRadius: 4,
            }}
          >
            <div style={{ textAlign: "center" }}>
              <div style={{ color: "#e5e7eb", fontSize: 24, fontWeight: "bold" }}>{totalGames}</div>
              <div style={{ color: "#9ca3af", fontSize: 11, textTransform: "uppercase", letterSpacing: 1 }}>
                Total
              </div>
            </div>
            <div style={{ textAlign: "center" }}>
              <div style={{ color: "#4ade80", fontSize: 24, fontWeight: "bold" }}>{totalBlackjack}</div>
              <div style={{ color: "#9ca3af", fontSize: 11, textTransform: "uppercase", letterSpacing: 1 }}>
                Blackjack
              </div>
            </div>
            <div style={{ textAlign: "center" }}>
              <div style={{ color: "#d4a574", fontSize: 24, fontWeight: "bold" }}>{totalCheckers}</div>
              <div style={{ color: "#9ca3af", fontSize: 11, textTransform: "uppercase", letterSpacing: 1 }}>
                Checkers
              </div>
            </div>
          </div>

          {/* Filter tabs */}
          <div style={{ display: "flex", gap: 8, marginBottom: 24 }}>
            {[
              { key: "all", label: "All" },
              { key: "blackjack", label: "Blackjack" },
              { key: "checkers", label: "Checkers" },
            ].map((tab) => (
              <button
                key={tab.key}
                onClick={() => setFilter(tab.key)}
                style={{
                  padding: "8px 16px",
                  background: filter === tab.key ? "#1a3a1a" : "transparent",
                  border: `2px solid ${filter === tab.key ? "#4ade80" : "#333"}`,
                  borderRadius: 2,
                  color: filter === tab.key ? "#4ade80" : "#9ca3af",
                  fontFamily: "monospace",
                  fontSize: 12,
                  cursor: "pointer",
                  textTransform: "uppercase",
                  letterSpacing: 1,
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Game list */}
          {filtered.length === 0 ? (
            <p style={{ color: "#555", fontSize: 14 }}>No games found.</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {filtered.map((game) => (
                <div
                  key={game.id}
                  onClick={() => router.visit(`/history/${game.id}`)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "14px 18px",
                    background: "#111",
                    border: "2px solid #222",
                    borderRadius: 2,
                    cursor: "pointer",
                    transition: "border-color 0.1s",
                  }}
                  onMouseEnter={(e) => ((e.currentTarget as HTMLDivElement).style.borderColor = "#2d5a2d")}
                  onMouseLeave={(e) => ((e.currentTarget as HTMLDivElement).style.borderColor = "#222")}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                    <span style={{ fontSize: 20 }}>
                      {game.game_type === "blackjack" ? "\uD83C\uDCCF" : "\uD83C\uDFC1"}
                    </span>
                    <div>
                      <div style={{ fontSize: 14, textTransform: "capitalize" }}>
                        {game.game_type}
                      </div>
                      <div style={{ fontSize: 11, color: "#6b7280" }}>
                        vs {game.players.join(", ")}
                      </div>
                    </div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
                    <span style={{ fontSize: 12, color: "#6b7280" }}>
                      {game.move_count} moves
                    </span>
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
        </main>
      </div>
    </>
  );
}
