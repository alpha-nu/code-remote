/**
 * Search API client for semantic search functionality.
 */

import apiClient from './client';

export interface SearchResultItem {
  id: string;
  title: string;
  description: string | null;
  timeComplexity: string | null;
  spaceComplexity: string | null;
  score: number;
  language: string;
  isStarred: boolean;
  createdAt: string;
}

export interface UnifiedSearchResponse {
  query: string;
  results: SearchResultItem[];
  totalCount: number;
  method: 'cypher' | 'semantic' | 'fallback';
  cypherQuery: string | null;
}

export interface SimilarSnippetsResponse {
  snippetId: string;
  results: SearchResultItem[];
  totalCount: number;
}

export interface ComplexityFilterResponse {
  complexityType: 'time' | 'space';
  complexityValue: string;
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
