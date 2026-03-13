/**
 * Bridges our chatStore (WebSocket-backed) to assistant-ui's ExternalStoreRuntime.
 *
 * This is the single integration point: assistant-ui reads messages from here
 * and sends new messages through here. Also provides thread list support.
 *
 * Owns the WebSocket connection lifecycle via useGatewayWebSocket, so the
 * onNew/onCancel handlers can send messages through the live connection
 * rather than through no-op store stubs.
 */

import { useEffect, useMemo, type ReactNode } from "react";
import {
  useExternalStoreRuntime,
  AssistantRuntimeProvider,
} from "@assistant-ui/react";
import { useChatStore } from "@/stores/chatStore";
import { convertMessage } from "@/stores/chatRuntime";
import { useGatewayWebSocket } from "@/hooks/useGatewayWebSocket";
import { ClaraAttachmentAdapter, attachmentToGateway } from "@/lib/attachmentAdapter";

export function ChatRuntimeProvider({ children }: { children: ReactNode }) {
  const messages = useChatStore((s) => s.messages);
  const streaming = useChatStore((s) => s.streaming);
  const currentThreadId = useChatStore((s) => s.currentThreadId);
  const threads = useChatStore((s) => s.threads);
  const archivedThreads = useChatStore((s) => s.archivedThreads);
  const threadsLoading = useChatStore((s) => s.threadsLoading);

  // Own the WebSocket connection so we can send/cancel through it
  const { sendMessage: wsSendMessage, cancel: wsCancel } =
    useGatewayWebSocket();

  // Stable attachment adapter instance (survives re-renders)
  const attachmentAdapter = useMemo(() => new ClaraAttachmentAdapter(), []);

  // Load thread list on mount
  useEffect(() => {
    useChatStore.getState().loadThreads();
  }, []);

  const runtime = useExternalStoreRuntime({
    isRunning: streaming,
    messages,
    // Our convertMessage returns a shape compatible with ThreadMessageLike
    // but TypeScript can't verify the deep ReadonlyJSONObject constraint
    convertMessage: convertMessage as never,
    onNew: async (message) => {
      const textParts = message.content.filter((p) => p.type === "text");
      const text = textParts.map((p) => ("text" in p ? p.text : "")).join("\n");

      // Convert assistant-ui attachments to gateway wire format
      const attachments = (message.attachments ?? [])
        .map(attachmentToGateway)
        .filter((a): a is NonNullable<typeof a> => a !== null);

      if (text.trim() || attachments.length > 0) {
        const s = useChatStore.getState();
        wsSendMessage(text, {
          branchId: s.activeBranchId,
          tierOverride: s.selectedTier,
          attachments: attachments.length > 0
            ? attachments.map((a) => ({
                type: a.content_type.startsWith("image/") ? "image" : "file",
                filename: a.filename,
                media_type: a.content_type,
                base64_data: a.data,
              }))
            : undefined,
        });
      }
    },
    onCancel: async () => {
      wsCancel();
    },
    adapters: {
      attachments: attachmentAdapter,
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
