/**
 * Bridges our chatStore (WebSocket-backed) to assistant-ui's ExternalStoreRuntime.
 *
 * This is the single integration point: assistant-ui reads messages from here
 * and sends new messages through here. Also provides thread list support.
 */

import { useEffect, type ReactNode } from "react";
import {
  useExternalStoreRuntime,
  AssistantRuntimeProvider,
} from "@assistant-ui/react";
import { useChatStore } from "@/stores/chatStore";
import { convertMessage } from "@/stores/chatRuntime";

export function ChatRuntimeProvider({ children }: { children: ReactNode }) {
  const messages = useChatStore((s) => s.messages);
  const sendMessage = useChatStore((s) => s.sendMessage);
  const cancel = useChatStore((s) => s.cancel);
  const currentThreadId = useChatStore((s) => s.currentThreadId);
  const threads = useChatStore((s) => s.threads);
  const archivedThreads = useChatStore((s) => s.archivedThreads);
  const threadsLoading = useChatStore((s) => s.threadsLoading);

  // Load thread list on mount
  useEffect(() => {
    useChatStore.getState().loadThreads();
  }, []);

  const runtime = useExternalStoreRuntime({
    isRunning: messages.some((m) => m.streaming),
    messages,
    // Our convertMessage returns a shape compatible with ThreadMessageLike
    // but TypeScript can't verify the deep ReadonlyJSONObject constraint
    convertMessage: convertMessage as never,
    onNew: async (message) => {
      const textParts = message.content.filter((p) => p.type === "text");
      const text = textParts.map((p) => ("text" in p ? p.text : "")).join("\n");
      if (text.trim()) {
        const tier = useChatStore.getState().selectedTier;
        sendMessage(text, tier);
      }
    },
    onCancel: async () => {
      cancel();
    },
    adapters: {
      threadList: {
        threadId: currentThreadId ?? undefined,
        isLoading: threadsLoading,
        threads: threads.map((s) => ({
          status: "regular" as const,
          id: s.id,
          title: s.title ?? s.session_summary ?? undefined,
        })),
        archivedThreads: archivedThreads.map((s) => ({
          status: "archived" as const,
          id: s.id,
          title: s.title ?? s.session_summary ?? undefined,
        })),
        onSwitchToNewThread: async () => {
          useChatStore.getState().switchToNewThread();
        },
        onSwitchToThread: async (threadId) => {
          await useChatStore.getState().switchToThread(threadId);
        },
        onRename: async (threadId, newTitle) => {
          await useChatStore.getState().renameThread(threadId, newTitle);
        },
        onArchive: async (threadId) => {
          await useChatStore.getState().archiveThread(threadId);
        },
        onUnarchive: async (threadId) => {
          await useChatStore.getState().unarchiveThread(threadId);
        },
        onDelete: async (threadId) => {
          await useChatStore.getState().deleteThread(threadId);
        },
      },
    },
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {children}
    </AssistantRuntimeProvider>
  );
}
