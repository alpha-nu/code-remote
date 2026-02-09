/**
 * React Query hooks for search functionality.
 */

import { useQuery } from '@tanstack/react-query';
import { searchApi } from '../api/search';
import { useAuthStore } from '../store/authStore';
import type {
  UnifiedSearchResponse,
  SimilarSnippetsResponse,
  ComplexityFilterResponse,
  ComplexityType,
} from '../api/search';

/**
 * Hook for semantic search.
 * Only fetches when authenticated, query is provided, and has >= 3 characters.
 */
export function useSearch(query: string | null, limit = 10) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  return useQuery<UnifiedSearchResponse>({
    queryKey: ['search', query, limit],
    queryFn: () => searchApi.search(query!, limit),
    enabled: isAuthenticated && !!query && query.length >= 3,
    staleTime: 30_000, // Cache results for 30 seconds
  });
}

/**
 * Hook for finding similar snippets.
 * Only fetches when authenticated and snippetId is provided.
 */
export function useSimilarSnippets(snippetId: string | null, limit = 5) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  return useQuery<SimilarSnippetsResponse>({
    queryKey: ['similar', snippetId, limit],
    queryFn: () => searchApi.similar(snippetId!, limit),
    enabled: isAuthenticated && !!snippetId,
    staleTime: 60_000, // Cache for 1 minute
  });
}

/**
 * Hook for filtering by complexity.
 * Only fetches when authenticated and both complexity and type are provided.
 */
export function useComplexityFilter(
  complexity: string | null,
  type: ComplexityType | null,
  limit = 20
) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  return useQuery<ComplexityFilterResponse>({
    queryKey: ['complexity', complexity, type, limit],
    queryFn: () => searchApi.byComplexity(complexity!, type!, limit),
    enabled: isAuthenticated && !!complexity && !!type,
    staleTime: 60_000, // Cache for 1 minute
  });
}

export type { ComplexityType };
