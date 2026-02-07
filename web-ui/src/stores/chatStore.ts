import { create } from "zustand";

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

interface ChatStore {
  messages: StreamMessage[];
  connected: boolean;
  ws: WebSocket | null;
  activeRequestId: string | null;

  connect: (token: string) => void;
  disconnect: () => void;
  sendMessage: (content: string, tier?: string, attachments?: { name: string; type: string; base64: string }[]) => void;
  cancel: () => void;
}

let msgCounter = 0;

export const useChatStore = create<ChatStore>((set, get) => ({
  messages: [],
  connected: false,
  ws: null,
  activeRequestId: null,

  connect: (token: string) => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/chat?token=${token}`);

    ws.onopen = () => set({ connected: true });

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

    ws.onclose = () => set({ connected: false, ws: null });
    ws.onerror = () => set({ connected: false });

    set({ ws });
  },

  disconnect: () => {
    get().ws?.close();
    set({ ws: null, connected: false });
  },

  sendMessage: (content: string, tier?: string, attachments?: { name: string; type: string; base64: string }[]) => {
    const { ws, messages } = get();
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
}));
