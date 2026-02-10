/**
 * WebSocket connection management hook for real-time updates.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useAuthStore } from '../store/authStore';

const WS_URL = import.meta.env.VITE_WEBSOCKET_URL || 'ws://localhost:8000/ws';

/** WebSocket connection states */
export type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'error';

/** Message received from WebSocket */
export interface WebSocketMessage {
  type: string;
  [key: string]: unknown;
}

/** Execution result received via WebSocket */
export interface ExecutionResultMessage {
  type: 'execution_result';
  job_id: string;
  success: boolean;
  stdout: string;
  stderr: string;
  error: string | null;
  error_type: string | null;
  execution_time_ms: number;
  timed_out: boolean;
  security_violations: Array<{ line: number; column: number; message: string }>;
}

interface UseWebSocketOptions {
  /** Whether to automatically connect on mount. Default: true */
  autoConnect?: boolean;
  /** Reconnection delay in ms. Default: 3000 */
  reconnectDelay?: number;
  /** Maximum reconnection attempts. Default: 5 */
  maxReconnectAttempts?: number;
}

interface UseWebSocketReturn {
  /** Current connection state */
  connectionState: ConnectionState;
  /** Connection ID returned by the server (needed for async execution) */
  connectionId: string | null;
  /** Error message if connection failed */
  error: string | null;
  /** Manually connect to WebSocket */
  connect: () => void;
  /** Manually disconnect from WebSocket */
  disconnect: () => void;
  /** Add a message handler */
  addMessageHandler: (handler: (message: WebSocketMessage) => void) => () => void;
}

/**
 * Hook for managing WebSocket connection to the backend.
 *
 * Provides:
 * - Automatic connection on mount (optional)
 * - Automatic reconnection on disconnect
 * - Connection ID tracking for async execution
 * - Message handler registration
 */
export function useWebSocket(options: UseWebSocketOptions = {}): UseWebSocketReturn {
  const {
    autoConnect = true,
    reconnectDelay = 3000,
    maxReconnectAttempts = 5,
  } = options;

  const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected');
  const [connectionId, setConnectionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const messageHandlersRef = useRef<Set<(message: WebSocketMessage) => void>>(new Set());
  const isManualDisconnectRef = useRef(false);
  const connectFnRef = useRef<(() => void) | null>(null);
  const disconnectFnRef = useRef<(() => void) | null>(null);

  const { isAuthenticated } = useAuthStore();

  /**
   * Connect to WebSocket server.
   */
  const connect = useCallback(() => {
    // Don't connect if not authenticated
    if (!isAuthenticated) {
      setError('Must be authenticated to connect');
      setConnectionState('error');
      return;
    }

    // Don't connect if already connected or connecting
    if (wsRef.current?.readyState === WebSocket.OPEN ||
        wsRef.current?.readyState === WebSocket.CONNECTING) {
      return;
    }

    isManualDisconnectRef.current = false;
    setConnectionState('connecting');
    setError(null);

    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnectionState('connected');
        reconnectAttemptsRef.current = 0;

        // Send a ping to get our connection ID
        ws.send(JSON.stringify({ action: 'ping' }));
      };

      ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);

          // Handle connection ID response
          if (message.type === 'pong' && typeof message.connection_id === 'string') {
            setConnectionId(message.connection_id);
          }

          // Notify all registered handlers
          messageHandlersRef.current.forEach((handler) => {
            try {
              handler(message);
            } catch (err) {
              console.error('Error in WebSocket message handler:', err);
            }
          });
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err);
        }
      };

      ws.onclose = (event) => {
        wsRef.current = null;
        setConnectionId(null);

        // Don't reconnect if manually disconnected
        if (isManualDisconnectRef.current) {
          setConnectionState('disconnected');
          return;
        }

        // Try to reconnect
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          setConnectionState('connecting');
          reconnectAttemptsRef.current += 1;
          reconnectTimeoutRef.current = window.setTimeout(() => {
            // Use ref to avoid stale closure
            connectFnRef.current?.();
          }, reconnectDelay);
        } else {
          setConnectionState('error');
          setError(`Connection closed: ${event.reason || 'Unknown reason'}`);
        }
      };

      ws.onerror = () => {
        setConnectionState('error');
        setError('WebSocket connection error');
      };
    } catch (err) {
      setConnectionState('error');
      setError(err instanceof Error ? err.message : 'Failed to connect');
    }
  }, [isAuthenticated, maxReconnectAttempts, reconnectDelay]);

  // Keep refs up to date
  useEffect(() => {
    connectFnRef.current = connect;
  }, [connect]);

  /**
   * Disconnect from WebSocket server.
   */
  const disconnect = useCallback(() => {
    isManualDisconnectRef.current = true;

    // Clear any pending reconnect timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setConnectionState('disconnected');
    setConnectionId(null);
    setError(null);
    reconnectAttemptsRef.current = 0;
  }, []);

  // Keep disconnect ref up to date
  useEffect(() => {
    disconnectFnRef.current = disconnect;
  }, [disconnect]);

  /**
   * Add a message handler. Returns cleanup function.
   */
  const addMessageHandler = useCallback(
    (handler: (message: WebSocketMessage) => void): (() => void) => {
      messageHandlersRef.current.add(handler);
      return () => {
        messageHandlersRef.current.delete(handler);
      };
    },
    []
  );

  // Auto-connect when authenticated
  useEffect(() => {
    if (autoConnect && isAuthenticated) {
      // Use timeout to defer connection, avoiding synchronous setState in effect
      const timeoutId = setTimeout(() => {
        connectFnRef.current?.();
      }, 0);
      return () => clearTimeout(timeoutId);
    }

    // Cleanup on unmount
    return () => {
      disconnectFnRef.current?.();
    };
  }, [autoConnect, isAuthenticated]);

  // Disconnect when logging out
  useEffect(() => {
    if (!isAuthenticated && connectionState !== 'disconnected') {
      // Use timeout to defer disconnection
      const timeoutId = setTimeout(() => {
        disconnectFnRef.current?.();
      }, 0);
      return () => clearTimeout(timeoutId);
    }
  }, [isAuthenticated, connectionState]);

  // --- Heartbeat: keep the connection alive and detect zombie sockets ---
  // AWS API Gateway has a 10-minute idle timeout.  Sending a ping every
  // 5 minutes resets that timer.  If the connection is silently dead,
  // the send() will eventually trigger onerror/onclose so we reconnect.
  useEffect(() => {
    if (connectionState !== 'connected') return;

    const HEARTBEAT_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes

    const interval = setInterval(() => {
      const ws = wsRef.current;
      if (ws?.readyState === WebSocket.OPEN) {
        try {
          ws.send(JSON.stringify({ action: 'ping' }));
        } catch {
          // send() failed — socket is dead; browser will fire onclose
        }
      }
    }, HEARTBEAT_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [connectionState]);

  return {
    connectionState,
    connectionId,
    error,
    connect,
    disconnect,
    addMessageHandler,
  };
}

export default useWebSocket;
