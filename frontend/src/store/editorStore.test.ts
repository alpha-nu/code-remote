/**
 * Unit tests for the editor store.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { useEditorStore } from './editorStore';

describe('useEditorStore', () => {
  beforeEach(() => {
    // Reset store to initial state before each test
    useEditorStore.getState().reset();
  });

  describe('code state', () => {
    it('should have default code', () => {
      const { code } = useEditorStore.getState();
      expect(code).toContain('factorial');
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
      const mockAnalysis = {
        success: true,
        time_complexity: 'O(n)',
        space_complexity: 'O(1)',
        time_explanation: 'Linear iteration',
        space_explanation: 'Constant space',
        algorithm_identified: null,
        suggestions: null,
        error: null,
        available: true,
      };
      setAnalysis(mockAnalysis);
      expect(useEditorStore.getState().analysis).toEqual(mockAnalysis);
    });

    it('should have initial autoAnalyze as true', () => {
      const { autoAnalyze } = useEditorStore.getState();
      expect(autoAnalyze).toBe(true);
    });

    it('should toggle autoAnalyze', () => {
      const { setAutoAnalyze } = useEditorStore.getState();
      setAutoAnalyze(false);
      expect(useEditorStore.getState().autoAnalyze).toBe(false);
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

      // Reset
      store.reset();

      // Verify reset
      const resetState = useEditorStore.getState();
      expect(resetState.code).toContain('factorial');
      expect(resetState.isExecuting).toBe(false);
      expect(resetState.result).toBeNull();
      expect(resetState.apiError).toBeNull();
    });
  });
});
