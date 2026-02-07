import { ChatView } from "@/components/chat/ChatView";
import { useWebSocket } from "@/hooks/useWebSocket";

export function ChatPage() {
  useWebSocket();

  return (
    <div className="h-full">
      <ChatView />
    </div>
  );
}
