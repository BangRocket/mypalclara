import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { commands, type CreateFolderInput, type UpdateFolderInput } from '../lib/bindings';

export function useFolders(parentId?: number | null) {
  return useQuery({
    queryKey: ['folders', parentId],
    queryFn: async () => {
      const result = await commands.listFolders(parentId ?? null);
      if (result.status === 'ok') {
        return result.data;
      }
      throw new Error(result.error);
    },
  });
}

export function useCreateFolder() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (input: CreateFolderInput) => {
      const result = await commands.createFolder(input);
      if (result.status === 'ok') {
        return result.data;
      }
      throw new Error(result.error);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['folders'] });
    },
  });
}

export function useUpdateFolder() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, input }: { id: number; input: UpdateFolderInput }) => {
      const result = await commands.updateFolder(id, input);
      if (result.status === 'ok') {
        return result.data;
      }
      throw new Error(result.error);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['folders'] });
    },
  });
}

export function useDeleteFolder() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: number) => {
      const result = await commands.deleteFolder(id);
      if (result.status === 'ok') {
        return result.data;
      }
      throw new Error(result.error);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['folders'] });
      queryClient.invalidateQueries({ queryKey: ['notes'] });
    },
  });
}
