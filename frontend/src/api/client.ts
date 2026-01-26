/**
 * API client for backend services.
 */

import axios from 'axios';
import type { ExecutionRequest, ExecutionResponse } from '../types/execution';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Execute Python code on the backend.
 */
export async function executeCode(request: ExecutionRequest): Promise<ExecutionResponse> {
  const response = await apiClient.post<ExecutionResponse>('/execute', request);
  return response.data;
}

/**
 * Health check endpoint.
 */
export async function healthCheck(): Promise<{ status: string; version: string }> {
  const response = await apiClient.get('/health');
  return response.data;
}

export default apiClient;
