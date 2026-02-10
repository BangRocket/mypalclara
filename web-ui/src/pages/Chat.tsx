import { Thread } from "@/components/assistant-ui/thread";
import { ThreadList } from "@/components/assistant-ui/thread-list";
import { ArtifactPanel } from "@/components/chat/ArtifactPanel";
import { ChatRuntimeProvider } from "@/components/chat/ChatRuntimeProvider";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useArtifactStore } from "@/stores/artifactStore";
import { useChatStore } from "@/stores/chatStore";

export function ChatPage() {
  useWebSocket();
  const connectionError = useChatStore((s) => s.connectionError);
  const connected = useChatStore((s) => s.connected);
  const panelOpen = useArtifactStore((s) => s.panelOpen);
  const hasArtifacts = useArtifactStore((s) => s.artifacts.length > 0);

  return (
    <ChatRuntimeProvider>
      <div className="flex h-full">
        {/* Thread list sidebar */}
        <aside className="hidden w-64 shrink-0 border-r border-border bg-card p-3 md:block">
          <ThreadList />
        </aside>

        {/* Main chat area */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {connectionError && (
            <div className="border-b border-destructive/30 bg-destructive/10 px-4 py-2 text-center text-sm text-destructive">
              {connectionError}
            </div>
          )}
          {!connected && !connectionError && (
            <div className="border-b border-border bg-muted/50 px-4 py-2 text-center text-sm text-muted-foreground">
              Connecting to chat...
            </div>
          )}
          <div className="flex flex-1 overflow-hidden">
            <div className="flex-1">
              <Thread />
            </div>
            {panelOpen && hasArtifacts && <ArtifactPanel />}
          </div>
        </div>
      </div>
    </ChatRuntimeProvider>
  );
}
