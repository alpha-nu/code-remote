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
}

export interface AnalyzeResponse {
  success: boolean;
  time_complexity: string;
  space_complexity: string;
  time_explanation: string;
  space_explanation: string;
  algorithm_identified: string | null;
  suggestions: string[] | null;
  error: string | null;
  available: boolean;
  model: string | null;
}

export interface AnalysisStatus {
  available: boolean;
  provider: string | null;
}
