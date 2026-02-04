/**
 * Zustand store for snippets UI state
 */

import { create } from 'zustand';

interface SnippetsState {
  loadedSnippetId: string | null;
  loadedSnippetTitle: string | null;
  loadedSnippetCode: string | null;

  setLoadedSnippet: (id: string, title: string, code: string) => void;
  clearLoadedSnippet: () => void;
  updateLoadedCode: (code: string) => void;
}

export const useSnippetsStore = create<SnippetsState>((set) => ({
  loadedSnippetId: null,
  loadedSnippetTitle: null,
  loadedSnippetCode: null,

  setLoadedSnippet: (id, title, code) => set({
    loadedSnippetId: id,
    loadedSnippetTitle: title,
    loadedSnippetCode: code,
  }),

  clearLoadedSnippet: () => set({
    loadedSnippetId: null,
    loadedSnippetTitle: null,
    loadedSnippetCode: null,
  }),

  updateLoadedCode: (code) => set({ loadedSnippetCode: code }),
}));
