/**
 * API client for backend services.
 */

import axios from 'axios';
import type {
  AnalyzeRequest,
  AnalyzeResponse,
  AnalysisStatus,
  ExecutionRequest,
  ExecutionResponse,
} from '../types/execution';
import { useAuthStore } from '../store/authStore';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Request interceptor to attach JWT token to authenticated requests.
 */
apiClient.interceptors.request.use(
  async (config) => {
    const token = await useAuthStore.getState().getAccessToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

/**
 * Response interceptor to handle 401 errors.
 */
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // Token expired or invalid - clear auth state
      useAuthStore.getState().logout();
    }
    return Promise.reject(error);
  }
);

/**
 * Execute Python code on the backend.
 */
export async function executeCode(request: ExecutionRequest): Promise<ExecutionResponse> {
  const response = await apiClient.post<ExecutionResponse>('/execute', request);
  return response.data;
}

/**
 * Analyze code complexity using LLM.
 */
export async function analyzeCode(request: AnalyzeRequest): Promise<AnalyzeResponse> {
  const response = await apiClient.post<AnalyzeResponse>('/analyze', request);
  return response.data;
}

/**
 * Check if complexity analysis is available.
 */
export async function getAnalysisStatus(): Promise<AnalysisStatus> {
  const response = await apiClient.get<AnalysisStatus>('/analyze/status');
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
