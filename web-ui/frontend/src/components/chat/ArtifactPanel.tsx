import { useArtifactStore } from "@/stores/artifactStore";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { CheckIcon, CopyIcon, XIcon } from "lucide-react";
import { useState } from "react";

export function ArtifactPanel() {
  const artifacts = useArtifactStore((s) => s.artifacts);
  const activeId = useArtifactStore((s) => s.activeId);
  const setActive = useArtifactStore((s) => s.setActive);
  const removeArtifact = useArtifactStore((s) => s.removeArtifact);
  const closePanel = useArtifactStore((s) => s.closePanel);

  const active = artifacts.find((a) => a.id === activeId);

  return (
    <div className="flex h-full w-[40%] min-w-72 max-w-[50%] flex-col border-l border-border bg-card">
      {/* Tab bar */}
      <div className="flex items-center gap-1 border-b border-border px-2 py-1">
        <div className="flex flex-1 items-center gap-1 overflow-x-auto">
          {artifacts.map((a) => (
            <button
              key={a.id}
              onClick={() => setActive(a.id)}
              className={cn(
                "flex items-center gap-1 rounded-md px-2 py-1 text-xs transition-colors",
                a.id === activeId
                  ? "bg-muted text-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <span className="max-w-24 truncate">{a.title}</span>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  removeArtifact(a.id);
                }}
                className="ml-0.5 rounded p-0.5 hover:bg-muted-foreground/20"
              >
                <XIcon className="size-3" />
              </button>
            </button>
          ))}
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="size-7 shrink-0"
          onClick={closePanel}
        >
          <XIcon className="size-4" />
        </Button>
      </div>

      {/* Content */}
      {active ? (
        <div className="flex flex-1 flex-col overflow-hidden">
          <div className="flex items-center justify-between border-b border-border px-3 py-2">
            <div>
              <h3 className="text-sm font-medium">{active.title}</h3>
              {active.language && (
                <span className="text-xs text-muted-foreground">
                  {active.language}
                </span>
              )}
            </div>
            <CopyButton text={active.content} />
          </div>
          <div className="flex-1 overflow-auto">
            <pre className="p-3 text-sm leading-relaxed">
              <code>{active.content}</code>
            </pre>
          </div>
        </div>
      ) : (
        <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
          No artifact selected
        </div>
      )}
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Button variant="ghost" size="icon" className="size-7" onClick={handleCopy}>
      {copied ? (
        <CheckIcon className="size-3.5 text-green-500" />
      ) : (
        <CopyIcon className="size-3.5" />
      )}
    </Button>
  );
}
