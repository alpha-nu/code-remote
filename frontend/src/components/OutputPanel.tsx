/**
 * Output panel to display execution results.
 */

import { useEditorStore } from '../store/editorStore';
import { ComplexityPanel } from './ComplexityPanel';
import spinner from '../assets/spinner.svg';

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
  // Always render the panel header and the tools area, then render content
  return (
    <div className="output-panel">
      <div className="output-header">
        <span className="output-title">Output</span>
        {result ? (
          <>
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
                    <circle cx="11" cy="11" r="6" />
                    <line x1="21" y1="21" x2="16.65" y2="16.65" />
                  </svg>
                  <span>Analyze Code</span>
                </>
              )}
            </button>
          )}
        </div>
      </div>

      <div className="output-content">
        {isExecuting && (
          <div className="loading-spinner">
            <img src={spinner} className="spinner-logo" alt="executing" /> Executing code...
          </div>
        )}

        {apiError && (
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
                <p className="empty-output">Code executed successfully with no output.</p>
              </div>
            )}

            {/* Complexity Analysis */}
            <ComplexityPanel />

            {/* analyze button moved to top tools area */}
          </>
        )}
      </div>
    </div>
  );
}
