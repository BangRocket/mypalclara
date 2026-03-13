/**
 * Direct WebSocket connection to the Clara gateway (port 18789).
 *
 * Handles:
 * - Clerk JWT authentication via query param
 * - Adapter registration on connect
 * - Heartbeat pings every 25s
 * - Reconnect with exponential backoff (1s -> 60s)
 * - Dispatching gateway events to the chat store
 */

import { useEffect, useRef, useCallback } from "react";
import { useAuth, useUser } from "@clerk/react";
import { useChatStore } from "@/stores/chatStore";

const WS_URL = import.meta.env.VITE_GATEWAY_WS_URL || "ws://localhost:18789";

/** Generate a stable-ish web client node ID. */
function makeNodeId(): string {
  const stored = sessionStorage.getItem("clara-node-id");
  if (stored) return stored;
  const id = `web-${crypto.randomUUID()}`;
  sessionStorage.setItem("clara-node-id", id);
  return id;
}

const PING_INTERVAL_MS = 25_000;
const INITIAL_BACKOFF_MS = 1_000;
const MAX_BACKOFF_MS = 60_000;

/**
 * Manage the gateway WebSocket connection lifecycle.
 *
 * Connects when authenticated, disconnects on unmount/logout.
 * Returns `{ connected, send, disconnect }`.
 */
