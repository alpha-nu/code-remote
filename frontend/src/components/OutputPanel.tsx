/**
 * Output panel to display execution results.
 */

import { useEditorStore } from '../store/editorStore';
import { ComplexityPanel } from './ComplexityPanel';

export function OutputPanel() {
  const { result, isExecuting, apiError } = useEditorStore();

  if (isExecuting) {
    return (
      <div className="output-panel">
        <div className="output-header">
          <span className="output-title">Output</span>
          <span className="output-status running">Running...</span>
        </div>
        <div className="output-content">
          <div className="loading-spinner">⏳ Executing code...</div>
        </div>
      </div>
    );
  }

  if (apiError) {
    return (
      <div className="output-panel">
        <div className="output-header">
          <span className="output-title">Output</span>
          <span className="output-status error">API Error</span>
        </div>
        <div className="output-content error-content">
          <pre>{apiError}</pre>
        </div>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="output-panel">
        <div className="output-header">
          <span className="output-title">Output</span>
        </div>
        <div className="output-content empty">
          <p>Click "Run" to execute your code</p>
        </div>
      </div>
    );
  }

  return (
    <div className="output-panel">
      <div className="output-header">
        <span className="output-title">Output</span>
        <span className={`output-status ${result.success ? 'success' : 'error'}`}>
          {result.success ? '✓ Success' : '✗ Error'}
        </span>
        <span className="output-time">{result.execution_time_ms.toFixed(2)} ms</span>
      </div>

      <div className="output-content">
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
      </div>
    </div>
  );
}
