/**
 * Toolbar with run button and settings.
 */

import { useEditorStore, updateSnippetCachesAfterAnalysis } from '../store/editorStore';
import { executeCode, executeCodeAsync } from '../api/client';
import { UserMenu } from './UserMenu';
import { useEffect, useState, useCallback, useRef } from 'react';
import { useAuthStore } from '../store/authStore';
import { useWebSocket, type ExecutionResultMessage, type WebSocketMessage, type ConnectionState } from '../hooks';
import type { ExecutionResponse, AnalyzeResponse } from '../types/execution';

interface ToolbarProps {
  onConnectionStateChange?: (state: ConnectionState) => void;
  onConnectionIdChange?: (id: string | null) => void;
}

export function Toolbar({ onConnectionStateChange, onConnectionIdChange }: ToolbarProps) {
  const {
    code,
    isExecuting,
    setIsExecuting,
    setResult,
    setApiError,
    timeoutSeconds,
    autoAnalyze,
  } = useEditorStore();

  const { isAuthenticated } = useAuthStore();

  // WebSocket connection for async execution
  const {
    connectionState,
    connectionId,
    addMessageHandler,
  } = useWebSocket({ autoConnect: true });

  // Notify parent of connection state changes
  useEffect(() => {
    onConnectionStateChange?.(connectionState);
  }, [connectionState, onConnectionStateChange]);

  // Notify parent of connectionId changes
  useEffect(() => {
    onConnectionIdChange?.(connectionId);
  }, [connectionId, onConnectionIdChange]);

  // Track pending job for async execution — use a ref so the WS message
  // handler always reads the current value without triggering re-registration.
  const [pendingJobId, setPendingJobId] = useState<string | null>(null);
  const pendingJobIdRef = useRef<string | null>(null);
  const connectionIdRef = useRef<string | null>(connectionId);

  // Keep refs in sync with state
  useEffect(() => { pendingJobIdRef.current = pendingJobId; }, [pendingJobId]);
  useEffect(() => { connectionIdRef.current = connectionId; }, [connectionId]);

  // Handle incoming WebSocket messages.
  // The callback is intentionally stable (no closure deps that change per
  // render) — it reads mutable values via refs / Zustand getState().
  const handleMessage = useCallback((message: WebSocketMessage) => {
    // --- Execution results ---
    if (message.type === 'execution_result') {
      const resultMsg = message as unknown as ExecutionResultMessage;

      // Gate on isExecuting to handle the race where the WS result arrives
      // before the HTTP response that carries the job_id (same pattern as
      // the analysis streaming handler below).
      const store = useEditorStore.getState();
      if (!store.isExecuting) return;

      // If we already know our job_id, do a strict match
      if (pendingJobIdRef.current && resultMsg.job_id !== pendingJobIdRef.current) return;

      const result: ExecutionResponse = {
        success: resultMsg.success,
        stdout: resultMsg.stdout,
        stderr: resultMsg.stderr,
        error: resultMsg.error,
        error_type: resultMsg.error_type,
        execution_time_ms: resultMsg.execution_time_ms,
        timed_out: resultMsg.timed_out,
        security_violations: resultMsg.security_violations.map((v) => ({
          type: 'security',
          message: v.message,
          line: v.line,
          column: v.column,
        })),
      };

      useEditorStore.getState().setResult(result);
      useEditorStore.getState().setIsExecuting(false);
      setPendingJobId(null);

      // Auto-analyze after successful execution
      if (useEditorStore.getState().autoAnalyze && result.success) {
        useEditorStore.getState().analyze(connectionIdRef.current);
      }
      return;
    }

    // --- Analysis streaming ---
    // Gate on isAnalyzing rather than analysisJobId to avoid a race condition:
    // In Lambda/Mangum, BackgroundTasks block the HTTP response, so WS
    // messages arrive *before* the HTTP response that carries the job_id.
    // isAnalyzing is set synchronously before the HTTP call, so it's safe.
    const store = useEditorStore.getState();
    if (!store.isAnalyzing) return;

    // Lazily capture the job_id from the first analysis message when the
    // HTTP response hasn't arrived yet (analysisJobId is still null).
    const msgJobId = message.job_id as string | undefined;
    if (msgJobId && !store.analysisJobId) {
      store.setAnalysisJobId(msgJobId);
    }

    // If we already have a job_id, validate it matches
    if (store.analysisJobId && msgJobId !== store.analysisJobId) return;

    if (message.type === 'analysis_stream_chunk') {
      store.appendAnalysisStreamChunk(message.chunk as string);
      return;
    }

    if (message.type === 'analysis_stream_complete') {
      const result = (message as unknown as { result: AnalyzeResponse }).result;
      store.setAnalysis(result);
      store.setIsAnalyzing(false);
      store.setAnalysisJobId(null);
      // Note: analysisStreamText is cleared by ComplexityPanel once the typewriter finishes
      updateSnippetCachesAfterAnalysis(result);
      return;
    }

    if (message.type === 'analysis_stream_error') {
      store.setIsAnalyzing(false);
      store.setAnalysisJobId(null);
      store.setApiError(message.error as string);
      return;
    }
  }, []);

  // Register message handler — stable callback means this only runs once
  useEffect(() => {
    const cleanup = addMessageHandler(handleMessage);
    return cleanup;
  }, [addMessageHandler, handleMessage]);

  // --- Safety net: timeout for pending async execution ---
  // If the WS message never arrives (connection lost, worker error, etc.),
  // reset after the configured execution timeout + a generous buffer for
  // SQS latency, Lambda cold-start, and WS delivery.
  useEffect(() => {
    if (!pendingJobId) return;

    const bufferMs = 15_000; // 15 s on top of execution timeout
    const timeoutMs = useEditorStore.getState().timeoutSeconds * 1000 + bufferMs;

    const timer = setTimeout(() => {
      if (pendingJobIdRef.current === pendingJobId) {
        useEditorStore.getState().setIsExecuting(false);
        useEditorStore.getState().setApiError(
          'Execution result not received — the connection may have been lost. Please try again.'
        );
        setPendingJobId(null);
      }
    }, timeoutMs);

    return () => clearTimeout(timer);
  }, [pendingJobId]);

  // --- Safety net: timeout for pending async analysis ---
  useEffect(() => {
    const store = useEditorStore.getState();
    if (!store.isAnalyzing || !store.analysisJobId) return;

    const jobId = store.analysisJobId;
    const timer = setTimeout(() => {
      const s = useEditorStore.getState();
      if (s.isAnalyzing && s.analysisJobId === jobId) {
        s.setIsAnalyzing(false);
        s.setAnalysisJobId(null);
        s.setApiError(
          'Analysis result not received — the connection may have been lost. Please try again.'
        );
      }
    }, 60_000); // 60 s — LLM streaming can be slow

    return () => clearTimeout(timer);
    // Re-run when analysisJobId changes (subscribed below)
  });

  // Subscribe to analysisJobId changes so the timeout effect above re-runs
  useEditorStore((s) => s.analysisJobId);

  // --- Detect WebSocket disconnect while jobs are pending ---
  // When connectionId becomes null (WS closed), any in-flight async job
  // will push its result to the now-dead connection.  Reset immediately
  // rather than waiting for the full timeout.
  useEffect(() => {
    if (connectionId) return; // connected — nothing to do

    // Execution pending?
    if (pendingJobId) {
      useEditorStore.getState().setIsExecuting(false);
      useEditorStore.getState().setApiError(
        'Connection lost while waiting for execution result. Please try again.'
      );
      // Defer setPendingJobId to avoid synchronous setState in effect body
      const timer = setTimeout(() => setPendingJobId(null), 0);
      return () => clearTimeout(timer);
    }

    // Analysis streaming?
    const store = useEditorStore.getState();
    if (store.isAnalyzing && store.analysisJobId) {
      store.setIsAnalyzing(false);
      store.setAnalysisJobId(null);
      store.setApiError(
        'Connection lost during analysis. Please try again.'
      );
    }
  }, [connectionId, pendingJobId]);

  const [isLight, setIsLight] = useState(() =>
    typeof document !== 'undefined' && document.documentElement.classList.contains('light-theme'),
  );

  useEffect(() => {
    const onTheme = () => setIsLight(document.documentElement.classList.contains('light-theme'));
    window.addEventListener('themechange', onTheme);
    window.addEventListener('storage', onTheme);
    return () => {
      window.removeEventListener('themechange', onTheme);
      window.removeEventListener('storage', onTheme);
    };
  }, []);

  const handleRun = useCallback(async () => {
    if (isExecuting || !code.trim()) return;

    // Check auth (backend enforces this, but show friendly message)
    if (!isAuthenticated) {
      setApiError('Please sign in to run code');
      return;
    }

    // Cancel any in-progress analysis before starting new execution
    useEditorStore.getState().cancelAnalysis();

    setIsExecuting(true);
    setResult(null);
    setApiError(null);
    setPendingJobId(null);

    try {
      // Use async execution if WebSocket connected, else fall back to sync
      if (connectionState === 'connected' && connectionId) {
        const response = await executeCodeAsync({
          code,
          connection_id: connectionId,
          timeout_seconds: timeoutSeconds,
        });
        // Set ref immediately (synchronous) so the WS handler can match
        // even before React re-renders from the setState below.
        pendingJobIdRef.current = response.job_id;
        setPendingJobId(response.job_id);
        // Result will come via WebSocket
      } else {
        // Fall back to sync execution
        const result = await executeCode({
          code,
          timeout_seconds: timeoutSeconds,
        });
        setResult(result);
        setIsExecuting(false);

        // Auto-analyze after successful execution
        if (autoAnalyze && result.success) {
          await useEditorStore.getState().analyze();
        }
      }
    } catch (error) {
      if (error instanceof Error) {
        setApiError(error.message);
      } else {
        setApiError('An unexpected error occurred');
      }
      setIsExecuting(false);
    }
  }, [code, isExecuting, isAuthenticated, connectionState, connectionId, timeoutSeconds, autoAnalyze, setIsExecuting, setResult, setApiError]);

  // analysis is provided by the store via `analyze()`

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    // Ctrl/Cmd + Enter to run
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      handleRun();
    }
  }, [handleRun]);

  // Add global keyboard shortcut
  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  return (
    <div className="toolbar">
      <div className="toolbar-left">
        <div className="app-logo">
          <span className="code-keyword">def</span>
          <span className="code-function">__code_remote__</span>
          <span className="code-punctuation">():</span>
        </div>
        <span className="keyboard-hint">Python Sandbox</span>
      </div>

      <div className="toolbar-center">
        <div style={{display: 'flex', alignItems: 'center', gap: 12}}>
          <button
            className={`run-button ${isExecuting ? 'running' : ''}`}
            onClick={handleRun}
            disabled={isExecuting || !code.trim()}
            aria-label="Run code"
          >
            {isExecuting ? (
              pendingJobId ? 'Queued...' : 'Running...'
            ) : (
              <>
                <span className="btn-icon">▶</span>
                <span>Run</span>
              </>
            )}
          </button>

          <span className="keyboard-hint">Ctrl+Enter</span>
        </div>
      </div>

      <div className="toolbar-right">
          {/* auto-analyze and timeout moved to Output tools */}
          <button
            className="theme-toggle"
            onClick={() => {
              const root = document.documentElement;
              const currentlyLight = root.classList.contains('light-theme');
              if (currentlyLight) {
                root.classList.remove('light-theme');
                localStorage.setItem('theme', 'dark');
              } else {
                root.classList.add('light-theme');
                localStorage.setItem('theme', 'light');
              }
              // animate the icon briefly
              const svg = document.querySelector('.theme-toggle-icon');
              if (svg) {
                svg.classList.add('animate');
                setTimeout(() => svg.classList.remove('animate'), 420);
              }
              window.dispatchEvent(new Event('themechange'));
            }}
            aria-label="Toggle theme"
          >
            {isLight ? (
              // light theme -> show dark crescent
              <svg className="theme-toggle-icon" viewBox="0 0 24 24" width="28" height="28" aria-hidden="true">
                <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" fill="#0b1220" />
              </svg>
            ) : (
              // dark theme -> show sun
              <svg className="theme-toggle-icon" viewBox="0 0 24 24" width="28" height="28" aria-hidden="true">
                <circle cx="12" cy="12" r="4" fill="#FFD43B" />
                <g stroke="#FFD43B" strokeWidth="2" strokeLinecap="round">
                  <line x1="12" y1="1" x2="12" y2="3" />
                  <line x1="12" y1="21" x2="12" y2="23" />
                  <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
                  <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
                  <line x1="1" y1="12" x2="3" y2="12" />
                  <line x1="21" y1="12" x2="23" y2="12" />
                  <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
                  <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
                </g>
              </svg>
            )}
          </button>
        <UserMenu />
      </div>
    </div>
  );
}
