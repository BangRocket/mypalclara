/** Typed API client for the Clara gateway backend. */

const GATEWAY_URL = import.meta.env.VITE_GATEWAY_URL || "http://localhost:18790";
const BASE = `${GATEWAY_URL}/api/v1`;

// ── Token management (set from React via TokenBridge) ────────────────────

let _getToken: (() => Promise<string | null>) | null = null;

export function setTokenGetter(getter: () => Promise<string | null>) {
  _getToken = getter;
}

async function getAuthHeaders(): Promise<Record<string, string>> {
  if (!_getToken) return {};
  const token = await _getToken();
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

/** Get a fresh token for non-HTTP uses (e.g. WebSocket auth). */
export async function getToken(): Promise<string | null> {
  if (!_getToken) return null;
  return _getToken();
}

// ── Request helper ───────────────────────────────────────────────────────

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = path.startsWith("http") ? path : `${GATEWAY_URL}${path}`;
  const authHeaders = await getAuthHeaders();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...authHeaders,
    ...((init?.headers as Record<string, string>) ?? {}),
  };
  const res = await fetch(url, {
    ...init,
    headers,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || res.statusText);
  }
  return res.json();
}

// ── Memories ──────────────────────────────────────────────────────────────

export interface MemoryDynamics {
  stability: number | null;
  difficulty: number | null;
  retrieval_strength: number | null;
  storage_strength: number | null;
  is_key: boolean;
  category: string | null;
  access_count: number;
  last_accessed_at: string | null;
}

export interface Memory {
  id: string;
  content: string;
  metadata: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
  user_id: string | null;
  dynamics: MemoryDynamics | null;
}

export interface MemorySearchResult {
  id: string;
  content: string;
  score: number | null;
  metadata: Record<string, unknown>;
  dynamics: { is_key: boolean; category: string | null; stability: number | null } | null;
}

export const memories = {
  list: (params?: {
    category?: string;
    is_key?: boolean;
    sort?: string;
    order?: string;
    offset?: number;
    limit?: number;
  }) => {
    const sp = new URLSearchParams();
    if (params) {
      for (const [k, v] of Object.entries(params)) {
        if (v !== undefined) sp.set(k, String(v));
      }
    }
    return request<{ memories: Memory[]; total: number; offset: number; limit: number }>(
      `${BASE}/memories?${sp}`,
    );
  },
  get: (id: string) => request<Memory>(`${BASE}/memories/${id}`),
  create: (body: { content: string; category?: string; is_key?: boolean }) =>
    request<{ ok: boolean; result: unknown }>(`${BASE}/memories`, { method: "POST", body: JSON.stringify(body) }),
  update: (id: string, body: { content?: string; category?: string; is_key?: boolean }) =>
    request<{ ok: boolean }>(`${BASE}/memories/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  delete: (id: string) => request<{ ok: boolean }>(`${BASE}/memories/${id}`, { method: "DELETE" }),
  history: (id: string) =>
    request<{
      history: { id: string; event: string; old_memory: string | null; new_memory: string | null; created_at: string | null }[];
    }>(`${BASE}/memories/${id}/history`),
  dynamics: (id: string) => request<Record<string, unknown>>(`${BASE}/memories/${id}/dynamics`),
  search: (body: { query: string; category?: string; is_key?: boolean; limit?: number; threshold?: number }) =>
    request<{ results: MemorySearchResult[] }>(`${BASE}/memories/search`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  stats: () => request<{ total: number; by_category: Record<string, number>; key_count: number }>(`${BASE}/memories/stats`),
  updateTags: (id: string, tags: string[]) =>
    request<{ ok: boolean; tags: string[] }>(`${BASE}/memories/${id}/tags`, { method: "PUT", body: JSON.stringify({ tags }) }),
  allTags: () => request<{ tags: string[] }>(`${BASE}/memories/tags/all`),
  exportAll: () => `${BASE}/memories/export`,
  importMemories: (body: { memories: { content: string; category?: string; is_key?: boolean; tags?: string[] }[] }) =>
    request<{ ok: boolean; imported: number; total: number }>(`${BASE}/memories/import`, { method: "POST", body: JSON.stringify(body) }),
};

// ── Sessions ──────────────────────────────────────────────────────────────

export interface ChatSession {
  id: string;
  title: string | null;
  user_id: string;
  context_id: string;
  started_at: string | null;
  last_activity_at: string | null;
  session_summary: string | null;
  archived: boolean;
}

export interface ChatMessage {
  id: number;
  role: string;
  content: string;
  created_at: string | null;
}

export const sessions = {
  list: (params?: { offset?: number; limit?: number; archived?: boolean }) => {
    const sp = new URLSearchParams();
    if (params) {
      for (const [k, v] of Object.entries(params)) {
        if (v !== undefined) sp.set(k, String(v));
      }
    }
    return request<{ sessions: ChatSession[]; total: number }>(`${BASE}/sessions?${sp}`);
  },
  get: (id: string) =>
    request<ChatSession & { messages: ChatMessage[]; context_snapshot: string | null }>(`${BASE}/sessions/${id}`),
  rename: (id: string, title: string) =>
    request<{ ok: boolean }>(`${BASE}/sessions/${id}`, { method: "PUT", body: JSON.stringify({ title }) }),
  archive: (id: string) =>
    request<{ ok: boolean }>(`${BASE}/sessions/${id}/archive`, { method: "PATCH" }),
  unarchive: (id: string) =>
    request<{ ok: boolean }>(`${BASE}/sessions/${id}/unarchive`, { method: "PATCH" }),
  delete: (id: string) =>
    request<{ ok: boolean }>(`${BASE}/sessions/${id}`, { method: "DELETE" }),
};

// ── Users ─────────────────────────────────────────────────────────────────

export interface User {
  id: string;
  display_name: string;
  email: string | null;
  avatar_url: string | null;
  created_at: string | null;
  status?: "pending" | "active" | "suspended";
  is_admin?: boolean;
  platforms?: { platform: string; platform_user_id: string; display_name: string; linked_at: string | null }[];
}

export const users = {
  me: () => request<User & { links: { id: string; platform: string; platform_user_id: string; prefixed_user_id: string; display_name: string; linked_at: string | null; linked_via: string }[] }>(`${BASE}/users/me`),
  update: (body: { display_name?: string; avatar_url?: string }) =>
    request<{ ok: boolean }>(`${BASE}/users/me`, { method: "PUT", body: JSON.stringify(body) }),
};

// ── Unified API namespace ────────────────────────────────────────────

export const api = {
  memories,
  sessions,
  users,
};
