import { useQuery, useQueryClient } from '@tanstack/react-query';
import { commands, type Backlink } from '../lib/bindings';

/**
 * Hook to fetch backlinks for a note
 * @param noteId - The note ID to get backlinks for
 * @returns TanStack Query result with backlinks data
 */
export function useBacklinks(noteId: number | null) {
  return useQuery({
    queryKey: ['backlinks', noteId],
    queryFn: async (): Promise<Backlink[]> => {
      if (noteId === null) return [];

      const result = await commands.getBacklinks(noteId);
      if (result.status === 'error') {
        throw new Error(result.error);
      }
      return result.data;
    },
    enabled: noteId !== null,
    staleTime: 1000 * 60, // Cache for 1 minute
    refetchOnWindowFocus: false,
  });
}

/**
 * Hook to get backlinks invalidation function
 * Call after saving note content to refresh backlinks
 */
export function useInvalidateBacklinks() {
  const queryClient = useQueryClient();

  return {
    /**
     * Invalidate backlinks for specific notes
     * @param noteIds - Note IDs whose backlinks should refresh
     */
    invalidateNotes: (noteIds: number[]) => {
      noteIds.forEach((id) => {
        queryClient.invalidateQueries({ queryKey: ['backlinks', id] });
      });
    },

    /**
     * Invalidate all backlinks cache
     * Use after bulk operations
     */
    invalidateAll: () => {
      queryClient.invalidateQueries({ queryKey: ['backlinks'] });
    },
  };
}
