/**
 * useExecutionWebSocket.ts - WebSocket Hook for Real-time Execution Streaming
 *
 * Manages WebSocket connections to the backend's real-time execution streaming.
 * Handles connection lifecycle, message parsing, and automatic reconnection.
 *
 * Integration with backend: /ops/ws/execute/{script_id}
 */

import { useEffect, useRef, useCallback, useState } from 'react';
import { buildAuthenticatedWsUrl } from '@/lib/api';

export interface WSMessage {
  type: 'log_chunk' | 'status_update' | 'execution_complete' | 'execution_failed' | 'system_alert' | 'heartbeat';
  execution_id: string;
  timestamp: string;
  payload: Record<string, any>;
}

export interface ExecutionLog {
  type: 'stdout' | 'stderr' | 'status' | 'error' | 'warning';
  data: string;
  timestamp: string;
  stream?: 'stdout' | 'stderr';
}

interface UseExecutionWebSocketOptions {
  scriptId: string;
  userId?: string;
  onMessage?: (message: WSMessage) => void;
  onLog?: (log: ExecutionLog) => void;
  onStatusChange?: (status: string) => void;
  onComplete?: (exitCode: number, duration: number) => void;
  onError?: (error: string) => void;
  autoReconnect?: boolean;
  maxReconnectAttempts?: number;
}

const DEFAULT_RECONNECT_ATTEMPTS = 5;
const RECONNECT_DELAY_MS = 3000;

export const useExecutionWebSocket = ({
  scriptId,
  userId,
  onMessage,
  onLog,
  onStatusChange,
  onComplete,
  onError,
  autoReconnect = true,
  maxReconnectAttempts = DEFAULT_RECONNECT_ATTEMPTS,
}: UseExecutionWebSocketOptions) => {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCountRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      console.log('✓ WebSocket already connected');
      return;
    }

    setIsConnecting(true);

    try {
      const wsUrl = new URL(buildAuthenticatedWsUrl(`/api/v1/ops/ws/execute/${scriptId}`));
      
      if (userId) {
        wsUrl.searchParams.append('user_id', userId);
      }

      console.log(`🔌 Connecting WebSocket to ${wsUrl.toString()}`);

      wsRef.current = new WebSocket(wsUrl.toString());

      wsRef.current.onopen = () => {
        console.log('✓ WebSocket connected');
        setIsConnected(true);
        setIsConnecting(false);
        reconnectCountRef.current = 0;
      };

      wsRef.current.onmessage = (event) => {
        try {
          const message: WSMessage = JSON.parse(event.data);

          console.log(`📨 WS Message: ${message.type}`, message.payload);

          // Call generic message handler
          onMessage?.(message);

          // Route based on message type
          switch (message.type) {
            case 'log_chunk':
              onLog?.({
                type: message.payload.stream === 'stderr' ? 'stderr' : 'stdout',
                data: message.payload.text,
                timestamp: message.timestamp,
                stream: message.payload.stream,
              });
              break;

            case 'status_update':
              onStatusChange?.(message.payload.status);
              break;

            case 'execution_complete':
              onComplete?.(message.payload.exit_code, message.payload.duration_seconds);
              break;

            case 'execution_failed':
              onError?.(message.payload.error || 'Execution failed');
              break;

            case 'system_alert':
              console.warn(`⚠️ System Alert: ${message.payload.message}`);
              onError?.(message.payload.message);
              break;

            case 'heartbeat':
              // Keep-alive, no action needed
              break;
          }
        } catch (err) {
          console.error('Failed to parse WS message:', err, event.data);
        }
      };

      wsRef.current.onerror = (error) => {
        console.error('WebSocket error:', error);
        setIsConnected(false);
        onError?.('WebSocket error: ' + error);
      };

      wsRef.current.onclose = () => {
        console.log('💔 WebSocket disconnected');
        setIsConnected(false);
        setIsConnecting(false);

        // Attempt reconnection if enabled
        if (autoReconnect && reconnectCountRef.current < maxReconnectAttempts) {
          reconnectCountRef.current++;
          console.log(
            `🔄 Reconnecting... (${reconnectCountRef.current}/${maxReconnectAttempts})`
          );

          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, RECONNECT_DELAY_MS);
        }
      };
    } catch (error) {
      console.error('Failed to establish WebSocket:', error);
      setIsConnecting(false);
      onError?.('Failed to connect: ' + String(error));
    }
  }, [scriptId, userId, onMessage, onLog, onStatusChange, onComplete, onError, autoReconnect, maxReconnectAttempts]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
  }, []);

  const send = useCallback((data: Record<string, any>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    } else {
      console.warn('WebSocket not connected, message not sent');
    }
  }, []);

  // Auto-connect on mount
  useEffect(() => {
    connect();

    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    isConnected,
    isConnecting,
    connect,
    disconnect,
    send,
  };
};

export default useExecutionWebSocket;
