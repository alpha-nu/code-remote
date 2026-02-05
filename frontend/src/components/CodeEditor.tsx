/**
 * Monaco Editor component for Python code editing.
 */

import Editor from '@monaco-editor/react';
import { useEffect, useState } from 'react';
import { useEditorStore } from '../store/editorStore';
import { useSnippetsStore } from '../store/snippetsStore';
import { useAutoSave } from '../hooks/useAutoSave';
import spinner from '../assets/spinner.svg';
import type { ConnectionState } from '../hooks/useWebSocket';

interface CodeEditorProps {
  connectionState?: ConnectionState;
}

export function CodeEditor({ connectionState = 'disconnected' }: CodeEditorProps) {
  const { code, setCode, isExecuting, result } = useEditorStore();
  const { loadedSnippetId, loadedSnippetTitle, loadedSnippetCode, clearLoadedSnippet } = useSnippetsStore();
  const { saveSnippet } = useAutoSave();
  const [theme, setTheme] = useState(() =>
    document.documentElement.classList.contains('light-theme') ? 'light' : 'vs-dark',
  );

  useEffect(() => {
    const onTheme = () => {
      setTheme(document.documentElement.classList.contains('light-theme') ? 'light' : 'vs-dark');
    };
    window.addEventListener('themechange', onTheme);
    window.addEventListener('storage', onTheme);
    return () => {
      window.removeEventListener('themechange', onTheme);
      window.removeEventListener('storage', onTheme);
    };
  }, []);

  // Auto-save on successful execution
  useEffect(() => {
    if (result && result.success && loadedSnippetId) {
      saveSnippet();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result]);

  const getConnectionLabel = () => {
    switch (connectionState) {
      case 'connected':
        return 'WebSocket';
      case 'connecting':
        return 'Connecting';
      default:
        return 'HTTP';
    }
  };

  const getConnectionTitle = () => {
    switch (connectionState) {
      case 'connected':
        return 'Real-time connection via WebSocket';
      case 'connecting':
        return 'Establishing WebSocket connection...';
      default:
        return 'Using HTTP requests (WebSocket unavailable)';
    }
  };

  const hasChanges = loadedSnippetId && loadedSnippetCode !== null && code !== loadedSnippetCode;

  return (
    <div className="editor-container">
      <span className="keyboard-hint editor-hint">command pallete F1</span>
      <Editor
        height="100%"
        defaultLanguage="python"
        theme={theme}
        value={code}
        onChange={(value) => setCode(value || '')}
        options={{
          minimap: { enabled: false },
          fontSize: 14,
          lineNumbers: 'on',
          roundedSelection: false,
          scrollBeyondLastLine: false,
          readOnly: isExecuting,
          automaticLayout: true,
          tabSize: 4,
          insertSpaces: true,
          wordWrap: 'on',
          folding: true,
          lineDecorationsWidth: 10,
          lineNumbersMinChars: 3,
        }}
        loading={<div className="editor-loading"><img src={spinner} className="spinner-logo" alt="loading" /> Loading editor...</div>}
      />
      <div className="editor-status-bar">
        <div className="status-bar-left">
          {loadedSnippetId && (
            <span
              className={`status-item snippet-status ${hasChanges ? 'modified' : 'saved'}`}
              title={hasChanges ? 'Snippet has unsaved changes' : 'Snippet saved'}
            >
              <span className="status-dot" />
              {loadedSnippetTitle || 'Untitled'}
              <button
                className="snippet-eject-btn"
                onClick={clearLoadedSnippet}
                title="Eject snippet (keep code in editor)"
              >
                ⏏
              </button>
            </span>
          )}
        </div>
        <div className="status-bar-right">
          <span className="status-item">Python</span>
          <span className="status-item">UTF-8</span>
          <span
            className={`status-item connection-indicator ${connectionState}`}
            title={getConnectionTitle()}
          >
            <span className="status-dot" />
            {getConnectionLabel()}
          </span>
        </div>
      </div>
    </div>
  );
}
