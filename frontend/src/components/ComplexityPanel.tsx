/**
 * Panel to display code complexity analysis results.
 *
 * Supports two modes:
 * - Streaming: renders Markdown narrative with a typewriter reveal effect
 * - Complete: shows complexity badges + full Markdown narrative
 */

import { useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { useEditorStore } from '../store/editorStore';
import { useTypewriter } from '../hooks';
import type { ConnectionState } from '../hooks';
import spinner from '../assets/spinner.svg';

interface ComplexityPanelProps {
  /** Current WebSocket connection state — drives the connection indicator. */
  connectionState?: ConnectionState;
}

/**
 * Strip the trailing ```json {...} ``` block from the narrative
 * so it's not visible to the user during streaming.
 */
function stripJsonBlock(text: string): string {
  const lastFenceStart = text.lastIndexOf('```json');
  if (lastFenceStart !== -1) {
    return text.slice(0, lastFenceStart).trimEnd();
  }
  return text;
}

/** Small connection-mode pill shown in the panel header. */
function ConnectionIndicator({ state }: { state: ConnectionState }) {
  const isWs = state === 'connected';
  return (
    <span
      className={`analysis-conn-indicator ${isWs ? 'ws' : 'http'}`}
      title={isWs ? 'Streaming via WebSocket' : 'Sync HTTP request'}
    >
      <span className="analysis-conn-dot" />
      {isWs ? 'WebSocket' : 'HTTP'}
    </span>
  );
}

export function ComplexityPanel({ connectionState = 'disconnected' }: ComplexityPanelProps) {
  const { analysis, isAnalyzing, analysisStreamText, setAnalysisStreamText } = useEditorStore();

  // Typewriter: progressively reveal the raw stream text.
  // analysisStreamText stays populated after streaming until the typewriter catches up.
  const revealedRaw = useTypewriter(analysisStreamText, { charsPerTick: 2, intervalMs: 14 });
  const displayText = stripJsonBlock(revealedRaw);

  // Typewriter is done when it has revealed all visible (non-JSON) text
  const strippedTarget = stripJsonBlock(analysisStreamText);
  const typewriterDone = !analysisStreamText || displayText.length >= strippedTarget.length;

  // Show typewriter while streaming or while it's still catching up
  const showTypewriter = !!analysisStreamText && (!typewriterDone || isAnalyzing);

  // Clear stream text once the typewriter finishes (Zustand store, not React state)
  useEffect(() => {
    if (typewriterDone && !isAnalyzing && analysisStreamText) {
      setAnalysisStreamText('');
    }
  }, [typewriterDone, isAnalyzing, analysisStreamText, setAnalysisStreamText]);

  // --- Auto-scroll ---
  const panelRef = useRef<HTMLDivElement>(null);
  const prevShowTypewriterRef = useRef(false);

  // During typewriter: pin scroll to bottom (instant, no jitter)
  useEffect(() => {
    if (showTypewriter && panelRef.current) {
      panelRef.current.scrollTop = panelRef.current.scrollHeight;
    }
  }, [showTypewriter, displayText]);

  // When typewriter finishes → smooth scroll to top
  useEffect(() => {
    if (prevShowTypewriterRef.current && !showTypewriter) {
      const timer = setTimeout(() => {
        panelRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
      }, 200);
      return () => clearTimeout(timer);
    }
    prevShowTypewriterRef.current = showTypewriter;
  }, [showTypewriter]);

  // Header with connection indicator aligned right
  const renderHeader = (statusEl: React.ReactNode) => (
    <div className="complexity-header">
      <span className="complexity-title">Complexity Analysis</span>
      {statusEl}
      <span className="complexity-header-spacer" />
      <ConnectionIndicator state={connectionState} />
    </div>
  );

  // Streaming or typewriter still catching up — show typewriter Markdown
  if (showTypewriter) {
    return (
      <div className="complexity-panel" ref={panelRef}>
        {renderHeader(
          <span className="complexity-status analyzing">Analyzing...</span>
        )}
        <div className="complexity-content complexity-narrative streaming-content">
          <ReactMarkdown
            remarkPlugins={[remarkMath]}
            rehypePlugins={[rehypeKatex]}
          >
            {displayText || '\u200B'}
          </ReactMarkdown>
          <span className="streaming-cursor" />
        </div>
      </div>
    );
  }

  // Analyzing but no chunks yet — simple spinner
  if (isAnalyzing) {
    return (
      <div className="complexity-panel">
        {renderHeader(
          <span className="complexity-status analyzing">Analyzing...</span>
        )}
        <div className="complexity-content">
          <div className="loading-spinner">
            <img src={spinner} className="spinner-logo small" alt="analyzing" /> Analyzing code complexity...
          </div>
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
        {renderHeader(
          <span className="complexity-status unavailable">Unavailable</span>
        )}
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
        {renderHeader(
          <span className="complexity-status error">Error</span>
        )}
        <div className="complexity-content">
          <p className="error-message">{analysis.error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="complexity-panel" ref={panelRef}>
      {renderHeader(
        <span className="complexity-status success">✓ Analyzed</span>
      )}

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

        {/* Markdown narrative */}
        {analysis.narrative && (
          <div className="complexity-narrative">
            <ReactMarkdown
              remarkPlugins={[remarkMath]}
              rehypePlugins={[rehypeKatex]}
            >
              {analysis.narrative}
            </ReactMarkdown>
          </div>
        )}

        {/* Model attribution */}
        {analysis.model && (
          <div className="model-attribution">
            Analyzed by <span className="model-name">{analysis.model}</span>
          </div>
        )}
      </div>
    </div>
  );
}
