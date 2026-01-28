/**
 * API client for backend services.
 */

import axios, { AxiosError } from 'axios';
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
  timeout: 35000, // 35s timeout (slightly more than max execution time)
});

/**
 * Format API errors into user-friendly messages.
 */
function formatApiError(error: AxiosError): Error {
  const url = error.config?.url || 'unknown endpoint';
  const baseURL = error.config?.baseURL || API_BASE_URL;

  // Network error (no response received)
  if (error.code === 'ERR_NETWORK' || !error.response) {
    return new Error(
      `Unable to connect to backend at ${baseURL}.\n` +
      `Please ensure the backend server is running.\n\n` +
      `If running locally: cd backend && uvicorn api.main:app --reload\n` +
      `Endpoint: ${url}`
    );
  }

  // Timeout
  if (error.code === 'ECONNABORTED') {
    return new Error(`Request timed out. The server took too long to respond.`);
  }

  // Server responded with error
  const status = error.response.status;
  const data = error.response.data as Record<string, unknown>;

  // Try to extract error detail from response
  const detail = data?.detail || data?.message || data?.error;

  switch (status) {
    case 400:
      return new Error(`Bad Request: ${detail || 'Invalid request data'}`);
    case 401:
      return new Error(`Unauthorized: ${detail || 'Please sign in again'}`);
    case 403:
      return new Error(`Forbidden: ${detail || 'You do not have permission'}`);
    case 404:
      return new Error(`Not Found: ${detail || `Endpoint ${url} not found`}`);
    case 422:
      return new Error(`Validation Error: ${detail || 'Invalid input data'}`);
    case 429:
      return new Error(`Rate Limited: Too many requests. Please try again later.`);
    case 500:
      return new Error(`Server Error: ${detail || 'Internal server error'}`);
    case 502:
      return new Error(`Bad Gateway: Backend server is not responding. Is it deployed?`);
    case 503:
      return new Error(`Service Unavailable: ${detail || 'Server is temporarily unavailable'}`);
    case 504:
      return new Error(`Gateway Timeout: Backend server took too long to respond.`);
    default:
      return new Error(`Error ${status}: ${detail || error.message}`);
  }
}

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
 * Response interceptor to handle errors with better messages.
 */
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Token expired or invalid - clear auth state
      useAuthStore.getState().logout();
    }
    return Promise.reject(formatApiError(error));
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
