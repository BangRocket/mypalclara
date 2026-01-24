import { useQuery } from '@tanstack/react-query';
import { commands, type UnlinkedMention } from '../lib/bindings';

/**
 * Hook to fetch unlinked mentions for a note.
 * Unlinked mentions are notes that mention this note's title
 * without using wiki link syntax ([[title]]).
 *
 * @param noteId - The note ID to find mentions of
 * @returns TanStack Query result with unlinked mentions
 */
export function useUnlinkedMentions(noteId: number | null) {
  return useQuery({
    queryKey: ['unlinkedMentions', noteId],
    queryFn: async (): Promise<UnlinkedMention[]> => {
      if (noteId === null) return [];

      const result = await commands.getUnlinkedMentions(noteId);
      if (result.status === 'error') {
        throw new Error(result.error);
      }
      return result.data;
    },
    enabled: noteId !== null,
    staleTime: 1000 * 60 * 2, // Cache for 2 minutes
    refetchOnWindowFocus: false,
  });
}
