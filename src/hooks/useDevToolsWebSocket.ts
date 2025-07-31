/**
 * LEGACY/FALLBACK HOOK - DevTools WebSocket Management
 * 
 * This hook manages DevTools WebSocket connections for the legacy fallback system.
 * Used by DevToolsViewer when RRWeb streaming is not available.
 * 
 * Primary Method: WorkflowVisualizer WebSocket - Built-in streaming connection  
 * Fallback Method: useDevToolsWebSocket - Separate WebSocket for legacy DevTools
 * 
 * Status: Active fallback system, provides WebSocket management for DevTools components
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { WS_BASE_URL } from '@/lib/constants';

interface DevToolsStatusMessage {
  type: "devtools_status";
  status: "connecting" | "connected" | "disconnected" | "error";
  message: string;
  timestamp: number;
}

interface DevToolsProtocolMessage {
  id?: number;
  method?: string;
  params?: any;
  result?: any;
  error?: any;
}

interface DevToolsMessage {
  type: 'status' | 'protocol' | 'workflow_status' | 'log' | 'error' | 'completed';
  data: any;
  timestamp: number;
}

interface UseDevToolsWebSocketResult {
  isConnected: boolean;
  connectionStatus: string;
  messages: DevToolsMessage[];
  sendMessage: (message: any) => void;
  lastStatusUpdate: DevToolsStatusMessage | null;
  reconnect: () => void;
}

export function useDevToolsWebSocket(sessionId: string): UseDevToolsWebSocketResult {
  const [isConnected, setIsConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [messages, setMessages] = useState<DevToolsMessage[]>([]);
  const [lastStatusUpdate, setLastStatusUpdate] = useState<DevToolsStatusMessage | null>(null);
  
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const sendMessage = useCallback((message: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket not connected, cannot send message:', message);
    }
  }, []);

  const connect = useCallback(() => {
    if (!sessionId) return;

    // Clear any existing reconnect timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }

    // Close existing connection
    if (wsRef.current) {
      wsRef.current.close();
    }

    // Connect to backend WebSocket endpoint using constants
    const wsUrl = `${WS_BASE_URL}/workflows/devtools/${sessionId}`;
    
    console.log(`🔌 [useDevToolsWebSocket] Connecting to: ${wsUrl}`);
    setConnectionStatus('connecting');
    
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('✅ DevTools WebSocket connected');
      setIsConnected(true);
      setConnectionStatus('connected');
      
      // Add connection message
      setMessages(prev => [...prev, {
        type: 'status',
        data: { type: 'devtools_status', status: 'connected', message: 'WebSocket connected', timestamp: Date.now() },
        timestamp: Date.now()
      }]);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        // Check if it's a status update
        if (data.type === 'devtools_status') {
          console.log('📢 Status Update:', data);
          setLastStatusUpdate(data);
          setConnectionStatus(data.status);
          
          setMessages(prev => [...prev, {
            type: 'status',
            data,
            timestamp: Date.now()
          }]);
        } else if (data.type === 'workflow_status' || data.type === 'log' || data.type === 'error' || data.type === 'completed') {
          // Handle workflow-specific messages
          setMessages(prev => [...prev, {
            type: data.type,
            data,
            timestamp: Date.now()
          }]);
        } else {
          // Regular DevTools protocol message
          setMessages(prev => [...prev, {
            type: 'protocol',
            data,
            timestamp: Date.now()
          }]);
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
        setMessages(prev => [...prev, {
          type: 'error',
          data: { message: 'Failed to parse WebSocket message', error },
          timestamp: Date.now()
        }]);
      }
    };

    ws.onclose = (event) => {
      console.log('🔌 DevTools WebSocket closed:', event.code, event.reason);
      setIsConnected(false);
      
      let status = 'disconnected';
      let message = 'Connection closed';
      
      if (event.code === 4404) {
        status = 'session_not_found';
        message = 'DevTools session not found';
      } else if (event.code === 4408) {
        status = 'timeout';
        message = 'Connection timeout';
      } else if (event.code === 1006) {
        status = 'connection_lost';
        message = 'Connection lost unexpectedly';
      } else if (event.code === 1000) {
        status = 'closed_normal';
        message = 'Connection closed normally';
      } else if (event.reason) {
        message = `Connection closed: ${event.reason}`;
      }
      
      setConnectionStatus(status);
      
      setMessages(prev => [...prev, {
        type: 'status',
        data: { type: 'devtools_status', status, message, timestamp: Date.now() },
        timestamp: Date.now()
      }]);

      // Auto-reconnect for certain error codes (but not for session not found)
      if (event.code !== 4404 && event.code !== 1000) {
        console.log('🔄 Attempting to reconnect in 3 seconds...');
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, 3000);
      }
    };

    ws.onerror = (error) => {
      console.error('❌ DevTools WebSocket error:', error);
      setConnectionStatus('error');
      
      setMessages(prev => [...prev, {
        type: 'error',
        data: { message: 'WebSocket connection error', error },
        timestamp: Date.now()
      }]);
    };
  }, [sessionId]);

  const reconnect = useCallback(() => {
    connect();
  }, [connect]);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  return {
    isConnected,
    connectionStatus,
    messages,
    sendMessage,
    lastStatusUpdate,
    reconnect
  };
} 