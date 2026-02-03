/**
 * Code execution hook with support for both sync and async modes.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { executeCode as executeCodeSync } from '../api/client';
import type { ExecutionResponse } from '../types/execution';
import {
  useWebSocket,
  type ExecutionResultMessage,
  type WebSocketMessage,
} from './useWebSocket';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/** Execution mode: sync (HTTP) or async (WebSocket) */
export type ExecutionMode = 'sync' | 'async';

/** Job status for async execution */
export type JobStatus = 'idle' | 'queued' | 'executing' | 'completed' | 'error';

interface UseExecutionOptions {
  /** Preferred execution mode. Default: 'async' if WebSocket available, else 'sync' */
  preferredMode?: ExecutionMode;
  /** Callback when execution completes */
  onComplete?: (result: ExecutionResponse) => void;
  /** Callback when execution fails */
  onError?: (error: string) => void;
}

interface UseExecutionReturn {
  /** Execute code */
  execute: (code: string, timeoutSeconds?: number) => Promise<void>;
  /** Whether execution is in progress */
  isExecuting: boolean;
  /** Current execution result */
  result: ExecutionResponse | null;
  /** Error message if execution failed */
  error: string | null;
  /** Current execution mode being used */
  mode: ExecutionMode;
  /** Job status for async execution */
  jobStatus: JobStatus;
  /** Current job ID for async execution */
  jobId: string | null;
  /** Cancel current async execution (best effort) */
  cancel: () => void;
  /** WebSocket connection state */
  connectionState: ReturnType<typeof useWebSocket>['connectionState'];
  /** WebSocket connection ID */
  connectionId: string | null;
}

/**
 * Hook for executing code with automatic mode selection.
 *
 * Features:
 * - Automatic fallback from async to sync if WebSocket unavailable
 * - Job tracking for async execution
 * - Cancellation support
 * - Unified result handling
 */
export function useExecution(options: UseExecutionOptions = {}): UseExecutionReturn {
  const { preferredMode = 'async', onComplete, onError } = options;

  const [isExecuting, setIsExecuting] = useState(false);
  const [result, setResult] = useState<ExecutionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<JobStatus>('idle');
  const [jobId, setJobId] = useState<string | null>(null);

  // Track which job we're waiting for
  const pendingJobRef = useRef<string | null>(null);
  const isCancelledRef = useRef(false);

  // WebSocket connection
  const {
    connectionState,
    connectionId,
    addMessageHandler,
  } = useWebSocket();

  // Determine actual mode based on WebSocket availability
  const mode: ExecutionMode =
    preferredMode === 'async' && connectionState === 'connected' && connectionId
      ? 'async'
      : 'sync';

  /**
   * Handle execution result from WebSocket.
   */
  const handleWebSocketMessage = useCallback(
    (message: WebSocketMessage) => {
      // Only handle execution results
      if (message.type !== 'execution_result') {
        return;
      }

      const resultMessage = message as unknown as ExecutionResultMessage;

      // Only handle if this is the job we're waiting for
      if (resultMessage.job_id !== pendingJobRef.current) {
        return;
      }

      // Check if cancelled
      if (isCancelledRef.current) {
        pendingJobRef.current = null;
        return;
      }

      // Convert to ExecutionResponse format
      const executionResult: ExecutionResponse = {
        success: resultMessage.success,
        stdout: resultMessage.stdout,
        stderr: resultMessage.stderr,
        error: resultMessage.error,
        error_type: resultMessage.error_type,
        execution_time_ms: resultMessage.execution_time_ms,
        timed_out: resultMessage.timed_out,
        security_violations: resultMessage.security_violations.map((v) => ({
          type: 'security',
          message: v.message,
          line: v.line,
          column: v.column,
        })),
      };

      setResult(executionResult);
      setJobStatus('completed');
      setIsExecuting(false);
      pendingJobRef.current = null;

      onComplete?.(executionResult);
    },
    [onComplete]
  );

  // Register WebSocket message handler
  useEffect(() => {
    const unsubscribe = addMessageHandler(handleWebSocketMessage);
    return unsubscribe;
  }, [addMessageHandler, handleWebSocketMessage]);

  /**
   * Execute code asynchronously via SQS/WebSocket.
   */
  const executeAsync = useCallback(
    async (code: string, timeoutSeconds: number = 30): Promise<void> => {
      if (!connectionId) {
        throw new Error('WebSocket not connected');
      }

      // Submit job to queue
      const token = await (await import('../store/authStore')).useAuthStore.getState().getAccessToken();

      const response = await fetch(`${API_BASE_URL}/execute/async`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          code,
          connection_id: connectionId,
          timeout_seconds: timeoutSeconds,
        }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || `HTTP ${response.status}`);
      }

      const data = await response.json();
      const newJobId = data.job_id;

      setJobId(newJobId);
      setJobStatus('queued');
      pendingJobRef.current = newJobId;

      // Result will come via WebSocket
    },
    [connectionId]
  );

  /**
   * Execute code synchronously via HTTP.
   */
  const executeSync = useCallback(
    async (code: string, timeoutSeconds: number = 30): Promise<void> => {
      const executionResult = await executeCodeSync({
        code,
        timeout_seconds: timeoutSeconds,
      });

      setResult(executionResult);
      onComplete?.(executionResult);
    },
    [onComplete]
  );

  /**
   * Execute code using the current mode.
   */
  const execute = useCallback(
    async (code: string, timeoutSeconds: number = 30): Promise<void> => {
      // Reset state
      setIsExecuting(true);
      setResult(null);
      setError(null);
      setJobStatus('idle');
      setJobId(null);
      isCancelledRef.current = false;

      try {
        if (mode === 'async') {
          await executeAsync(code, timeoutSeconds);
        } else {
          await executeSync(code, timeoutSeconds);
          setIsExecuting(false);
        }
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Execution failed';
        setError(errorMessage);
        setJobStatus('error');
        setIsExecuting(false);
        onError?.(errorMessage);
      }
    },
    [mode, executeAsync, executeSync, onError]
  );

  /**
   * Cancel current async execution.
   */
  const cancel = useCallback(() => {
    if (pendingJobRef.current) {
      isCancelledRef.current = true;
      pendingJobRef.current = null;
      setIsExecuting(false);
      setJobStatus('idle');
      setJobId(null);
    }
  }, []);

  return {
    execute,
    isExecuting,
    result,
    error,
    mode,
    jobStatus,
    jobId,
    cancel,
    connectionState,
    connectionId,
  };
}

export default useExecution;
