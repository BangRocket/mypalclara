import { create } from "zustand";
import { sessions as sessionsApi, type ChatSession, type ChatMessage } from "@/api/client";

export interface ToolEvent {
  tool_name: string;
  step?: number;
  description?: string | null;
  emoji?: string;
  success?: boolean;
  output_preview?: string | null;
  duration_ms?: number | null;
}

export interface StreamMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  tools: ToolEvent[];
  streaming: boolean;
}

export type ModelTier = "low" | "mid" | "high";

interface ChatStore {
  // Current thread
  messages: StreamMessage[];
  currentThreadId: string | null; // null = new thread

  // Thread list
  threads: ChatSession[];
  archivedThreads: ChatSession[];
  threadsLoading: boolean;

  // Connection
  connected: boolean;
  connectionError: string | null;
  ws: WebSocket | null;
  activeRequestId: string | null;
  selectedTier: ModelTier;

  // Actions
  connect: (token: string) => void;
  disconnect: () => void;
  sendMessage: (content: string, tier?: string, attachments?: { name: string; type: string; base64: string }[]) => void;
  cancel: () => void;
  setTier: (tier: ModelTier) => void;

  // Thread actions
  loadThreads: () => Promise<void>;
  switchToThread: (threadId: string) => Promise<void>;
  switchToNewThread: () => void;
  renameThread: (threadId: string, title: string) => Promise<void>;
  archiveThread: (threadId: string) => Promise<void>;
  unarchiveThread: (threadId: string) => Promise<void>;
  deleteThread: (threadId: string) => Promise<void>;
}

let msgCounter = 0;

/** Convert API messages to our StreamMessage format. */
function apiToStreamMessages(messages: ChatMessage[]): StreamMessage[] {
  return messages.map((m, i) => ({
    id: `hist-${i}`,
    role: m.role as "user" | "assistant",
    content: m.content,
    tools: [],
    streaming: false,
  }));
}

