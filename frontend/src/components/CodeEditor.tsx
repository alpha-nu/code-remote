/**
 * Monaco Editor component for Python code editing.
 */

import Editor from '@monaco-editor/react';
import { useEditorStore } from '../store/editorStore';

export function CodeEditor() {
  const { code, setCode, isExecuting } = useEditorStore();

  return (
    <div className="editor-container">
      <Editor
        height="100%"
        defaultLanguage="python"
        theme="vs-dark"
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
        loading={<div className="editor-loading">Loading editor...</div>}
      />
    </div>
  );
}
