/**
 * Types for code execution API.
 */

export interface ExecutionRequest {
  code: string;
  timeout_seconds?: number;
}

export interface AsyncExecutionRequest {
  code: string;
  connection_id: string;
  timeout_seconds?: number;
}

export interface JobSubmittedResponse {
  job_id: string;
  status: string;
}

export interface ExecutionResponse {
  success: boolean;
  stdout: string;
  stderr: string;
  error: string | null;
  error_type: string | null;
  execution_time_ms: number;
  timed_out: boolean;
  security_violations: SecurityViolation[];
}

export interface SecurityViolation {
  type: string;
  message: string;
  line: number | null;
  column: number | null;
}

/**
 * Types for code analysis API.
 */

export interface AnalyzeRequest {
  code: string;
  snippet_id?: string;
}

export interface AsyncAnalyzeRequest {
  code: string;
  connection_id: string;
  snippet_id?: string;
}

export interface AnalyzeResponse {
  success: boolean;
  time_complexity: string;
  space_complexity: string;
  narrative: string;
  error: string | null;
  available: boolean;
  model: string | null;
}

export interface AnalysisStatus {
  available: boolean;
  provider: string | null;
}

/**
 * WebSocket message types for analysis streaming.
 */

export interface AnalysisStreamStartMessage {
  type: 'analysis_stream_start';
  job_id: string;
}

export interface AnalysisStreamChunkMessage {
  type: 'analysis_stream_chunk';
  job_id: string;
  chunk: string;
}

export interface AnalysisStreamCompleteMessage {
  type: 'analysis_stream_complete';
  job_id: string;
  result: AnalyzeResponse;
}

export interface AnalysisStreamErrorMessage {
  type: 'analysis_stream_error';
  job_id: string;
  error: string;
}
