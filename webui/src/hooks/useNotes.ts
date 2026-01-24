import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { commands, type CreateNoteInput, type UpdateNoteInput } from '../lib/bindings';

export function useNotes(folderId?: number | null) {
  return useQuery({
    queryKey: ['notes', folderId],
    queryFn: async () => {
      const result = await commands.listNotes(folderId ?? null);
      if (result.status === 'ok') {
        return result.data;
      }
      throw new Error(result.error);
    },
  });
}

export function useNote(id: number | null) {
  return useQuery({
    queryKey: ['note', id],
    queryFn: async () => {
      if (id === null) return null;
      const result = await commands.getNote(id);
      if (result.status === 'ok') {
        return result.data;
      }
      throw new Error(result.error);
    },
    enabled: id !== null,
  });
}

export function useCreateNote() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (input: CreateNoteInput) => {
      const result = await commands.createNote(input);
      if (result.status === 'ok') {
        return result.data;
      }
      throw new Error(result.error);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notes'] });
    },
  });
}

export function useUpdateNote() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, input }: { id: number; input: UpdateNoteInput }) => {
      const result = await commands.updateNote(id, input);
      if (result.status === 'ok') {
        return result.data;
      }
      throw new Error(result.error);
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['notes'] });
      queryClient.setQueryData(['note', data.id], data);
    },
  });
}

export function useDeleteNote() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: number) => {
      const result = await commands.deleteNote(id);
      if (result.status === 'ok') {
        return result.data;
      }
      throw new Error(result.error);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notes'] });
    },
  });
}
