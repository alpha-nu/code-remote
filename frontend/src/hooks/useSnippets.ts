/**
 * React Query hooks for snippets API
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { snippetsApi } from '../api/snippets';
import type { SnippetCreate, SnippetUpdate } from '../types/api';

/**
 * List user's snippets with pagination
 */
export function useSnippets(limit = 50, offset = 0) {
  return useQuery({
    queryKey: ['snippets', limit, offset],
    queryFn: async () => {
      const response = await snippetsApi.list({ limit, offset });
      return response;
    },
    staleTime: 30000, // Consider fresh for 30s
  });
}

/**
 * Get single snippet by ID
 */
export function useSnippet(id: string | null) {
  return useQuery({
    queryKey: ['snippet', id],
    queryFn: async () => {
      if (!id) throw new Error('Snippet ID required');
      return await snippetsApi.get(id);
    },
    enabled: !!id, // Only run query if ID exists
    staleTime: 60000, // Consider fresh for 1 min
  });
}

/**
 * Create new snippet mutation
 */
export function useCreateSnippet() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: SnippetCreate) => snippetsApi.create(data),
    onSuccess: () => {
      // Invalidate and refetch snippets list
      queryClient.invalidateQueries({ queryKey: ['snippets'] });
    },
  });
}

/**
 * Update existing snippet mutation
 */
export function useUpdateSnippet() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: SnippetUpdate }) =>
      snippetsApi.update(id, data),
    onSuccess: (updatedSnippet) => {
      // Update the specific snippet in cache
      queryClient.setQueryData(['snippet', updatedSnippet.id], updatedSnippet);
      // Invalidate list to refresh
      queryClient.invalidateQueries({ queryKey: ['snippets'] });
    },
  });
}

/**
 * Delete snippet mutation
 */
export function useDeleteSnippet() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => snippetsApi.delete(id),
    onSuccess: (_data, deletedId) => {
      // Remove from cache
      queryClient.removeQueries({ queryKey: ['snippet', deletedId] });
      // Invalidate list
      queryClient.invalidateQueries({ queryKey: ['snippets'] });
    },
  });
}
