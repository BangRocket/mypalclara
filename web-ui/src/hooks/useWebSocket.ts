import { useEffect } from "react";
import { getToken } from "@/api/client";
import { useAuth } from "@/auth/AuthProvider";
import { useChatStore } from "@/stores/chatStore";

/**
 * Manage the chat WebSocket connection lifecycle.
 * Connects when authenticated, disconnects on logout.
 */
export function useWebSocket() {
  const { user } = useAuth();
  const connect = useChatStore((s) => s.connect);
  const disconnect = useChatStore((s) => s.disconnect);
  const connected = useChatStore((s) => s.connected);

  useEffect(() => {
    if (!user) return;

    connect(getToken() || "");

    return () => {
      disconnect();
    };
  }, [user, connect, disconnect]);

  return { connected };
}
