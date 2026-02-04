/**
 * SnippetStatusBar - Shows loaded snippet and save button
 */

import { useState, useEffect } from 'react';
import { useUpdateSnippet } from '../hooks/useSnippets';
import { useEditorStore } from '../store/editorStore';
import './SnippetStatusBar.css';

interface SnippetStatusBarProps {
  loadedSnippetId: string | null;
  loadedSnippetTitle: string | null;
  originalCode: string | null;
  onSaved?: () => void;
}

export function SnippetStatusBar({
  loadedSnippetId,
  loadedSnippetTitle,
  originalCode,
  onSaved
}: SnippetStatusBarProps) {
  const { code } = useEditorStore();
  const updateSnippet = useUpdateSnippet();
  const [isSaving, setIsSaving] = useState(false);

  // Track if code has changed from original
  const hasChanges = loadedSnippetId && originalCode !== null && code !== originalCode;

  useEffect(() => {
    // Auto-save indicator could be added here later
  }, [code, originalCode]);

  if (!loadedSnippetId) {
    return null; // Don't show bar when no snippet loaded
  }

  const handleSave = async () => {
    if (!loadedSnippetId || !hasChanges) return;

    setIsSaving(true);
    try {
      await updateSnippet.mutateAsync({
        id: loadedSnippetId,
        data: { code },
      });
      onSaved?.();
    } catch (error) {
      console.error('Failed to save snippet:', error);
      alert('Failed to save snippet. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="snippet-status-bar">
      <div className="snippet-status-info">
        <span className="snippet-status-icon">📄</span>
        <span className="snippet-status-title">{loadedSnippetTitle || 'Untitled'}</span>
        {hasChanges && <span className="snippet-status-badge modified">Modified</span>}
        {!hasChanges && <span className="snippet-status-badge saved">Saved</span>}
      </div>
      {hasChanges && (
        <button
          className="snippet-save-btn"
          onClick={handleSave}
          disabled={isSaving}
          title="Save changes to snippet"
        >
          {isSaving ? 'Saving...' : 'Save'}
        </button>
      )}
    </div>
  );
}