export function useGatewayWebSocket() {
  const { isSignedIn, getToken } = useAuth();
  const { user } = useUser();

  const wsRef = useRef<WebSocket | null>(null);
  const pingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const backoffRef = useRef(INITIAL_BACKOFF_MS);
  const intentionalCloseRef = useRef(false);
  const nodeIdRef = useRef<string>(makeNodeId());
  const sessionIdRef = useRef<string | null>(null);

  const store = useChatStore;

  // ── Helpers ──────────────────────────────────────────────────────────

  const clearTimers = useCallback(() => {
    if (pingTimerRef.current) {
      clearInterval(pingTimerRef.current);
      pingTimerRef.current = null;
    }
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  const startPing = useCallback((ws: WebSocket) => {
    if (pingTimerRef.current) clearInterval(pingTimerRef.current);
    pingTimerRef.current = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "ping" }));
      }
    }, PING_INTERVAL_MS);
  }, []);

  // ── Send ─────────────────────────────────────────────────────────────

  const send = useCallback((payload: Record<string, unknown>) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify(payload));
  }, []);

  // ── Disconnect ───────────────────────────────────────────────────────

  const disconnect = useCallback(() => {
    intentionalCloseRef.current = true;
    clearTimers();
    const ws = wsRef.current;
    if (ws) {
      ws.close(1000, "Client disconnect");
      wsRef.current = null;
    }
    store.getState().setConnected(false);
    store.getState().setConnectionError(null);
  }, [clearTimers, store]);

  // ── Connect ──────────────────────────────────────────────────────────

  const connect = useCallback(
    async (token: string) => {
      // Tear down any existing connection first
      if (wsRef.current) {
        intentionalCloseRef.current = true;
        wsRef.current.close(1000, "Reconnecting");
        wsRef.current = null;
      }
      intentionalCloseRef.current = false;

      const params = token ? `?token=${encodeURIComponent(token)}` : "";
      const ws = new WebSocket(`${WS_URL}${params}`);
      wsRef.current = ws;

      ws.onopen = () => {
        backoffRef.current = INITIAL_BACKOFF_MS;
        store.getState().setConnected(true);
        store.getState().setConnectionError(null);

        // Send registration
        const registration: Record<string, unknown> = {
          type: "register",
          node_id: nodeIdRef.current,
          platform: "web",
          capabilities: ["streaming", "attachments"],
        };
        // If we have a previous session_id, include it for reconnection
        if (sessionIdRef.current) {
          registration.metadata = { previous_session_id: sessionIdRef.current };
        }
        ws.send(JSON.stringify(registration));

        // Start heartbeat
        startPing(ws);
      };

      ws.onmessage = (event) => {
        let data: Record<string, unknown>;
        try {
          data = JSON.parse(event.data as string);
        } catch {
          return; // Ignore non-JSON messages
        }

        const s = store.getState();
        const type = data.type as string;

        switch (type) {
          case "registered":
            // Store session_id for potential reconnection
            sessionIdRef.current = data.session_id as string;
            break;

          case "response_start":
            s.onResponseStart(data.request_id as string);
            break;

          case "response_chunk": {
            const content = (data.accumulated as string) ?? (data.chunk as string) ?? "";
            s.onChunk(content, !!(data.accumulated));
            break;
          }

          case "tool_start":
            s.onToolStart(
              data.tool_name as string,
              data.step as number | undefined,
              data.description as string | undefined,
              data.emoji as string | undefined,
            );
            break;

          case "tool_result":
            s.onToolResult(
              data.tool_name as string,
              data.success as boolean,
              data.output_preview as string | undefined,
              data.duration_ms as number | undefined,
            );
            break;

          case "response_end":
            s.onResponseEnd(
              data.full_text as string,
              data.tool_count as number | undefined,
              data.files as string[] | undefined,
            );
            break;

          case "error":
            s.onError(data.message as string);
            break;

          case "pong":
            // Heartbeat response — no action needed
            break;

          default:
            // Unknown event type — ignore
            break;
        }
      };

      ws.onclose = (event) => {
        clearTimers();
        wsRef.current = null;

        const errorMap: Record<number, string> = {
          4001: "Authentication failed",
          4500: "Server error",
          4503: "Chat gateway not available -- is the gateway running?",
        };
        const connectionError = errorMap[event.code] || null;
        store.getState().setConnected(false);
        if (connectionError) {
          store.getState().setConnectionError(connectionError);
        }

        // Reconnect unless intentionally closed or auth failure
        if (!intentionalCloseRef.current && event.code !== 4001) {
          const delay = backoffRef.current;
          backoffRef.current = Math.min(delay * 2, MAX_BACKOFF_MS);

          reconnectTimerRef.current = setTimeout(async () => {
            try {
              const freshToken = await getToken();
              if (freshToken) {
                connect(freshToken);
              }
            } catch {
              // Token fetch failed — retry with backoff
              reconnectTimerRef.current = setTimeout(async () => {
                try {
                  const t = await getToken();
                  if (t) connect(t);
                } catch {
                  // Give up for now; user will need to reload
                }
              }, backoffRef.current);
            }
          }, delay);
        }
      };

      ws.onerror = () => {
        // onerror is always followed by onclose — let onclose handle state
      };
    },
    [clearTimers, getToken, startPing, store],
  );

  // ── Lifecycle ────────────────────────────────────────────────────────

  useEffect(() => {
    if (!isSignedIn) {
      disconnect();
      return;
    }

    getToken().then((token) => {
      if (token) connect(token);
    });

    return () => {
      disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isSignedIn]);

  // ── Public API ───────────────────────────────────────────────────────

  const connected = useChatStore((s) => s.connected);

  /**
   * Send a chat message through the gateway WebSocket.
   *
   * This is a convenience wrapper that builds the full `message` payload
   * expected by the gateway protocol.
   */
  const sendMessage = useCallback(
    (
      content: string,
      options?: {
        branchId?: string | null;
        tierOverride?: string;
        attachments?: { type: string; filename: string; media_type?: string; base64_data?: string }[];
        userId?: string;
        displayName?: string;
      },
    ) => {
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) return;

      const msgId = crypto.randomUUID();
      const s = store.getState();

      // Add user message to the store
      s.addUserMessage(content, options?.attachments);

      const payload: Record<string, unknown> = {
        type: "message",
        id: msgId,
        user: {
          id: options?.userId || user?.id || "web-user",
          platform_id: user?.id || "web-user",
          name: options?.displayName || user?.username || user?.firstName || "Web User",
          display_name:
            options?.displayName ||
            user?.fullName ||
            user?.firstName ||
            "Web User",
        },
        channel: { id: "web", type: "dm" },
        content,
        branch_id: options?.branchId ?? s.activeBranchId,
        tier_override: options?.tierOverride ?? s.selectedTier,
        attachments: options?.attachments ?? [],
        metadata: {},
      };

      ws.send(JSON.stringify(payload));
      s.setActiveRequestId(msgId);
    },
    [store, user],
  );

  /** Cancel the current in-flight request. */
  const cancel = useCallback(() => {
    const requestId = store.getState().activeRequestId;
    if (requestId) {
      send({ type: "cancel", request_id: requestId });
    }
  }, [send, store]);

  return { connected, send, sendMessage, cancel, disconnect };
}
