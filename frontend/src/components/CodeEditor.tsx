/**
 * Monaco Editor component for Python code editing.
 */

import Editor from '@monaco-editor/react';
import { useEffect, useState } from 'react';
import { useEditorStore } from '../store/editorStore';
import pythonLogo from '../assets/python-logo.svg';

export function CodeEditor() {
  const { code, setCode, isExecuting } = useEditorStore();
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
        loading={<div className="editor-loading"><img src={pythonLogo} className="spinner-logo" alt="loading" /> Loading editor...</div>}
      />
    </div>
  );
}
