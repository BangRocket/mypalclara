/**
 * Zustand store for branch-aware chat state.
 *
 * This store manages messages, branches, connection status, and streaming
 * state. It does NOT contain WebSocket connection logic -- that lives in
 * `useGatewayWebSocket`. The hook calls the store's action methods to
 * dispatch incoming gateway events.
 */

import { create } from "zustand";
import { sessions as sessionsApi, type ChatSession, type ChatMessage as ApiChatMessage } from "@/api/client";

// ── Types ──────────────────────────────────────────────────────────────

export type ModelTier = "low" | "mid" | "high";

export interface ToolEvent {
  type: "tool_start" | "tool_result";
  tool_name: string;
  step?: number;
  description?: string | null;
  emoji?: string;
  success?: boolean;
  output_preview?: string | null;
  duration_ms?: number | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  toolEvents?: ToolEvent[];
  attachments?: unknown[];
  streaming?: boolean;
  created_at?: string;
}

export interface BranchInfo {
  id: string;
  conversation_id: string;
  parent_branch_id: string | null;
  fork_message_id: string | null;
  name: string | null;
  status: "active" | "merged" | "archived";
  created_at: string;
  merged_at: string | null;
}

// ── Backward-compat alias ──────────────────────────────────────────────
// ChatRuntimeProvider and other consumers reference `StreamMessage` and its
// `tools` field. Keep an alias so existing code doesn't break.
export type StreamMessage = ChatMessage & { tools: ToolEvent[] };

// ── Store Interface ────────────────────────────────────────────────────

interface ChatState {
  // Connection
  connected: boolean;
  connectionError: string | null;

  // Branch state
  branches: BranchInfo[];
  activeBranchId: string | null;

  // Messages for active branch
  messages: ChatMessage[];

  // Thread list (sessions -- kept for backward compat with ChatRuntimeProvider)
  threads: ChatSession[];
  archivedThreads: ChatSession[];
  threadsLoading: boolean;
  currentThreadId: string | null;

  // UI state
  selectedTier: ModelTier;
  streaming: boolean;
  activeRequestId: string | null;

  // ── Connection actions ───────────────────────────────────────────────
  setConnected: (connected: boolean) => void;
  setConnectionError: (error: string | null) => void;

  // ── Branch actions ───────────────────────────────────────────────────
  setBranches: (branches: BranchInfo[]) => void;
  setActiveBranch: (branchId: string | null) => void;

  // ── Message actions ──────────────────────────────────────────────────
  setMessages: (messages: ChatMessage[]) => void;
  addUserMessage: (content: string, attachments?: unknown[]) => string;
  setActiveRequestId: (id: string | null) => void;

  // ── Tier ─────────────────────────────────────────────────────────────
  setTier: (tier: ModelTier) => void;

  // ── Streaming event handlers ─────────────────────────────────────────
  onResponseStart: (requestId: string) => void;
  onChunk: (content: string, isAccumulated: boolean) => void;
  onToolStart: (name: string, step?: number, description?: string, emoji?: string) => void;
  onToolResult: (name: string, success: boolean, outputPreview?: string, durationMs?: number) => void;
  onResponseEnd: (fullText: string, toolCount?: number, files?: string[]) => void;
  onError: (message: string) => void;

  // ── Thread management (backward compat) ──────────────────────────────
  loadThreads: () => Promise<void>;
  switchToThread: (threadId: string) => Promise<void>;
  switchToNewThread: () => void;
  renameThread: (threadId: string, title: string) => Promise<void>;
  archiveThread: (threadId: string) => Promise<void>;
  unarchiveThread: (threadId: string) => Promise<void>;
  deleteThread: (threadId: string) => Promise<void>;

  // ── Legacy compat (used by ChatRuntimeProvider) ──────────────────────
  sendMessage: (content: string, tier?: string, attachments?: { name: string; type: string; base64: string }[]) => void;
  cancel: () => void;
}

// ── Helpers ────────────────────────────────────────────────────────────

let msgCounter = 0;

/** Convert API messages to our ChatMessage format. */
function apiToMessages(messages: ApiChatMessage[]): ChatMessage[] {
  return messages.map((m, i) => ({
    id: `hist-${i}`,
    role: m.role as "user" | "assistant",
    content: m.content,
    toolEvents: [],
    streaming: false,
  }));
}

// ── Store ──────────────────────────────────────────────────────────────

