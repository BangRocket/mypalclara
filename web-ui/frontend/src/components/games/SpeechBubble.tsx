interface SpeechBubbleProps {
  text: string;
  speaker?: string;
  direction?: "left" | "right" | "bottom";
}

export default function SpeechBubble({ text, speaker, direction = "bottom" }: SpeechBubbleProps) {
  if (!text) return null;

  const arrowStyle: React.CSSProperties = {
    position: "absolute",
    width: 0,
    height: 0,
  };

  if (direction === "bottom") {
    Object.assign(arrowStyle, {
      bottom: -10,
      left: 20,
      borderLeft: "8px solid transparent",
      borderRight: "8px solid transparent",
      borderTop: "10px solid #2d5a2d",
    });
  } else if (direction === "left") {
    Object.assign(arrowStyle, {
      left: -10,
      top: 12,
      borderTop: "8px solid transparent",
      borderBottom: "8px solid transparent",
      borderRight: "10px solid #2d5a2d",
    });
  } else {
    Object.assign(arrowStyle, {
      right: -10,
      top: 12,
      borderTop: "8px solid transparent",
      borderBottom: "8px solid transparent",
      borderLeft: "10px solid #2d5a2d",
    });
  }

  return (
    <div style={{ position: "relative", display: "inline-block" }}>
      <div
        style={{
          background: "#0d1f0d",
          border: "2px solid #2d5a2d",
          borderRadius: 4,
          padding: "8px 14px",
          fontFamily: "monospace",
          fontSize: 13,
          color: "#e5e7eb",
          maxWidth: 280,
          imageRendering: "pixelated",
          boxShadow: "3px 3px 0 rgba(0,0,0,0.3)",
        }}
      >
        {speaker && (
          <div
            style={{
              fontSize: 10,
              color: "#4ade80",
              textTransform: "uppercase",
              letterSpacing: 1,
              marginBottom: 4,
            }}
          >
            {speaker}
          </div>
        )}
        <div style={{ lineHeight: 1.4 }}>{text}</div>
      </div>
      <div style={arrowStyle} />
    </div>
  );
}
