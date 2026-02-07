import { useState } from "react";
import { ChevronDown, ChevronRight, CheckCircle, XCircle, Loader2 } from "lucide-react";
import type { ToolEvent } from "@/stores/chatStore";

interface ToolCallDisplayProps {
  tool: ToolEvent;
}

export function ToolCallDisplay({ tool }: ToolCallDisplayProps) {
  const [expanded, setExpanded] = useState(false);
  const done = tool.success !== undefined;

  return (
    <div className="border border-border rounded-lg text-xs overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-1.5 hover:bg-surface-overlay transition"
      >
        {done ? (
          tool.success ? (
            <CheckCircle size={14} className="text-success shrink-0" />
          ) : (
            <XCircle size={14} className="text-danger shrink-0" />
          )
        ) : (
          <Loader2 size={14} className="text-accent animate-spin shrink-0" />
        )}
        <span className="text-text-secondary">{tool.emoji || "\u2699\ufe0f"}</span>
        <span className="font-medium text-text-primary">{tool.tool_name}</span>
        {tool.description && <span className="text-text-muted truncate">— {tool.description}</span>}
        <span className="ml-auto">
          {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        </span>
      </button>

      {expanded && tool.output_preview && (
        <div className="px-3 py-2 border-t border-border bg-surface-overlay">
          <pre className="text-text-secondary whitespace-pre-wrap font-mono">{tool.output_preview}</pre>
          {tool.duration_ms != null && (
            <p className="text-text-muted mt-1">{tool.duration_ms}ms</p>
          )}
        </div>
      )}
    </div>
  );
}
