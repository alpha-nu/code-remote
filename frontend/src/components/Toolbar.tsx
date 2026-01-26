/**
 * Toolbar with run button and settings.
 */

import { useEditorStore } from '../store/editorStore';
import { analyzeCode, executeCode } from '../api/client';
import { UserMenu } from './UserMenu';
import { useAuthStore } from '../store/authStore';

export function Toolbar() {
  const {
    code,
    isExecuting,
    setIsExecuting,
    setResult,
    isAnalyzing,
    setIsAnalyzing,
    setAnalysis,
    autoAnalyze,
    setAutoAnalyze,
    setApiError,
    timeoutSeconds,
    setTimeoutSeconds,
  } = useEditorStore();

  const { isAuthenticated } = useAuthStore();

  const handleRun = async () => {
    if (isExecuting || !code.trim()) return;

    // Require authentication to run code
    if (!isAuthenticated) {
      setApiError('Please sign in to run code');
      return;
    }

    setIsExecuting(true);
    setResult(null);
    setApiError(null);

    try {
      const result = await executeCode({
        code,
        timeout_seconds: timeoutSeconds,
      });
      setResult(result);

      // Auto-analyze after successful execution
      if (autoAnalyze && result.success) {
        handleAnalyze();
      }
    } catch (error) {
      if (error instanceof Error) {
        setApiError(error.message);
      } else {
        setApiError('An unexpected error occurred');
      }
    } finally {
      setIsExecuting(false);
    }
  };

  const handleAnalyze = async () => {
    if (isAnalyzing || !code.trim()) return;

    setIsAnalyzing(true);
    setAnalysis(null);

    try {
      const analysis = await analyzeCode({ code });
      setAnalysis(analysis);
    } catch (error) {
      // Silently fail analysis - it's optional
      console.error('Analysis failed:', error);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    // Ctrl/Cmd + Enter to run
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      handleRun();
    }
  };

  // Add global keyboard shortcut
  if (typeof window !== 'undefined') {
    window.removeEventListener('keydown', handleKeyDown);
    window.addEventListener('keydown', handleKeyDown);
  }

  return (
    <div className="toolbar">
      <div className="toolbar-left">
        <h1 className="app-title">Code Remote</h1>
        <span className="app-subtitle">Python Sandbox</span>
      </div>

      <div className="toolbar-center">
        <button
          className={`run-button ${isExecuting ? 'running' : ''}`}
          onClick={handleRun}
          disabled={isExecuting || !code.trim()}
        >
          {isExecuting ? (
            <>
              <span className="spinner">⟳</span> Running...
            </>
          ) : (
            <>▶ Run</>
          )}
        </button>
        <span className="keyboard-hint">Ctrl+Enter</span>
      </div>

      <div className="toolbar-right">
        <label className="auto-analyze-label">
          <input
            type="checkbox"
            checked={autoAnalyze}
            onChange={(e) => setAutoAnalyze(e.target.checked)}
          />
          Auto-analyze
        </label>
        <label className="timeout-label">
          Timeout:
          <select
            value={timeoutSeconds}
            onChange={(e) => setTimeoutSeconds(Number(e.target.value))}
            disabled={isExecuting}
          >
            <option value={5}>5s</option>
            <option value={10}>10s</option>
            <option value={30}>30s</option>
          </select>
        </label>
        <UserMenu />
      </div>
    </div>
  );
}
