import type {
  unstable_RemoteThreadListAdapter as RemoteThreadListAdapter,
  ThreadHistoryAdapter,
} from "@assistant-ui/react";
import { createAssistantStream } from "assistant-stream";

// Use relative URL - Next.js rewrites will proxy to backend
// This avoids CORS issues entirely
const BACKEND_URL = "";

// Types for message content parts
type ContentPart = { type: string; text?: string };

/**
 * Remote thread list adapter for managing threads via our backend API.
 */
export const threadListAdapter: RemoteThreadListAdapter = {
  /**
   * List all threads from the backend.
   */
  async list() {
    try {
      const response = await fetch(`${BACKEND_URL}/api/threads`);
      if (!response.ok) {
        console.error("[threads] Failed to list threads:", response.status);
        return { threads: [] };
      }
      const data = await response.json();
      return { threads: data.threads };
    } catch (error) {
      console.error("[threads] Error listing threads:", error);
      return { threads: [] };
    }
  },

  /**
   * Initialize a new thread - called when creating a new thread.
   */
  async initialize(threadId: string) {
    console.log("[threads] initialize() called with threadId:", threadId);
    try {
      const response = await fetch(`${BACKEND_URL}/api/threads`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (!response.ok) {
        console.error("[threads] Failed to create thread:", response.status);
        throw new Error("Failed to create thread");
      }
      const data = await response.json();
      console.log("[threads] Created thread:", data.remoteId);
      return { remoteId: data.remoteId, externalId: undefined };
    } catch (error) {
      console.error("[threads] Error creating thread:", error);
      throw error;
    }
  },

  /**
   * Rename a thread.
   */
  async rename(remoteId: string, newTitle: string) {
    try {
      const response = await fetch(`${BACKEND_URL}/api/threads/${remoteId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: newTitle }),
      });
      if (!response.ok) {
        console.error("[threads] Failed to rename thread:", response.status);
      }
    } catch (error) {
      console.error("[threads] Error renaming thread:", error);
    }
  },

  /**
   * Archive a thread.
   */
  async archive(remoteId: string) {
    try {
      const response = await fetch(`${BACKEND_URL}/api/threads/${remoteId}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        console.error("[threads] Failed to archive thread:", response.status);
      }
    } catch (error) {
      console.error("[threads] Error archiving thread:", error);
    }
  },

  /**
   * Unarchive a thread.
   */
  async unarchive(remoteId: string) {
    try {
      const response = await fetch(`${BACKEND_URL}/api/threads/${remoteId}/unarchive`, {
        method: "POST",
      });
      if (!response.ok) {
        console.error("[threads] Failed to unarchive thread:", response.status);
      }
    } catch (error) {
      console.error("[threads] Error unarchiving thread:", error);
    }
  },

  /**
   * Delete a thread permanently.
   */
  async delete(remoteId: string) {
    try {
      const response = await fetch(`${BACKEND_URL}/api/threads/${remoteId}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        console.error("[threads] Failed to delete thread:", response.status);
      }
    } catch (error) {
      console.error("[threads] Error deleting thread:", error);
    }
  },

  /**
   * Fetch thread metadata.
   */
  async fetch(threadId: string) {
    try {
      const response = await fetch(`${BACKEND_URL}/api/threads/${threadId}`);
      if (!response.ok) {
        console.error("[threads] Failed to fetch thread:", response.status);
        return { remoteId: threadId, status: "regular" as const, title: undefined };
      }
      const data = await response.json();
      return {
        remoteId: data.remoteId || threadId,
        status: data.status || "regular",
        title: data.title,
      };
    } catch (error) {
      console.error("[threads] Error fetching thread:", error);
      return { remoteId: threadId, status: "regular" as const, title: undefined };
    }
  },

  /**
   * Generate a title for the thread based on messages.
   * Returns a Promise<AssistantStream> with the generated title.
   */
  async generateTitle(remoteId: string) {
    // Request title generation from backend
    try {
      const response = await fetch(`${BACKEND_URL}/api/threads/${remoteId}/generate-title`, {
        method: "POST",
      });
      if (response.ok) {
        const data = await response.json();
        const title = data.title || "New Chat";
        return createAssistantStream((controller) => {
          controller.appendText(title);
          controller.close();
        });
      }
    } catch (error) {
      console.error("[threads] Error generating title:", error);
    }

    // Fallback
    return createAssistantStream((controller) => {
      controller.appendText("New Chat");
      controller.close();
    });
  },
};

/**
 * Create a history adapter for a specific thread.
 */
export function createHistoryAdapter(remoteId: string | undefined): ThreadHistoryAdapter {
  const adapter: ThreadHistoryAdapter = {
    /**
     * Required for load() to be called - returns self with same interface.
     * Type cast needed due to complex generic constraints in assistant-ui.
     */
    withFormat() {
      return adapter as any;
    },

    /**
     * Load messages for this thread.
     */
    async load() {
      if (!remoteId) {
        return { messages: [] };
      }

      try {
        const response = await fetch(`${BACKEND_URL}/api/threads/${remoteId}/messages`);
        if (!response.ok) {
          return { messages: [] };
        }
        const data = await response.json();

        // Convert to the expected format (simple format per docs)
        interface BackendMessage {
          id: string;
          role: string;
          content: ContentPart[];
          createdAt: string;
        }

        // Filter out empty messages first
        const validMessages = data.messages.filter((m: BackendMessage) => {
          const text = m.content
            .filter((p) => p.type === "text")
            .map((p) => p.text || "")
            .join("");
          return text.length > 0;
        });

        if (validMessages.length === 0) {
          return { messages: [] };
        }

        // Convert to MessageFormatRepository format expected by assistant-ui
        // { headId: string, messages: [{ message: UIMessage, parentId: string | null }] }
        const messages = validMessages.map((m: BackendMessage, index: number) => ({
          message: {
            id: m.id,
            role: m.role as "user" | "assistant",
            parts: m.content, // AI SDK UIMessage uses 'parts'
            createdAt: new Date(m.createdAt),
          },
          parentId: index > 0 ? validMessages[index - 1].id : null,
        }));

        const headId = validMessages[validMessages.length - 1].id;
        return { headId, messages };
      } catch (error) {
        console.error("[history] Error loading messages:", error);
        return { messages: [] };
      }
    },

    /**
     * Append a message to this thread.
     */
    async append(item) {
      if (!remoteId) {
        return;
      }

      const { message } = item;

      // Extract text content
      let textContent = "";
      if (typeof message.content === "string") {
        textContent = message.content;
      } else if (Array.isArray(message.content)) {
        textContent = message.content
          .filter((p: ContentPart) => p.type === "text")
          .map((p: ContentPart) => p.text || "")
          .join("");
      }

      try {
        const response = await fetch(`${BACKEND_URL}/api/threads/${remoteId}/messages`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            role: message.role,
            content: textContent,
            id: message.id,
            createdAt: message.createdAt?.toISOString(),
          }),
        });
        if (!response.ok) {
          console.error("[threads] Failed to append message:", response.status);
        }
      } catch (error) {
        console.error("[history] Error appending message:", error);
      }
    },
  };

  return adapter;
}
