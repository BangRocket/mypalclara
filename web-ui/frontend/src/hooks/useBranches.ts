/**
 * React Query hook for branch CRUD and conversation management.
 *
 * Wraps the gateway REST API for conversations, branches, fork, merge,
 * rename, archive, and delete. Keeps the chatStore in sync so the
 * BranchSidebar and thread display always reflect current state.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getToken } from "@/api/client";
import { useChatStore, type BranchInfo, type ChatMessage } from "@/stores/chatStore";

const GATEWAY_URL = import.meta.env.VITE_GATEWAY_URL || "http://localhost:18790";
const BASE = `${GATEWAY_URL}/api/v1`;

// ── Auth header helper (re-uses the token getter set by TokenBridge) ─

async function authHeaders(): Promise<Record<string, string>> {
  const token = await getToken();
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = path.startsWith("http") ? path : `${GATEWAY_URL}${path}`;
  const auth = await authHeaders();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...auth,
    ...((init?.headers as Record<string, string>) ?? {}),
  };
  const res = await fetch(url, { ...init, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || res.statusText);
  }
  return res.json();
}

// ── API response types ──────────────────────────────────────────────

interface ConversationResponse {
  id: string;
  user_id: string;
  title: string | null;
  created_at: string;
}

interface BranchesResponse {
  branches: BranchInfo[];
}

interface ForkResponse {
  branch: BranchInfo;
}

interface MergeResponse {
  ok: boolean;
  merged_memories: number;
  appended_messages: number;
}

interface BranchMessagesResponse {
  messages: {
    id: string;
    role: string;
    content: string;
    created_at: string | null;
  }[];
}

// ── Hook ────────────────────────────────────────────────────────────

export function useBranches() {
  const queryClient = useQueryClient();
  const store = useChatStore;

  // ── Conversation (auto-creates on first access) ───────────────────

  const conversation = useQuery<ConversationResponse>({
    queryKey: ["conversation"],
    queryFn: () => request<ConversationResponse>(`${BASE}/conversation`),
  });

  // ── Branches list ─────────────────────────────────────────────────

  const branchesQuery = useQuery<BranchesResponse>({
    queryKey: ["branches"],
    queryFn: () => request<BranchesResponse>(`${BASE}/branches`),
    enabled: !!conversation.data,
  });

  const branches: BranchInfo[] = branchesQuery.data?.branches ?? [];

  // Sync branches to store whenever they change
  const currentStoreBranches = useChatStore((s) => s.branches);
  if (branches.length > 0 && branches !== currentStoreBranches) {
    // Only update if actually different (reference check is fine for query data)
    const storeState = store.getState();
    if (storeState.branches !== branches) {
      storeState.setBranches(branches);
    }
  }

  // Auto-switch to main branch on initial load
  const activeBranchId = useChatStore((s) => s.activeBranchId);
  if (branches.length > 0 && !activeBranchId) {
    const main = branches.find((b) => b.parent_branch_id === null);
    if (main) {
      switchToBranch(main.id);
    }
  }

  // ── Switch to branch ──────────────────────────────────────────────

  async function switchToBranch(branchId: string) {
    const s = store.getState();
    if (s.activeBranchId === branchId) return;

    s.setActiveBranch(branchId);

    try {
      const data = await request<BranchMessagesResponse>(
        `${BASE}/branches/${branchId}/messages`,
      );
      const messages: ChatMessage[] = data.messages.map((m, i) => ({
        id: m.id || `hist-${i}`,
        role: m.role as "user" | "assistant",
        content: m.content,
        toolEvents: [],
        streaming: false,
        created_at: m.created_at ?? undefined,
      }));
      s.setMessages(messages);
    } catch {
      // If fetch fails, clear messages rather than showing stale data
      s.setMessages([]);
    }
  }

  // ── Fork ──────────────────────────────────────────────────────────

  const fork = useMutation<
    ForkResponse,
    Error,
    { parentBranchId: string; forkMessageId?: string; name?: string }
  >({
    mutationFn: (vars) =>
      request<ForkResponse>(`${BASE}/branches/fork`, {
        method: "POST",
        body: JSON.stringify({
          parent_branch_id: vars.parentBranchId,
          fork_message_id: vars.forkMessageId,
          name: vars.name,
        }),
      }),
    onSuccess: async (data) => {
      await queryClient.invalidateQueries({ queryKey: ["branches"] });
      // Switch to the newly created branch
      await switchToBranch(data.branch.id);
    },
  });

  // ── Merge ─────────────────────────────────────────────────────────

  const merge = useMutation<
    MergeResponse,
    Error,
    { branchId: string; strategy: "squash" | "full" }
  >({
    mutationFn: (vars) =>
      request<MergeResponse>(`${BASE}/branches/${vars.branchId}/merge`, {
        method: "POST",
        body: JSON.stringify({ strategy: vars.strategy }),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["branches"] });
      // Switch back to main branch after merge
      const freshBranches = await request<BranchesResponse>(`${BASE}/branches`);
      const main = freshBranches.branches.find(
        (b) => b.parent_branch_id === null,
      );
      if (main) {
        await switchToBranch(main.id);
      }
    },
  });

  // ── Rename ────────────────────────────────────────────────────────

  const renameBranch = useMutation<
    { ok: boolean },
    Error,
    { branchId: string; name: string }
  >({
    mutationFn: (vars) =>
      request<{ ok: boolean }>(`${BASE}/branches/${vars.branchId}`, {
        method: "PATCH",
        body: JSON.stringify({ name: vars.name }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["branches"] });
    },
  });

  // ── Archive ───────────────────────────────────────────────────────

  const archiveBranch = useMutation<
    { ok: boolean },
    Error,
    { branchId: string }
  >({
    mutationFn: (vars) =>
      request<{ ok: boolean }>(`${BASE}/branches/${vars.branchId}`, {
        method: "PATCH",
        body: JSON.stringify({ status: "archived" }),
      }),
    onSuccess: async (_data, vars) => {
      await queryClient.invalidateQueries({ queryKey: ["branches"] });
      // If we archived the active branch, switch to main
      const s = store.getState();
      if (s.activeBranchId === vars.branchId) {
        const freshBranches = await request<BranchesResponse>(
          `${BASE}/branches`,
        );
        const main = freshBranches.branches.find(
          (b) => b.parent_branch_id === null,
        );
        if (main) {
          await switchToBranch(main.id);
        }
      }
    },
  });

  // ── Delete ────────────────────────────────────────────────────────

  const deleteBranch = useMutation<
    { ok: boolean },
    Error,
    { branchId: string }
  >({
    mutationFn: (vars) =>
      request<{ ok: boolean }>(`${BASE}/branches/${vars.branchId}`, {
        method: "DELETE",
      }),
    onSuccess: async (_data, vars) => {
      await queryClient.invalidateQueries({ queryKey: ["branches"] });
      // If we deleted the active branch, switch to main
      const s = store.getState();
      if (s.activeBranchId === vars.branchId) {
        const freshBranches = await request<BranchesResponse>(
          `${BASE}/branches`,
        );
        const main = freshBranches.branches.find(
          (b) => b.parent_branch_id === null,
        );
        if (main) {
          await switchToBranch(main.id);
        }
      }
    },
  });

  return {
    conversation,
    branches,
    isLoading: conversation.isLoading || branchesQuery.isLoading,
    fork,
    merge,
    renameBranch,
    archiveBranch,
    deleteBranch,
    switchToBranch,
  };
}
