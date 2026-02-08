/**
 * Search API client for semantic search functionality.
 */

import apiClient from './client';

// API response types (snake_case from backend)
export interface SearchResultItem {
  snippet_id: string;
  title: string | null;
  description: string | null;
  time_complexity: string | null;
  space_complexity: string | null;
  score: number;
  language: string;
}

export interface UnifiedSearchResponse {
  query: string;
  results: SearchResultItem[];
  total: number;
  method: 'cypher' | 'semantic';
}

export interface SimilarSnippetsResponse {
  source_snippet_id: string;
  similar: SearchResultItem[];
  total: number;
}

export interface ComplexityFilterResponse {
  complexity_type: 'time' | 'space';
  complexity_value: string;
  results: SearchResultItem[];
  total: number;
}

export type ComplexityType = 'time' | 'space';

export const searchApi = {
  /**
   * Unified semantic search with Text-to-Cypher.
   */
  search: async (query: string, limit = 10): Promise<UnifiedSearchResponse> => {
    const params = new URLSearchParams({ q: query, limit: limit.toString() });
    const response = await apiClient.get(`/search?${params}`);
    return response.data;
  },

  /**
   * Find snippets similar to a given snippet.
   */
  similar: async (snippetId: string, limit = 5): Promise<SimilarSnippetsResponse> => {
    const params = new URLSearchParams({ limit: limit.toString() });
    const response = await apiClient.get(`/search/similar/${snippetId}?${params}`);
    return response.data;
  },

  /**
   * Filter snippets by exact complexity match.
   */
  byComplexity: async (
    complexity: string,
    type: ComplexityType,
    limit = 20
  ): Promise<ComplexityFilterResponse> => {
    const params = new URLSearchParams({
      complexity,
      type,
      limit: limit.toString(),
    });
    const response = await apiClient.get(`/search/complexity?${params}`);
    return response.data;
  },
};
