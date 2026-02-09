/**
 * Unit tests for the editor store.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
// Mock the client module so tests can stub analyzeCode / analyzeCodeAsync at runtime
vi.mock('../api/client', () => ({
  analyzeCode: vi.fn(),
  analyzeCodeAsync: vi.fn(),
}));
import type { AnalyzeResponse } from '../types/execution';
import { useEditorStore } from './editorStore';

/** Helper to build a mock AnalyzeResponse with sane defaults. */
function mockAnalyzeResponse(overrides: Partial<AnalyzeResponse> = {}): AnalyzeResponse {
  return {
    success: true,
    time_complexity: 'O(n)',
    space_complexity: 'O(1)',
    narrative: '### Algorithm\nLinear scan.',
    error: null,
    available: true,
    model: 'gemini-2.0-flash',
    ...overrides,
  };
}

describe('useEditorStore', () => {
  beforeEach(() => {
    // Reset store to initial state before each test
    useEditorStore.getState().reset();
  });

  describe('code state', () => {
    it('should have default code', () => {
      const { code } = useEditorStore.getState();
      expect(code).toContain('CODE REMOTE');
    });

    it('should update code', () => {
      const { setCode } = useEditorStore.getState();
      setCode('print("hello")');
      expect(useEditorStore.getState().code).toBe('print("hello")');
    });
  });

  describe('execution state', () => {
    it('should have initial isExecuting as false', () => {
      const { isExecuting } = useEditorStore.getState();
      expect(isExecuting).toBe(false);
    });

    it('should update isExecuting', () => {
      const { setIsExecuting } = useEditorStore.getState();
      setIsExecuting(true);
      expect(useEditorStore.getState().isExecuting).toBe(true);
    });

    it('should have initial result as null', () => {
      const { result } = useEditorStore.getState();
      expect(result).toBeNull();
    });

    it('should update result', () => {
      const { setResult } = useEditorStore.getState();
      const mockResult = {
        success: true,
        stdout: 'hello',
        stderr: '',
        error: null,
        error_type: null,
        execution_time_ms: 10,
        timed_out: false,
        security_violations: [],
      };
      setResult(mockResult);
      expect(useEditorStore.getState().result).toEqual(mockResult);
    });
  });

  describe('analysis state', () => {
    it('should have initial isAnalyzing as false', () => {
      const { isAnalyzing } = useEditorStore.getState();
      expect(isAnalyzing).toBe(false);
    });

    it('should have initial analysis as null', () => {
      const { analysis } = useEditorStore.getState();
      expect(analysis).toBeNull();
    });

    it('should update analysis', () => {
      const { setAnalysis } = useEditorStore.getState();
      const mockAnalysis = mockAnalyzeResponse();
      setAnalysis(mockAnalysis);
      expect(useEditorStore.getState().analysis).toEqual(mockAnalysis);
    });

    it('should have initial autoAnalyze as false', () => {
      const { autoAnalyze } = useEditorStore.getState();
      expect(autoAnalyze).toBe(false);
    });

    it('should toggle autoAnalyze', () => {
      const { setAutoAnalyze } = useEditorStore.getState();
      setAutoAnalyze(false);
      expect(useEditorStore.getState().autoAnalyze).toBe(false);
    });
  });

  describe('analysis streaming state', () => {
    it('should have initial analysisStreamText as empty string', () => {
      const { analysisStreamText } = useEditorStore.getState();
      expect(analysisStreamText).toBe('');
    });

    it('should have initial analysisJobId as null', () => {
      const { analysisJobId } = useEditorStore.getState();
      expect(analysisJobId).toBeNull();
    });

    it('should append stream chunks', () => {
      const store = useEditorStore.getState();
      store.appendAnalysisStreamChunk('### Algorithm\n');
      expect(useEditorStore.getState().analysisStreamText).toBe('### Algorithm\n');
      store.appendAnalysisStreamChunk('Linear scan.');
      expect(useEditorStore.getState().analysisStreamText).toBe('### Algorithm\nLinear scan.');
    });

    it('should reset streaming state on reset()', () => {
      const store = useEditorStore.getState();
      store.appendAnalysisStreamChunk('partial data');
      store.reset();
      expect(useEditorStore.getState().analysisStreamText).toBe('');
      expect(useEditorStore.getState().analysisJobId).toBeNull();
    });
  });

  describe('error state', () => {
    it('should have initial apiError as null', () => {
      const { apiError } = useEditorStore.getState();
      expect(apiError).toBeNull();
    });

    it('should update apiError', () => {
      const { setApiError } = useEditorStore.getState();
      setApiError('Network error');
      expect(useEditorStore.getState().apiError).toBe('Network error');
    });
  });

  describe('timeout state', () => {
    it('should have default timeout of 30 seconds', () => {
      const { timeoutSeconds } = useEditorStore.getState();
      expect(timeoutSeconds).toBe(30);
    });

    it('should update timeout', () => {
      const { setTimeoutSeconds } = useEditorStore.getState();
      setTimeoutSeconds(10);
      expect(useEditorStore.getState().timeoutSeconds).toBe(10);
    });
  });

  describe('reset', () => {
    it('should reset all state to initial values', () => {
      const store = useEditorStore.getState();

      // Modify state
      store.setCode('modified code');
      store.setIsExecuting(true);
      store.setResult({
        success: true,
        stdout: 'test',
        stderr: '',
        error: null,
        error_type: null,
        execution_time_ms: 1,
        timed_out: false,
        security_violations: [],
      });
      store.setApiError('error');
      store.appendAnalysisStreamChunk('partial');

      // Reset
      store.reset();

      // Verify reset
      const resetState = useEditorStore.getState();
      expect(resetState.code).toContain('CODE REMOTE');
      expect(resetState.isExecuting).toBe(false);
      expect(resetState.result).toBeNull();
      expect(resetState.apiError).toBeNull();
      expect(resetState.analysisStreamText).toBe('');
      expect(resetState.analysisJobId).toBeNull();
    });
  });

  describe('analysis lifecycle', () => {
    it('clears analysis when code changes from last analyzed value', () => {
      const store = useEditorStore.getState();
      const mockAnalysisObj = mockAnalyzeResponse();

      store.setAnalysis(mockAnalysisObj);
      store.setLastAnalyzedCode('original');

      // Change to same code -> keep analysis
      store.setCode('original');
      expect(useEditorStore.getState().analysis).not.toBeNull();

      // Change to different code -> analysis should be cleared
      store.setCode('modified');
      expect(useEditorStore.getState().analysis).toBeNull();
    });

    it('analyze() calls analyzeCode and sets lastAnalyzedCode', async () => {
      const mockAnalysis = mockAnalyzeResponse();

      // Dynamically mock the module used by the store's analyze() (../api/client)
      const clientModule = await import('../api/client');
      // Replace analyzeCode mock implementation
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (clientModule as any).analyzeCode.mockResolvedValue(mockAnalysis);

      const store = useEditorStore.getState();
      store.setCode('code-to-analyze');

      await store.analyze();

      expect(useEditorStore.getState().analysis).toEqual(mockAnalysis);
      expect(useEditorStore.getState().lastAnalyzedCode).toBe('code-to-analyze');
    });
  });
});
