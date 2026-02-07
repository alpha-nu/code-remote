/**
 * React Query hooks for search functionality.
 */

import { useQuery } from '@tanstack/react-query';
import { searchApi } from '../api/search';
import type {
  UnifiedSearchResponse,
  SimilarSnippetsResponse,
  ComplexityFilterResponse,
  ComplexityType,
} from '../api/search';

/**
 * Hook for semantic search.
 * Only fetches when query is provided and has >= 3 characters.
 */
export function useSearch(query: string | null, limit = 10) {
  return useQuery<UnifiedSearchResponse>({
    queryKey: ['search', query, limit],
    queryFn: () => searchApi.search(query!, limit),
    enabled: !!query && query.length >= 3,
    staleTime: 30_000, // Cache results for 30 seconds
  });
}

/**
 * Hook for finding similar snippets.
 */
export function useSimilarSnippets(snippetId: string | null, limit = 5) {
  return useQuery<SimilarSnippetsResponse>({
    queryKey: ['similar', snippetId, limit],
    queryFn: () => searchApi.similar(snippetId!, limit),
    enabled: !!snippetId,
    staleTime: 60_000, // Cache for 1 minute
  });
}

/**
 * Hook for filtering by complexity.
 * Only fetches when both complexity and type are provided.
 */
export function useComplexityFilter(
  complexity: string | null,
  type: ComplexityType | null,
  limit = 20
) {
  return useQuery<ComplexityFilterResponse>({
    queryKey: ['complexity', complexity, type, limit],
    queryFn: () => searchApi.byComplexity(complexity!, type!, limit),
    enabled: !!complexity && !!type,
    staleTime: 60_000, // Cache for 1 minute
  });
}

export type { ComplexityType };
