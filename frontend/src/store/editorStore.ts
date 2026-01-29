/**
 * Zustand store for editor state management.
 */

import { create } from 'zustand';
import type { AnalyzeResponse, ExecutionResponse } from '../types/execution';

const DEFAULT_CODE = `# Write your Python code here
# Example: Calculate factorial

def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

# Test the function
for i in range(1, 6):
    print(f"factorial({i}) = {factorial(i)}")
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

  // Track last analyzed code to know when analysis is stale
  lastAnalyzedCode: string | null;
  setLastAnalyzedCode: (code: string | null) => void;

  // Convenience: analyze current code (calls API)
  analyze: () => Promise<void>;
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

  lastAnalyzedCode: null,
  setLastAnalyzedCode: (code) => set({ lastAnalyzedCode: code }),

  // Track whether code has been executed at least once
  hasRun: false,
  setHasRun: (hasRun: boolean) => set({ hasRun }),

  analyze: async () => {
    const { analyzeCode } = await import('../api/client');
    set({ isAnalyzing: true, analysis: null });
    try {
      const code = useEditorStore.getState().code;
      const analysis = await analyzeCode({ code });
      set({ analysis, lastAnalyzedCode: code });
    } catch {
      // ignore analysis errors
    } finally {
      set({ isAnalyzing: false });
    }
  },

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
      autoAnalyze: false,
      apiError: null,
      timeoutSeconds: 30,
    }),
}));
