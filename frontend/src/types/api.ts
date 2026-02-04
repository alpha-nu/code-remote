/**
 * API Type Definitions
 *
 * To regenerate from OpenAPI spec:
 * npm run generate:types
 *
 * This runs: npx openapi-typescript http://localhost:8000/openapi.json -o src/types/api-generated.ts
 * Then manually export the needed types here (or use generated types directly)
 */

// ====================
// Snippet Types
// ====================

/**
 * Full snippet with code (returned by GET /snippets/{id}, POST, PUT)
 */
export interface Snippet {
  id: string;
  title: string | null;
  language: string;
  code: string;
  description: string | null;
  executionCount: number;
  lastExecutionAt: string | null;
  createdAt: string;
  updatedAt: string;
  isStarred: boolean;
  // Future backend enhancements:
  timeComplexity?: string | null;
  spaceComplexity?: string | null;
}

/**
 * Snippet summary (no code) returned by list endpoint
 */
export interface SnippetSummary {
  id: string;
  title: string | null;
  language: string;
  description: string | null;
  executionCount: number;
  lastExecutionAt: string | null;
  createdAt: string;
  updatedAt: string;
  isStarred: boolean;
  // Future:
  timeComplexity?: string | null;
  spaceComplexity?: string | null;
}

/**
 * Payload for creating a snippet
 */
export interface SnippetCreate {
  code: string;
  title?: string;
  language?: string;
  description?: string;
}

/**
 * Payload for updating a snippet (all fields optional)
 */
export interface SnippetUpdate {
  code?: string;
  title?: string;
  language?: string;
  description?: string;
  isStarred?: boolean;
}

/**
 * Paginated list response
 */
export interface SnippetListResponse {
  items: SnippetSummary[];
  total: number;
  limit: number;
  offset: number;
}

/**
 * Delete confirmation response
 */
export interface SnippetDeleteResponse {
  deleted: boolean;
  id: string;
}

// ====================
// Type Transformers
// ====================

/**
 * API response shape (snake_case from backend)
 */
interface SnippetApiResponse {
  id: string;
  title: string | null;
  language: string;
  code: string;
  description: string | null;
  execution_count: number;
  last_execution_at: string | null;
  created_at: string;
  updated_at: string;
  is_starred: boolean;
  time_complexity?: string | null;
  space_complexity?: string | null;
}

/**
 * Transform API response (snake_case) to frontend model (camelCase)
 */
export function transformSnippetFromApi(apiSnippet: SnippetApiResponse): Snippet {
  return {
    id: apiSnippet.id,
    title: apiSnippet.title,
    language: apiSnippet.language,
    code: apiSnippet.code,
    description: apiSnippet.description,
    executionCount: apiSnippet.execution_count,
    lastExecutionAt: apiSnippet.last_execution_at,
    createdAt: apiSnippet.created_at,
    updatedAt: apiSnippet.updated_at,
    isStarred: apiSnippet.is_starred,
    timeComplexity: apiSnippet.time_complexity,
    spaceComplexity: apiSnippet.space_complexity,
  };
}

/**
 * Transform frontend model (camelCase) to API payload (snake_case)
 */
export function transformSnippetToApi(snippet: SnippetCreate | SnippetUpdate): Record<string, unknown> {
  const payload: Record<string, unknown> = {};

  if ('code' in snippet && snippet.code !== undefined) payload.code = snippet.code;
  if ('title' in snippet && snippet.title !== undefined) payload.title = snippet.title;
  if ('language' in snippet && snippet.language !== undefined) payload.language = snippet.language;
  if ('description' in snippet && snippet.description !== undefined) payload.description = snippet.description;
  if ('isStarred' in snippet && snippet.isStarred !== undefined) payload.is_starred = snippet.isStarred;

  return payload;
}
