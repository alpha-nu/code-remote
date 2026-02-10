/**
 * Zustand store for editor state management.
 */

import { create } from 'zustand';
import type { AnalyzeResponse, ExecutionResponse } from '../types/execution';
import type { Snippet, SnippetSummary } from '../types/api';

interface SnippetListResponse {
  items: SnippetSummary[];
  total: number;
  limit: number;
  offset: number;
}

const DEFAULT_CODE = `# Welcome to Code Remote! 🚀

def welcome():
    features = [
        "⚡ Execute Python code instantly",
        "🧠 Analyze complexity with AI",
        "💾 Save snippets for later",
        "🔍 Search your code library"
    ]

    print("=" * 45)
    print(" " * 10 + "CODE REMOTE")
    print("=" * 45)

    for feature in features:
        print(f"  {feature}")

    print("=" * 45)
    print("\\n👈 Check out the sidebar for saved snippets")
    print("⬆️  Hit Execute to run this code")
    print("🔬 Click Analyze for complexity insights\\n")

welcome()
`;

interface EditorState {
  // Code editor state
  code: string;
  setCode: (code: string) => void;

  // Execution state
  isExecuting: boolean;
  setIsExecuting: (isExecuting: boolean) => void;

  // Result state
  result: ExecutionResponse | null;
  setResult: (result: ExecutionResponse | null) => void;

  // Analysis state
  isAnalyzing: boolean;
  setIsAnalyzing: (isAnalyzing: boolean) => void;

  analysis: AnalyzeResponse | null;
  setAnalysis: (analysis: AnalyzeResponse | null) => void;

  // Streaming analysis state
  analysisStreamText: string;
  setAnalysisStreamText: (text: string) => void;
  appendAnalysisStreamChunk: (chunk: string) => void;
  analysisJobId: string | null;
  setAnalysisJobId: (jobId: string | null) => void;

  // Track last analyzed code to know when analysis is stale
  lastAnalyzedCode: string | null;
  setLastAnalyzedCode: (code: string | null) => void;

  // Convenience: analyze current code (calls API)
  analyze: (connectionId?: string | null) => Promise<void>;
  /** Cancel an in-progress analysis (streaming or sync). */
  cancelAnalysis: () => void;
  autoAnalyze: boolean;
  setAutoAnalyze: (autoAnalyze: boolean) => void;

  // Error state (for API errors, not execution errors)
  apiError: string | null;
  setApiError: (error: string | null) => void;

  // Timeout setting
  timeoutSeconds: number;
  setTimeoutSeconds: (timeout: number) => void;

  // Track whether code has been executed at least once
  hasRun: boolean;
  setHasRun: (hasRun: boolean) => void;

  // Reset
  reset: () => void;
}

export const useEditorStore = create<EditorState>((set) => ({
  code: DEFAULT_CODE,
  setCode: (code) =>
    set((state) => ({
      code,
      // clear analysis when the new code differs from the last analyzed code
      analysis: state.lastAnalyzedCode && state.lastAnalyzedCode !== code ? null : state.analysis,
    })),

  isExecuting: false,
  setIsExecuting: (isExecuting) => set({ isExecuting }),

  result: null,
  setResult: (result) => set({
    result,
    // mark that code has been executed at least once when a non-null result is set
    ...(result ? { hasRun: true } : {}),
  }),

  isAnalyzing: false,
  setIsAnalyzing: (isAnalyzing) => set({ isAnalyzing }),

  analysis: null,
  setAnalysis: (analysis) => set({ analysis }),

  // Streaming analysis state
  analysisStreamText: '',
  setAnalysisStreamText: (text) => set({ analysisStreamText: text }),
  appendAnalysisStreamChunk: (chunk) =>
    set((state) => ({ analysisStreamText: state.analysisStreamText + chunk })),
  analysisJobId: null,
  setAnalysisJobId: (jobId) => set({ analysisJobId: jobId }),

  lastAnalyzedCode: null,
  setLastAnalyzedCode: (code) => set({ lastAnalyzedCode: code }),

  // Track whether code has been executed at least once
  hasRun: false,
  setHasRun: (hasRun: boolean) => set({ hasRun }),

  analyze: async (connectionId?: string | null) => {
    const { analyzeCode, analyzeCodeAsync } = await import('../api/client');
    const { useSnippetsStore } = await import('./snippetsStore');
    set({ isAnalyzing: true, analysis: null, analysisStreamText: '', analysisJobId: null });
    try {
      const code = useEditorStore.getState().code;
      const snippetId = useSnippetsStore.getState().loadedSnippetId;

      if (connectionId) {
        // Async streaming via WebSocket
        const response = await analyzeCodeAsync({
          code,
          connection_id: connectionId,
          snippet_id: snippetId ?? undefined,
        });
        set({ analysisJobId: response.job_id, lastAnalyzedCode: code });
        // Result will arrive via WebSocket messages — handled by Toolbar
      } else {
        // Sync HTTP fallback
        const analysis = await analyzeCode({
          code,
          snippet_id: snippetId ?? undefined,
        });
        set({ analysis, lastAnalyzedCode: code, isAnalyzing: false });
        updateSnippetCachesAfterAnalysis(analysis);
      }
    } catch {
      set({ isAnalyzing: false });
    }
  },

  cancelAnalysis: () =>
    set({ isAnalyzing: false, analysisJobId: null, analysisStreamText: '' }),

  autoAnalyze: false,
  setAutoAnalyze: (autoAnalyze) => set({ autoAnalyze }),

  apiError: null,
  setApiError: (apiError) => set({ apiError }),

  timeoutSeconds: 30,
  setTimeoutSeconds: (timeoutSeconds) => set({ timeoutSeconds }),

  reset: () =>
    set({
      code: DEFAULT_CODE,
      isExecuting: false,
      result: null,
      isAnalyzing: false,
      analysis: null,
      analysisStreamText: '',
      analysisJobId: null,
      lastAnalyzedCode: null,
      autoAnalyze: false,
      apiError: null,
      timeoutSeconds: 30,
      hasRun: false,
    }),
}));

/**
 * Update snippet caches after a successful analysis.
 * Exported so the streaming WS handler can call it on stream complete.
 */
export async function updateSnippetCachesAfterAnalysis(analysis: AnalyzeResponse) {
  const { useSnippetsStore } = await import('./snippetsStore');
  const { queryClient } = await import('../utils/queryClient');
  const snippetId = useSnippetsStore.getState().loadedSnippetId;

  if (snippetId && analysis.success) {
    queryClient.setQueryData<Snippet>(
      ['snippet', snippetId],
      (old) => old ? {
        ...old,
        timeComplexity: analysis.time_complexity,
        spaceComplexity: analysis.space_complexity,
      } : old
    );

    queryClient.setQueriesData<SnippetListResponse>(
      { queryKey: ['snippets'] },
      (old) => {
        if (!old?.items) return old;
        return {
          ...old,
          items: old.items.map((snippet) =>
            snippet.id === snippetId
              ? {
                  ...snippet,
                  timeComplexity: analysis.time_complexity,
                  spaceComplexity: analysis.space_complexity,
                }
              : snippet
          ),
        };
      }
    );

    await queryClient.invalidateQueries({ queryKey: ['search'] });
    await queryClient.invalidateQueries({ queryKey: ['complexity'] });
  }
}
