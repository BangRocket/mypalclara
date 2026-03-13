/**
 * React Query hook for memory CRUD and search.
 *
 * Wraps the gateway REST API for memories via the typed client
 * in api/client.ts. Provides list, search, stats, update, delete,
 * and import mutations.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { memories as memoriesApi, type Memory, type MemorySearchResult } from "@/api/client";

export interface UseMemoriesOptions {
  search?: string;
  category?: string;
  isKey?: boolean;
}

export function useMemories(options: UseMemoriesOptions = {}) {
  const { search, category, isKey } = options;
  const queryClient = useQueryClient();

  // ── List (when not searching) ───────────────────────────────────────
  const listQuery = useQuery({
    queryKey: ["memories", category, isKey],
    queryFn: () =>
      memoriesApi.list({
        category: category || undefined,
        is_key: isKey,
        limit: 200,
      }),
    enabled: !search,
  });

  // ── Search (when search term provided) ──────────────────────────────
  const searchQuery = useQuery({
    queryKey: ["memories-search", search],
    queryFn: () => memoriesApi.search({ query: search!, limit: 50 }),
    enabled: !!search,
  });

  // ── Stats ───────────────────────────────────────────────────────────
  const statsQuery = useQuery({
    queryKey: ["memory-stats"],
    queryFn: memoriesApi.stats,
  });

  // ── Derived memories list ───────────────────────────────────────────
  const memories: Memory[] = search
    ? (searchQuery.data?.results || []).map((r: MemorySearchResult) => ({
        id: r.id,
        content: r.content,
        metadata: r.metadata,
        created_at: null,
        updated_at: null,
        user_id: null,
        dynamics: r.dynamics
          ? {
              ...r.dynamics,
              difficulty: null,
              retrieval_strength: null,
              storage_strength: null,
              access_count: 0,
              last_accessed_at: null,
            }
          : null,
      }))
    : listQuery.data?.memories || [];

  // ── Mutations ───────────────────────────────────────────────────────

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ["memories"] });
    queryClient.invalidateQueries({ queryKey: ["memories-search"] });
    queryClient.invalidateQueries({ queryKey: ["memory-stats"] });
  };

  const updateMemory = useMutation({
    mutationFn: ({ id, ...body }: { id: string; content?: string; category?: string; is_key?: boolean }) =>
      memoriesApi.update(id, body),
    onSuccess: invalidateAll,
  });

  const deleteMemory = useMutation({
    mutationFn: (id: string) => memoriesApi.delete(id),
    onSuccess: invalidateAll,
  });

  const importMemories = useMutation({
    mutationFn: memoriesApi.importMemories,
    onSuccess: invalidateAll,
  });

  return {
    memories,
    stats: statsQuery.data ?? null,
    isLoading: search ? searchQuery.isLoading : listQuery.isLoading,
    refetchList: listQuery.refetch,
    refetchStats: statsQuery.refetch,
    deleteMemory,
    updateMemory,
    importMemories,
  };
}
