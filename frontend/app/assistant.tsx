"use client";

import { useMemo, useState } from "react";
import {
  AssistantRuntimeProvider,
  useThreadListItem,
  useThreadListItemRuntime,
  RuntimeAdapterProvider,
  unstable_useRemoteThreadListRuntime as useRemoteThreadListRuntime,
} from "@assistant-ui/react";
import {
  useChatRuntime,
  AssistantChatTransport,
} from "@assistant-ui/react-ai-sdk";
import { PencilIcon, Check, X } from "lucide-react";
import { Thread } from "@/components/assistant-ui/thread";
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { ThreadListSidebar } from "@/components/assistant-ui/threadlist-sidebar";
import { Separator } from "@/components/ui/separator";
import { Input } from "@/components/ui/input";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import { threadListAdapter, createHistoryAdapter } from "@/lib/thread-adapter";

// Track current thread ID for chat requests via sessionStorage
const THREAD_ID_KEY = "clara-current-thread-id";

function setCurrentThreadId(id: string | undefined) {
  if (typeof window !== "undefined") {
    if (id) {
      sessionStorage.setItem(THREAD_ID_KEY, id);
    } else {
      sessionStorage.removeItem(THREAD_ID_KEY);
    }
  }
}

function getCurrentThreadId(): string | null {
  if (typeof window !== "undefined") {
    return sessionStorage.getItem(THREAD_ID_KEY);
  }
  return null;
}

// Intercept fetch to add thread ID header for /api/chat requests
if (typeof window !== "undefined") {
  const originalFetch = window.fetch;
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;

    if (url.includes("/api/chat")) {
      const threadId = getCurrentThreadId();
      const headers = new Headers(init?.headers);
      if (threadId) {
        headers.set("X-Thread-Id", threadId);
      }
      return originalFetch(input, { ...init, headers });
    }

    return originalFetch(input, init);
  };
}

/**
 * Header component that shows the current thread title with edit capability.
 */
function ThreadHeader() {
  const threadListItem = useThreadListItem();
  const runtime = useThreadListItemRuntime();
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState("");

  const title = threadListItem?.title || "Clara";

  const startEdit = () => {
    setEditTitle(title === "Clara" ? "" : title);
    setIsEditing(true);
  };

  const handleSave = async () => {
    if (editTitle.trim() && editTitle !== title) {
      await runtime.rename(editTitle.trim());
    }
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSave();
    } else if (e.key === "Escape") {
      setIsEditing(false);
    }
  };

  if (isEditing) {
    return (
      <div className="flex items-center gap-2">
        <Input
          value={editTitle}
          onChange={(e) => setEditTitle(e.target.value)}
          onKeyDown={handleKeyDown}
          className="h-8 text-lg font-semibold w-64"
          placeholder="Thread name..."
          autoFocus
        />
        <TooltipIconButton
          className="size-7 p-0"
          variant="ghost"
          tooltip="Save"
          onClick={handleSave}
        >
          <Check className="size-4" />
        </TooltipIconButton>
        <TooltipIconButton
          className="size-7 p-0"
          variant="ghost"
          tooltip="Cancel"
          onClick={() => setIsEditing(false)}
        >
          <X className="size-4" />
        </TooltipIconButton>
      </div>
    );
  }

  return (
    <div className="group flex items-center gap-2">
      <h1 className="text-lg font-semibold">{title}</h1>
      {threadListItem && (
        <TooltipIconButton
          className="size-7 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
          variant="ghost"
          tooltip="Rename thread"
          onClick={startEdit}
        >
          <PencilIcon className="size-4" />
        </TooltipIconButton>
      )}
    </div>
  );
}

/**
 * Provider component that runs in the context of each thread.
 * This gives us access to the thread's remoteId for history persistence.
 */
function ThreadProvider({ children }: { children?: React.ReactNode }) {
  const threadListItem = useThreadListItem();
  const remoteId = threadListItem?.remoteId;

  // Track current thread ID in sessionStorage for chat requests
  setCurrentThreadId(remoteId);

  const history = useMemo(() => createHistoryAdapter(remoteId), [remoteId]);
  const adapters = useMemo(() => ({ history }), [history]);

  return (
    <RuntimeAdapterProvider adapters={adapters}>
      {children}
    </RuntimeAdapterProvider>
  );
}

/**
 * Main content area with header and thread.
 */
function MainContent() {
  return (
    <SidebarInset>
      <header className="flex h-16 shrink-0 items-center gap-2 border-b px-4">
        <SidebarTrigger />
        <Separator orientation="vertical" className="mr-2 h-4" />
        <ThreadHeader />
      </header>
      <div className="flex-1 overflow-hidden">
        <Thread />
      </div>
    </SidebarInset>
  );
}

export const Assistant = () => {
  const runtime = useRemoteThreadListRuntime({
    runtimeHook: () =>
      useChatRuntime({
        transport: new AssistantChatTransport({
          api: "/api/chat",
        }),
      }),
    adapter: {
      ...threadListAdapter,
      unstable_Provider: ThreadProvider,
    },
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <SidebarProvider>
        <div className="flex h-dvh w-full pr-0.5">
          <ThreadListSidebar />
          <MainContent />
        </div>
      </SidebarProvider>
    </AssistantRuntimeProvider>
  );
};
