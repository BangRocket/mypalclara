/** Typed API client for the Clara web backend. */

const API_ORIGIN = import.meta.env.VITE_API_URL || "";
const BASE = `${API_ORIGIN}/api/v1`;

// ── Token management ─────────────────────────────────────────────────────
const TOKEN_KEY = "clara_token";
let _token: string | null = sessionStorage.getItem(TOKEN_KEY);

export function setToken(token: string | null) {
  _token = token;
  if (token) {
    sessionStorage.setItem(TOKEN_KEY, token);
  } else {
    sessionStorage.removeItem(TOKEN_KEY);
  }
}

export function getToken(): string | null {
  return _token;
}

// ── Request helper ───────────────────────────────────────────────────────

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = path.startsWith("/") ? `${API_ORIGIN}${path}` : path;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((init?.headers as Record<string, string>) ?? {}),
  };
  if (_token) {
    headers["Authorization"] = `Bearer ${_token}`;
  }
  const res = await fetch(url, {
    credentials: "include",
    ...init,
    headers,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || res.statusText);
  }
  return res.json();
}

// ── Auth ──────────────────────────────────────────────────────────────────

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

export interface AuthConfig {
  dev_mode: boolean;
  providers: { discord: boolean; google: boolean };
}

export const auth = {
  config: () => request<AuthConfig>("/auth/config"),
  me: () => request<User>("/auth/me"),
  loginUrl: (provider: string) => request<{ url: string }>(`/auth/login/${provider}`),
  logout: () => request<{ ok: boolean }>("/auth/logout", { method: "POST" }),
  devLogin: () => request<{ user: User; token: string }>("/auth/dev-login", { method: "POST" }),
  callback: (provider: string, code: string) =>
    request<{ user: User; token: string }>(`/auth/callback/${provider}?code=${code}`),
};

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

// ── Graph ─────────────────────────────────────────────────────────────────

export interface GraphNode {
  id: string;
  name: string;
  type: string | null;
}

export interface GraphEdge {
  source: string;
  target: string;
  label: string;
}

export const graph = {
  entities: (params?: { offset?: number; limit?: number }) => {
    const sp = new URLSearchParams();
    if (params) {
      for (const [k, v] of Object.entries(params)) sp.set(k, String(v));
    }
    return request<{ entities: { name: string; type: string }[]; total: number }>(`${BASE}/graph/entities?${sp}`);
  },
  entity: (name: string) =>
    request<{
      name: string;
      relationships: { source: string; relationship: string; description: string; target: string; target_type: string }[];
    }>(`${BASE}/graph/entities/${encodeURIComponent(name)}`),
  search: (q: string, limit?: number) =>
    request<{ results: { name: string; type: string }[] }>(`${BASE}/graph/search?q=${encodeURIComponent(q)}&limit=${limit || 20}`),
  subgraph: (params?: { center?: string; depth?: number; limit?: number }) => {
    const sp = new URLSearchParams();
    if (params) {
      for (const [k, v] of Object.entries(params)) {
        if (v !== undefined) sp.set(k, String(v));
      }
    }
    return request<{ nodes: GraphNode[]; edges: GraphEdge[] }>(`${BASE}/graph/subgraph?${sp}`);
  },
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

export const users = {
  me: () => request<User & { links: { id: string; platform: string; platform_user_id: string; prefixed_user_id: string; display_name: string; linked_at: string | null; linked_via: string }[] }>(`${BASE}/users/me`),
  update: (body: { display_name?: string; avatar_url?: string }) =>
    request<{ ok: boolean }>(`${BASE}/users/me`, { method: "PUT", body: JSON.stringify(body) }),
};

// ── Intentions ────────────────────────────────────────────────────────────

export interface Intention {
  id: string;
  content: string;
  trigger_conditions: Record<string, unknown>;
  priority: number;
  fire_once: boolean;
  fired: boolean;
  fired_at: string | null;
  created_at: string | null;
  expires_at: string | null;
}

export const intentions = {
  list: (params?: { fired?: boolean; offset?: number; limit?: number }) => {
    const sp = new URLSearchParams();
    if (params) {
      for (const [k, v] of Object.entries(params)) {
        if (v !== undefined) sp.set(k, String(v));
      }
    }
    return request<{ intentions: Intention[]; total: number }>(`${BASE}/intentions?${sp}`);
  },
  create: (body: { content: string; trigger_conditions: Record<string, unknown>; priority?: number; fire_once?: boolean }) =>
    request<{ id: string; ok: boolean }>(`${BASE}/intentions`, { method: "POST", body: JSON.stringify(body) }),
  update: (id: string, body: Partial<Intention>) =>
    request<{ ok: boolean }>(`${BASE}/intentions/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  delete: (id: string) => request<{ ok: boolean }>(`${BASE}/intentions/${id}`, { method: "DELETE" }),
};

// ── Admin ─────────────────────────────────────────────────────────────────

export interface AdminUser {
  id: string;
  display_name: string;
  email: string | null;
  avatar_url: string | null;
  created_at: string | null;
  status?: "pending" | "active" | "suspended";
  is_admin: boolean;
  platforms: { platform: string; display_name: string }[];
}

export const admin = {
  users: (params?: { status?: string; offset?: number; limit?: number }) => {
    const sp = new URLSearchParams();
    if (params) {
      for (const [k, v] of Object.entries(params)) {
        if (v !== undefined) sp.set(k, String(v));
      }
    }
    return request<{ users: AdminUser[]; total: number; offset: number; limit: number }>(
      `${BASE}/admin/users?${sp}`,
    );
  },
  approve: (userId: string) =>
    request<{ ok: boolean; user_id: string; status: string }>(`${BASE}/admin/users/${userId}/approve`, {
      method: "POST",
    }),
  suspend: (userId: string) =>
    request<{ ok: boolean; user_id: string; status: string }>(`${BASE}/admin/users/${userId}/suspend`, {
      method: "POST",
    }),
  pendingCount: () => request<{ count: number }>(`${BASE}/admin/users/pending/count`),
};