export const useChatStore = create<ChatState>((set, get) => ({
  // ── Initial state ────────────────────────────────────────────────────
  connected: false,
  connectionError: null,

  branches: [],
  activeBranchId: null,

  messages: [],

  threads: [],
  archivedThreads: [],
  threadsLoading: false,
  currentThreadId: null,

  selectedTier: "mid",
  streaming: false,
  activeRequestId: null,

  // ── Connection ───────────────────────────────────────────────────────

  setConnected: (connected) => set({ connected }),

  setConnectionError: (error) => set({ connectionError: error }),

  // ── Branches ─────────────────────────────────────────────────────────

  setBranches: (branches) => set({ branches }),

  setActiveBranch: (branchId) => set({ activeBranchId: branchId }),

  // ── Messages ─────────────────────────────────────────────────────────

  setMessages: (messages) => set({ messages }),

  addUserMessage: (content, attachments) => {
    const id = `u-${++msgCounter}`;
    const userMsg: ChatMessage = {
      id,
      role: "user",
      content,
      toolEvents: [],
      attachments,
      streaming: false,
    };
    set((state) => ({ messages: [...state.messages, userMsg] }));
    return id;
  },

  setActiveRequestId: (id) => set({ activeRequestId: id }),

  // ── Tier ─────────────────────────────────────────────────────────────

  setTier: (tier) => set({ selectedTier: tier }),

  // ── Streaming event handlers ─────────────────────────────────────────

  onResponseStart: (requestId) => {
    const assistantMsg: ChatMessage = {
      id: `a-${++msgCounter}`,
      role: "assistant",
      content: "",
      toolEvents: [],
      streaming: true,
    };
    set((state) => ({
      messages: [...state.messages, assistantMsg],
      streaming: true,
      activeRequestId: requestId,
    }));
  },

  onChunk: (content, isAccumulated) => {
    set((state) => {
      const messages = [...state.messages];
      const last = messages[messages.length - 1];
      if (!last || last.role !== "assistant" || !last.streaming) return state;

      const updated: ChatMessage = {
        ...last,
        content: isAccumulated ? content : last.content + content,
      };
      messages[messages.length - 1] = updated;
      return { messages };
    });
  },

  onToolStart: (name, step, description, emoji) => {
    set((state) => {
      const messages = [...state.messages];
      const last = messages[messages.length - 1];
      if (!last || last.role !== "assistant") return state;

      const toolEvent: ToolEvent = {
        type: "tool_start",
        tool_name: name,
        step,
        description,
        emoji,
      };
      const updated: ChatMessage = {
        ...last,
        toolEvents: [...(last.toolEvents ?? []), toolEvent],
      };
      messages[messages.length - 1] = updated;
      return { messages };
    });
  },

  onToolResult: (name, success, outputPreview, durationMs) => {
    set((state) => {
      const messages = [...state.messages];
      const last = messages[messages.length - 1];
      if (!last || last.role !== "assistant") return state;

      const toolEvents = (last.toolEvents ?? []).map((t) =>
        t.tool_name === name && t.success === undefined
          ? { ...t, type: "tool_result" as const, success, output_preview: outputPreview, duration_ms: durationMs }
          : t,
      );
      const updated: ChatMessage = { ...last, toolEvents };
      messages[messages.length - 1] = updated;
      return { messages };
    });
  },

  onResponseEnd: (fullText) => {
    set((state) => {
      const messages = [...state.messages];
      const last = messages[messages.length - 1];
      if (!last || last.role !== "assistant") return state;

      const updated: ChatMessage = {
        ...last,
        content: fullText,
        streaming: false,
      };
      messages[messages.length - 1] = updated;
      return { messages, streaming: false, activeRequestId: null };
    });
    // Refresh thread list after response completes (new session may have been created)
    get().loadThreads();
  },

  onError: (message) => {
    set((state) => {
      const messages = [...state.messages];
      const last = messages[messages.length - 1];

      // If there's a streaming assistant message, finalize it with the error
      if (last?.role === "assistant" && last.streaming) {
        const updated: ChatMessage = {
          ...last,
          content: last.content || `Error: ${message}`,
          streaming: false,
        };
        messages[messages.length - 1] = updated;
        return { messages, streaming: false, activeRequestId: null };
      }

      // Otherwise, add a new error message
      const errorMsg: ChatMessage = {
        id: `e-${++msgCounter}`,
        role: "assistant",
        content: `Error: ${message}`,
        toolEvents: [],
        streaming: false,
      };
      return {
        messages: [...messages, errorMsg],
        streaming: false,
        activeRequestId: null,
      };
    });
  },

  // ── Thread management ────────────────────────────────────────────────

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

  switchToThread: async (threadId) => {
    if (get().currentThreadId === threadId) return;
    try {
      const session = await sessionsApi.get(threadId);
      set({
        currentThreadId: threadId,
        messages: apiToMessages(session.messages),
      });
    } catch {
      // Session not found or access denied -- stay on current thread
    }
  },

  switchToNewThread: () => {
    set({ currentThreadId: null, messages: [], activeBranchId: null });
  },

  renameThread: async (threadId, title) => {
    await sessionsApi.rename(threadId, title);
    await get().loadThreads();
  },

  archiveThread: async (threadId) => {
    await sessionsApi.archive(threadId);
    if (get().currentThreadId === threadId) {
      set({ currentThreadId: null, messages: [] });
    }
    await get().loadThreads();
  },

  unarchiveThread: async (threadId) => {
    await sessionsApi.unarchive(threadId);
    await get().loadThreads();
  },

  deleteThread: async (threadId) => {
    await sessionsApi.delete(threadId);
    if (get().currentThreadId === threadId) {
      set({ currentThreadId: null, messages: [] });
    }
    await get().loadThreads();
  },

  // ── Legacy compat ────────────────────────────────────────────────────
  // These are called by ChatRuntimeProvider which doesn't have access to
  // the WebSocket hook. They add messages to the store; the actual WS
  // send happens in useGatewayWebSocket.sendMessage() which the runtime
  // provider should call instead. For now, keep these as no-op stubs so
  // the existing code doesn't crash.

  sendMessage: (_content, _tier, _attachments) => {
    // No-op: WebSocket sending moved to useGatewayWebSocket.sendMessage()
    // ChatRuntimeProvider will be updated in Task 9 to use the hook.
  },

  cancel: () => {
    // No-op: cancellation moved to useGatewayWebSocket.cancel()
  },
}));
