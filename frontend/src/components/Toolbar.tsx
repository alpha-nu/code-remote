/**
 * Toolbar with run button and settings.
 */

import { useEditorStore } from '../store/editorStore';
import { executeCode } from '../api/client';
import { UserMenu } from './UserMenu';
import themeToggleIcon from '../assets/theme-toggle.svg';
import { useAuthStore } from '../store/authStore';

export function Toolbar() {
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

  const handleRun = async () => {
    if (isExecuting || !code.trim()) return;

    // Check auth (backend enforces this, but show friendly message)
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

      // Auto-analyze after successful execution (use store helper)
      if (autoAnalyze && result.success) {
        await (useEditorStore.getState().analyze());
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

  // analysis is provided by the store via `analyze()`

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
        <div style={{display: 'flex', alignItems: 'center', gap: 12}}>
          <button
            className={`run-button ${isExecuting ? 'running' : ''}`}
            onClick={handleRun}
            disabled={isExecuting || !code.trim()}
            aria-label="Run code"
          >
            {isExecuting ? (
              'Running...'
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
              const isLight = root.classList.contains('light-theme');
              if (isLight) {
                root.classList.remove('light-theme');
                localStorage.setItem('theme', 'dark');
              } else {
                root.classList.add('light-theme');
                localStorage.setItem('theme', 'light');
              }
              // animate the icon briefly
              const img = document.querySelector('.theme-toggle-icon');
              if (img) {
                img.classList.add('animate');
                setTimeout(() => img.classList.remove('animate'), 420);
              }
              window.dispatchEvent(new Event('themechange'));
            }}
            aria-label="Toggle theme"
          >
            <img src={themeToggleIcon} className="theme-toggle-icon" alt="Toggle theme" />
          </button>
        <UserMenu />
      </div>
    </div>
  );
}
