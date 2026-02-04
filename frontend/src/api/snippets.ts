/**
 * Snippets API Client
 *
 * Type-safe API client for snippet CRUD operations.
 * Types are generated from OpenAPI spec via openapi-typescript.
 */

import apiClient from './client';
import type {
  Snippet,
  SnippetCreate,
  SnippetUpdate,
  SnippetListResponse,
  SnippetDeleteResponse,
} from '../types/api';

// Helper to transform snake_case to camelCase
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function toCamelCase(obj: any): any {
  if (Array.isArray(obj)) {
    return obj.map(toCamelCase);
  }
  if (obj !== null && typeof obj === 'object') {
    return Object.keys(obj).reduce((acc, key) => {
      const camelKey = key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
      acc[camelKey] = toCamelCase(obj[key]);
      return acc;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    }, {} as Record<string, any>);
  }
  return obj;
}

// Helper to transform camelCase to snake_case
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function toSnakeCase(obj: any): any {
  if (Array.isArray(obj)) {
    return obj.map(toSnakeCase);
  }
  if (obj !== null && typeof obj === 'object') {
    return Object.keys(obj).reduce((acc, key) => {
      const snakeKey = key.replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`);
      acc[snakeKey] = toSnakeCase(obj[key]);
      return acc;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    }, {} as Record<string, any>);
  }
  return obj;
}

export const snippetsApi = {
  /**
   * List user's snippets (paginated)
   * Returns summaries only - no code field
   */
  list: async (params?: { limit?: number; offset?: number }): Promise<SnippetListResponse> => {
    const searchParams = new URLSearchParams();
    if (params?.limit) searchParams.set('limit', params.limit.toString());
    if (params?.offset) searchParams.set('offset', params.offset.toString());

    const query = searchParams.toString();
    const response = await apiClient.get(`/snippets${query ? `?${query}` : ''}`);
    return toCamelCase(response.data);
  },

  /**
   * Get single snippet with full code
   */
  get: async (id: string): Promise<Snippet> => {
    const response = await apiClient.get(`/snippets/${id}`);
    return toCamelCase(response.data);
  },

  /**
   * Create new snippet from code
   */
  create: async (data: SnippetCreate): Promise<Snippet> => {
    const response = await apiClient.post('/snippets', toSnakeCase(data));
    return toCamelCase(response.data);
  },

  /**
   * Update existing snippet
   */
  update: async (id: string, data: SnippetUpdate): Promise<Snippet> => {
    const response = await apiClient.put(`/snippets/${id}`, toSnakeCase(data));
    return toCamelCase(response.data);
  },

  /**
   * Delete snippet
   */
  delete: async (id: string): Promise<SnippetDeleteResponse> => {
    const response = await apiClient.delete(`/snippets/${id}`);
    return response.data;
  },
};
