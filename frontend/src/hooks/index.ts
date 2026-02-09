/**
 * Custom React hooks for the application.
 */

export { useAutoSave } from './useAutoSave';
export { useWebSocket } from './useWebSocket';
export type {
  ConnectionState,
  WebSocketMessage,
  ExecutionResultMessage,
} from './useWebSocket';

export { useExecution } from './useExecution';
export type { ExecutionMode, JobStatus } from './useExecution';

export { useTypewriter } from './useTypewriter';
