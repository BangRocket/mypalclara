import { useEffect } from "react";
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

    // We need the JWT token — read from cookie isn't accessible from JS (httpOnly).
    // Instead, store it in sessionStorage during OAuth callback.
    const token = sessionStorage.getItem("clara_token");
    if (token) {
      connect(token);
    }

    return () => {
      disconnect();
    };
  }, [user, connect, disconnect]);

  return { connected };
}
