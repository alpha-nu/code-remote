/**
 * Output panel to display execution results.
 */

import { useEditorStore } from '../store/editorStore';
import { ComplexityPanel } from './ComplexityPanel';
import spinner from '../assets/spinner.svg';
import { useRef, useState, useEffect } from 'react';

export function OutputPanel() {
  const {
    result,
    isExecuting,
    apiError,
    autoAnalyze,
    isAnalyzing,
    analyze,
    setAutoAnalyze,
    timeoutSeconds,
    setTimeoutSeconds,
    hasRun,
  } = useEditorStore();

  // Splitter state: percentage of available space for output section (default 50%)
  const [splitPercent, setSplitPercent] = useState(50);
  const panelRef = useRef<HTMLDivElement>(null);
  const draggingRef = useRef(false);
  const dragOffsetRef = useRef(0);

  // Handle dragging
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!draggingRef.current || !panelRef.current) return;

      const panel = panelRef.current;
      const rect = panel.getBoundingClientRect();
      const availableHeight = rect.height - 48 - 40; // subtract header and tools height
      const mouseY = e.clientY - rect.top - 48 - 40 - dragOffsetRef.current;
      const newPercent = Math.max(20, Math.min(80, (mouseY / availableHeight) * 100));
      setSplitPercent(newPercent);
    };

    const handleTouchMove = (e: TouchEvent) => {
      if (!draggingRef.current || !panelRef.current) return;
      e.preventDefault();

      const touch = e.touches[0];
      const panel = panelRef.current;
      const rect = panel.getBoundingClientRect();
      const availableHeight = rect.height - 48 - 40;
      const touchY = touch.clientY - rect.top - 48 - 40 - dragOffsetRef.current;
      const newPercent = Math.max(20, Math.min(80, (touchY / availableHeight) * 100));
      setSplitPercent(newPercent);
    };

    const handleMouseUp = () => {
      draggingRef.current = false;
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('touchmove', handleTouchMove, { passive: false });
    document.addEventListener('mouseup', handleMouseUp);
    document.addEventListener('touchend', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('touchmove', handleTouchMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.removeEventListener('touchend', handleMouseUp);
    };
  }, []);

  // Show splitter whenever we have execution results
  const showSplitter = !!result;

  // Always render the panel header and the tools area, then render content
  return (
    <div className="output-panel" ref={panelRef}>
      <div className="output-header">
        <span className="output-title">Output</span>
        {result ? (
          <>
            {/* Execution time pill (prominent) - styled like status pills; color reflects success/error */}
            <span
              className={`output-time-pill ${result.success ? 'success' : 'error'}`}
              aria-label={`Execution time ${result.execution_time_ms.toFixed(2)} milliseconds`}
            >
              {result.execution_time_ms.toFixed(2)} ms
            </span>
            <span className={`output-status ${result.success ? 'success' : 'error'}`}>
              {result.success ? '✓ Success' : '✗ Error'}
            </span>
            <span className="output-time">{result.execution_time_ms.toFixed(2)} ms</span>
          </>
        ) : isExecuting ? (
          <span className="output-status running">Running...</span>
        ) : apiError ? (
          <span className="output-status error">API Error</span>
        ) : null}
      </div>

      <div className="output-tools">
        <div className="output-tools-left">
          <label className="auto-analyze-label">
            <input
              type="checkbox"
              checked={autoAnalyze}
              onChange={(e) => setAutoAnalyze(e.target.checked)}
              disabled={isExecuting}
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
        </div>

        <div className="output-tools-right">
          {/* Show explicit analyze button only after code has been executed once and when autoAnalyze is off */}
          {!autoAnalyze && hasRun && (
            <button className="analyze-button" onClick={() => analyze()} disabled={isAnalyzing}>
              {isAnalyzing ? (
                'Analyzing...'
              ) : (
                <>
                  <svg className="btn-icon small" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
                  </svg>
                  <span>Analyze Code</span>
                </>
              )}
            </button>
          )}
        </div>
      </div>

      <div className="output-sections-container">
        <div
          className="output-content-wrapper"
          style={showSplitter ? { height: `${splitPercent}%` } : undefined}
        >
          <div className="output-content">
            <div className="output-content-inner">
            {isExecuting && !result && (
              <div className="loading-spinner">
                <img src={spinner} className="spinner-logo small" alt="executing" /> Executing code...
              </div>
            )}

            {apiError && !result && (
              <div className="output-content error-content">
                <pre>{apiError}</pre>
              </div>
            )}

            {!isExecuting && !apiError && !result && (
              <div className="output-content empty">
                <p>Click "Run" to execute your code</p>
              </div>
            )}

            {result && (
              <>
                {/* Stdout */}
                {result.stdout && (
                  <div className="output-section">
                    <div className="section-label">stdout</div>
                    <pre className="stdout">{result.stdout}</pre>
                  </div>
                )}

                {/* Stderr */}
                {result.stderr && (
                  <div className="output-section">
                    <div className="section-label">stderr</div>
                    <pre className="stderr">{result.stderr}</pre>
                  </div>
                )}

                {/* Error */}
                {result.error && (
                  <div className="output-section">
                    <div className="section-label error-label">
                      {result.error_type || 'Error'}
                      {result.timed_out && ' (Timeout)'}
                    </div>
                    <pre className="error-message">{result.error}</pre>
                  </div>
                )}

                {/* Security Violations */}
                {result.security_violations.length > 0 && (
                  <div className="output-section">
                    <div className="section-label error-label">Security Violations</div>
                    <ul className="violations-list">
                      {result.security_violations.map((v, i) => (
                        <li key={i}>
                          <strong>{v.type}</strong>
                          {v.line && ` (line ${v.line})`}: {v.message}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Empty success state */}
                {result.success && !result.stdout && !result.stderr && (
                  <div className="output-section">
                    <div className="section-label">stdout</div>
                    <pre className="stdout">(no output)</pre>
                  </div>
                )}
              </>
            )}
            </div>
          </div>
        </div>

        {/* Draggable splitter */}
        {showSplitter && (
          <div
            className="output-splitter"
            role="separator"
            aria-orientation="horizontal"
            aria-valuenow={splitPercent}
            onMouseDown={(e) => {
              draggingRef.current = true;
              dragOffsetRef.current = 0;
              document.body.style.userSelect = 'none';
              document.body.style.cursor = 'row-resize';
              e.preventDefault();
            }}
            onTouchStart={(e) => {
              draggingRef.current = true;
              dragOffsetRef.current = 0;
              document.body.style.userSelect = 'none';
              document.body.style.cursor = 'row-resize';
              e.preventDefault();
            }}
          >
            <div className="splitter-handle" />
          </div>
        )}

        {/* Complexity Analysis in separate scrollable container */}
        {showSplitter && (
          <div
            className="complexity-panel-wrapper"
            style={{ height: `${100 - splitPercent}%` }}
          >
            <ComplexityPanel />
          </div>
        )}
      </div>
    </div>
  );
}
