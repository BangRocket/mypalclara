import { useState } from "react";
import { Thread } from "@/components/assistant-ui/thread";
import { ThreadList } from "@/components/assistant-ui/thread-list";
import { ArtifactPanel } from "@/components/chat/ArtifactPanel";
import { useChatStore } from "@/stores/chatStore";
import { useArtifactStore } from "@/stores/artifactStore";
import { Button } from "@/components/ui/button";
import { PanelLeftOpen, PanelLeftClose } from "lucide-react";

export function ChatPage() {
  const connectionError = useChatStore((s) => s.connectionError);
  const connected = useChatStore((s) => s.connected);
  const panelOpen = useArtifactStore((s) => s.panelOpen);
  const hasArtifacts = useArtifactStore((s) => s.artifacts.length > 0);
  const [threadsOpen, setThreadsOpen] = useState(false);

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {connectionError && (
        <div className="shrink-0 border-b border-destructive bg-destructive/10 px-4 py-2 text-sm text-destructive">
          {connectionError}
        </div>
      )}
      {!connected && !connectionError && (
        <div className="shrink-0 border-b border-border bg-muted px-4 py-2 text-sm text-muted-foreground">
          Connecting...
        </div>
      )}
      <div className="flex flex-1 overflow-hidden">
        {/* Thread list panel */}
        {threadsOpen && (
          <div className="w-64 shrink-0 overflow-y-auto border-r border-border bg-card">
            <ThreadList />
          </div>
        )}

        {/* Chat area */}
        <div className="flex flex-1 flex-col">
          {/* Thread toggle */}
          <div className="flex shrink-0 items-center border-b border-border px-2 py-1">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setThreadsOpen(!threadsOpen)}
              title={threadsOpen ? "Hide threads" : "Show threads"}
            >
              {threadsOpen ? <PanelLeftClose size={16} /> : <PanelLeftOpen size={16} />}
            </Button>
          </div>
          <div className="flex-1 overflow-hidden">
            <Thread />
          </div>
        </div>

        {panelOpen && hasArtifacts && <ArtifactPanel />}
      </div>
    </div>
  );
}
