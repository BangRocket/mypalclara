interface GameCardProps {
  gameType: string;
  label: string;
  icon: string;
  stats: { played: number; won: number };
  onPlay: () => void;
}

export default function GameCard({ gameType, label, icon, stats, onPlay }: GameCardProps) {
  const winRate = stats.played > 0 ? Math.round((stats.won / stats.played) * 100) : 0;

  return (
    <div
      style={{
        background: "linear-gradient(180deg, #1a3a1a 0%, #0d1f0d 100%)",
        border: "3px solid #2d5a2d",
        borderRadius: 4,
        padding: 24,
        fontFamily: "monospace",
        imageRendering: "pixelated",
        boxShadow: "6px 6px 0 rgba(0,0,0,0.4)",
        minWidth: 220,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 16,
      }}
    >
      <div style={{ fontSize: 48 }}>{icon}</div>
      <h3
        style={{
          color: "#4ade80",
          fontSize: 20,
          margin: 0,
          textTransform: "uppercase",
          letterSpacing: 2,
        }}
      >
        {label}
      </h3>

      <div
        style={{
          display: "flex",
          gap: 24,
          color: "#9ca3af",
          fontSize: 12,
        }}
      >
        <div style={{ textAlign: "center" }}>
          <div style={{ color: "#e5e7eb", fontSize: 18, fontWeight: "bold" }}>{stats.played}</div>
          <div>PLAYED</div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ color: "#facc15", fontSize: 18, fontWeight: "bold" }}>{stats.won}</div>
          <div>WON</div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ color: "#60a5fa", fontSize: 18, fontWeight: "bold" }}>{winRate}%</div>
          <div>RATE</div>
        </div>
      </div>

      <button
        onClick={onPlay}
        style={{
          background: "linear-gradient(180deg, #22c55e 0%, #16a34a 100%)",
          color: "#000",
          border: "3px solid #000",
          borderRadius: 2,
          padding: "10px 32px",
          fontFamily: "monospace",
          fontSize: 16,
          fontWeight: "bold",
          textTransform: "uppercase",
          letterSpacing: 2,
          cursor: "pointer",
          boxShadow: "3px 3px 0 rgba(0,0,0,0.5)",
          transition: "transform 0.1s",
        }}
        onMouseDown={(e) => {
          (e.target as HTMLButtonElement).style.transform = "translate(2px, 2px)";
          (e.target as HTMLButtonElement).style.boxShadow = "1px 1px 0 rgba(0,0,0,0.5)";
        }}
        onMouseUp={(e) => {
          (e.target as HTMLButtonElement).style.transform = "translate(0, 0)";
          (e.target as HTMLButtonElement).style.boxShadow = "3px 3px 0 rgba(0,0,0,0.5)";
        }}
        onMouseLeave={(e) => {
          (e.target as HTMLButtonElement).style.transform = "translate(0, 0)";
          (e.target as HTMLButtonElement).style.boxShadow = "3px 3px 0 rgba(0,0,0,0.5)";
        }}
      >
        Play
      </button>
    </div>
  );
}