export const useChatStore = create<ChatStore>((set, get) => ({
  messages: [],
  currentThreadId: null,
  threads: [],
  archivedThreads: [],
  threadsLoading: false,
  connected: false,
  connectionError: null,
  ws: null,
  activeRequestId: null,
  selectedTier: "mid",

  connect: (token: string) => {
    const apiUrl = import.meta.env.VITE_API_URL || "";
    const params = token ? `?token=${token}` : "";
    let wsUrl: string;
    if (apiUrl) {
      const parsed = new URL(apiUrl);
      const wsProtocol = parsed.protocol === "https:" ? "wss:" : "ws:";
      wsUrl = `${wsProtocol}//${parsed.host}/ws/chat${params}`;
    } else {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      wsUrl = `${protocol}//${window.location.host}/ws/chat${params}`;
    }
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => set({ connected: true, connectionError: null });

    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);
      const { messages } = get();

      switch (data.type) {
        case "response_start": {
          const assistantMsg: StreamMessage = {
            id: `a-${++msgCounter}`,
            role: "assistant",
            content: "",
            tools: [],
            streaming: true,
          };
          set({ messages: [...messages, assistantMsg] });
          break;
        }

        case "chunk": {
          const last = messages[messages.length - 1];
          if (last?.role === "assistant" && last.streaming) {
            const updated = { ...last, content: data.accumulated || last.content + data.text };
            set({ messages: [...messages.slice(0, -1), updated] });
          }
          break;
        }

        case "tool_start": {
          const last = messages[messages.length - 1];
          if (last?.role === "assistant") {
            const tool: ToolEvent = {
              tool_name: data.tool_name,
              step: data.step,
              description: data.description,
              emoji: data.emoji,
            };
            const updated = { ...last, tools: [...last.tools, tool] };
            set({ messages: [...messages.slice(0, -1), updated] });
          }
          break;
        }

        case "tool_result": {
          const last = messages[messages.length - 1];
          if (last?.role === "assistant") {
            const tools = last.tools.map((t) =>
              t.tool_name === data.tool_name && t.success === undefined
                ? { ...t, success: data.success, output_preview: data.output_preview, duration_ms: data.duration_ms }
                : t,
            );
            set({ messages: [...messages.slice(0, -1), { ...last, tools }] });
          }
          break;
        }

        case "response_end": {
          const last = messages[messages.length - 1];
          if (last?.role === "assistant") {
            set({
              messages: [...messages.slice(0, -1), { ...last, content: data.full_text, streaming: false }],
              activeRequestId: null,
            });
          }
          // Refresh thread list after response completes (new session may have been created)
          get().loadThreads();
          break;
        }

        case "error": {
          const errorMsg: StreamMessage = {
            id: `e-${++msgCounter}`,
            role: "assistant",
            content: `Error: ${data.message}`,
            tools: [],
            streaming: false,
          };
          set({ messages: [...messages, errorMsg], activeRequestId: null });
          break;
        }
      }
    };

    ws.onclose = (e) => {
      const errorMap: Record<number, string> = {
        4001: "Authentication failed",
        4500: "Server error",
        4503: "Chat gateway not available — is the gateway running?",
      };
      const connectionError = errorMap[e.code] || null;
      set({ connected: false, ws: null, connectionError });
    };
    ws.onerror = () => set({ connected: false });

    set({ ws });
  },

  disconnect: () => {
    get().ws?.close();
    set({ ws: null, connected: false });
  },

  sendMessage: (content: string, tier?: string, attachments?: { name: string; type: string; base64: string }[]) => {
    const { ws, messages, currentThreadId } = get();
    if (!ws || ws.readyState !== WebSocket.OPEN) return;

    const userMsg: StreamMessage = {
      id: `u-${++msgCounter}`,
      role: "user",
      content,
      tools: [],
      streaming: false,
    };
    set({ messages: [...messages, userMsg] });

    const payload: Record<string, unknown> = { type: "message", content, tier };
    if (currentThreadId) {
      payload.session_id = currentThreadId;
    }
    if (attachments?.length) {
      payload.attachments = attachments;
    }
    ws.send(JSON.stringify(payload));
  },

  cancel: () => {
    const { ws, activeRequestId } = get();
    if (ws && activeRequestId) {
      ws.send(JSON.stringify({ type: "cancel", request_id: activeRequestId }));
    }
  },

  setTier: (tier: ModelTier) => set({ selectedTier: tier }),

  // ── Thread management ─────────────────────────────────────────────

  loadThreads: async () => {
    set({ threadsLoading: true });
    try {
      const [regular, archived] = await Promise.all([
        sessionsApi.list({ limit: 100 }),
        sessionsApi.list({ limit: 100, archived: true }),
      ]);
      set({
        threads: regular.sessions,
        archivedThreads: archived.sessions,
        threadsLoading: false,
      });
    } catch {
      set({ threadsLoading: false });
    }
  },

  switchToThread: async (threadId: string) => {
    if (get().currentThreadId === threadId) return;
    try {
      const session = await sessionsApi.get(threadId);
      set({
        currentThreadId: threadId,
        messages: apiToStreamMessages(session.messages),
      });
    } catch {
      // Session not found or access denied — stay on current thread
    }
  },

  switchToNewThread: () => {
    set({ currentThreadId: null, messages: [] });
  },

  renameThread: async (threadId: string, title: string) => {
    await sessionsApi.rename(threadId, title);
    await get().loadThreads();
  },

  archiveThread: async (threadId: string) => {
    await sessionsApi.archive(threadId);
    // If we archived the active thread, switch to new
    if (get().currentThreadId === threadId) {
      set({ currentThreadId: null, messages: [] });
    }
    await get().loadThreads();
  },

  unarchiveThread: async (threadId: string) => {
    await sessionsApi.unarchive(threadId);
    await get().loadThreads();
  },

  deleteThread: async (threadId: string) => {
    await sessionsApi.delete(threadId);
    if (get().currentThreadId === threadId) {
      set({ currentThreadId: null, messages: [] });
    }
    await get().loadThreads();
  },
}));
