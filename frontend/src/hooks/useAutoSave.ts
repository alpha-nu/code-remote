/**
 * Auto-save hook for snippets
 * Saves on:
 * 1. Successful code execution (no errors)
 * 2. Periodic interval (configurable via env)
 */

import { useEffect, useRef, useCallback } from 'react';
import { useUpdateSnippet } from './useSnippets';
import { useSnippetsStore } from '../store/snippetsStore';
import { useEditorStore } from '../store/editorStore';

const AUTO_SAVE_INTERVAL = parseInt(import.meta.env.VITE_SNIPPET_AUTOSAVE_INTERVAL || '30') * 1000;

export function useAutoSave() {
  const { code } = useEditorStore();
  const { loadedSnippetId, loadedSnippetCode, updateLoadedCode } = useSnippetsStore();
  const updateSnippet = useUpdateSnippet();
  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const isSavingRef = useRef(false);

  const hasChanges = loadedSnippetId && loadedSnippetCode !== null && code !== loadedSnippetCode;

  const saveSnippet = useCallback(async () => {
    if (!loadedSnippetId || !hasChanges || isSavingRef.current) {
      return;
    }

    isSavingRef.current = true;
    try {
      await updateSnippet.mutateAsync({
        id: loadedSnippetId,
        data: { code },
      });
      updateLoadedCode(code);
    } catch (error) {
      console.error('Auto-save failed:', error);
    } finally {
      isSavingRef.current = false;
    }
  }, [loadedSnippetId, hasChanges, code, updateSnippet, updateLoadedCode]);

  // Periodic auto-save
  useEffect(() => {
    if (!hasChanges) {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
        saveTimeoutRef.current = null;
      }
      return;
    }

    // Clear existing timeout
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }

    // Set new timeout
    saveTimeoutRef.current = setTimeout(() => {
      saveSnippet();
    }, AUTO_SAVE_INTERVAL);

    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
    };
  }, [code, hasChanges, loadedSnippetId, saveSnippet]);

  return {
    saveSnippet,
    hasChanges,
    isSaving: isSavingRef.current,
  };
}
