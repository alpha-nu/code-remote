/**
 * Panel to display code complexity analysis results.
 */

import { useEditorStore } from '../store/editorStore';

export function ComplexityPanel() {
  const { analysis, isAnalyzing } = useEditorStore();

  if (isAnalyzing) {
    return (
      <div className="complexity-panel">
        <div className="complexity-header">
          <span className="complexity-title">Complexity Analysis</span>
          <span className="complexity-status analyzing">Analyzing...</span>
        </div>
        <div className="complexity-content">
          <div className="loading-spinner">🔍 Analyzing code complexity...</div>
        </div>
      </div>
    );
  }

  if (!analysis) {
    return null;
  }

  if (!analysis.available) {
    return (
      <div className="complexity-panel">
        <div className="complexity-header">
          <span className="complexity-title">Complexity Analysis</span>
          <span className="complexity-status unavailable">Unavailable</span>
        </div>
        <div className="complexity-content">
          <p className="unavailable-message">
            LLM analysis is not configured. Set GEMINI_API_KEY to enable.
          </p>
        </div>
      </div>
    );
  }

  if (analysis.error) {
    return (
      <div className="complexity-panel">
        <div className="complexity-header">
          <span className="complexity-title">Complexity Analysis</span>
          <span className="complexity-status error">Error</span>
        </div>
        <div className="complexity-content">
          <p className="error-message">{analysis.error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="complexity-panel">
      <div className="complexity-header">
        <span className="complexity-title">Complexity Analysis</span>
        <span className="complexity-status success">✓ Analyzed</span>
      </div>

      <div className="complexity-content">
        {/* Complexity badges */}
        <div className="complexity-badges">
          <div className="complexity-badge time">
            <span className="badge-label">Time</span>
            <span className="badge-value">{analysis.time_complexity}</span>
          </div>
          <div className="complexity-badge space">
            <span className="badge-label">Space</span>
            <span className="badge-value">{analysis.space_complexity}</span>
          </div>
        </div>

        {/* Explanations */}
        <div className="complexity-explanations">
          <div className="explanation">
            <strong>Time:</strong> {analysis.time_explanation}
          </div>
          <div className="explanation">
            <strong>Space:</strong> {analysis.space_explanation}
          </div>
        </div>

        {/* Algorithm identified */}
        {analysis.algorithm_identified && (
          <div className="algorithm-identified">
            <strong>Algorithm:</strong> {analysis.algorithm_identified}
          </div>
        )}

        {/* Suggestions */}
        {analysis.suggestions && analysis.suggestions.length > 0 && (
          <div className="suggestions">
            <strong>Suggestions:</strong>
            <ul>
              {analysis.suggestions.map((suggestion, index) => (
                <li key={index}>{suggestion}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
