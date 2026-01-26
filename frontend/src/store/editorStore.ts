/**
 * Zustand store for editor state management.
 */

import { create } from 'zustand';
import type { ExecutionResponse } from '../types/execution';

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

  // Error state (for API errors, not execution errors)
  apiError: string | null;
  setApiError: (error: string | null) => void;

  // Timeout setting
  timeoutSeconds: number;
  setTimeoutSeconds: (timeout: number) => void;

  // Reset
  reset: () => void;
}

export const useEditorStore = create<EditorState>((set) => ({
  code: DEFAULT_CODE,
  setCode: (code) => set({ code }),

  isExecuting: false,
  setIsExecuting: (isExecuting) => set({ isExecuting }),

  result: null,
  setResult: (result) => set({ result }),

  apiError: null,
  setApiError: (apiError) => set({ apiError }),

  timeoutSeconds: 30,
  setTimeoutSeconds: (timeoutSeconds) => set({ timeoutSeconds }),

  reset: () =>
    set({
      code: DEFAULT_CODE,
      isExecuting: false,
      result: null,
      apiError: null,
      timeoutSeconds: 30,
    }),
}));
