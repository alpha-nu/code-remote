/**
 * Toolbar with run button and settings.
 */

import { useEditorStore } from '../store/editorStore';
import { executeCode } from '../api/client';

export function Toolbar() {
  const {
    code,
    isExecuting,
    setIsExecuting,
    setResult,
    setApiError,
    timeoutSeconds,
    setTimeoutSeconds,
  } = useEditorStore();

  const handleRun = async () => {
    if (isExecuting || !code.trim()) return;

    setIsExecuting(true);
    setResult(null);
    setApiError(null);

    try {
      const result = await executeCode({
        code,
        timeout_seconds: timeoutSeconds,
      });
      setResult(result);
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
      </div>
    </div>
  );
}
