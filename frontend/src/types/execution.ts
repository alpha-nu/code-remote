/**
 * Types for code execution API.
 */

export interface ExecutionRequest {
  code: string;
  timeout_seconds?: number;
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
