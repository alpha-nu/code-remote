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
