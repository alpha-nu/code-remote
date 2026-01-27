/**
 * Toolbar with run button and settings.
 */

import { useEditorStore } from '../store/editorStore';
import { executeCode } from '../api/client';
import { UserMenu } from './UserMenu';
import { useEffect, useState } from 'react';
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
