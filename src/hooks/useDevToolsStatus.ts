/**
 * LEGACY/FALLBACK HOOK - DevTools Status Management
 * 
 * This hook manages DevTools status polling for the legacy fallback system.
 * Used by DevToolsStatus component when RRWeb streaming is not available.
 * 
 * Primary Method: WorkflowVisualizer stats - Built-in status management
 * Fallback Method: useDevToolsStatus - Separate status polling for legacy viewer
 * 
 * Status: Active fallback system, provides status for DevTools components
 */
import { useState, useEffect, useCallback } from 'react';

interface DevToolsStatus {
  devtools_url: string | null;
  placeholder: boolean;
  active_connections: number;
  pending_connections: number;
  status: "waiting" | "ready";
  port: number | null;
  mode: 'cloud-run' | 'local-run' | 'custom' | 'unknown';
}

interface DevToolsStatusResponse {
  success: boolean;
  session_id: string;
  status: DevToolsStatus;
  message: string;
}

interface UseDevToolsStatusResult {
  status: DevToolsStatus | null;
  isLoading: boolean;
  error: string | null;
  refresh: () => void;
}

export function useDevToolsStatus(sessionId: string): UseDevToolsStatusResult {
  const [status, setStatus] = useState<DevToolsStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    if (!sessionId) return;
    
    try {
      setIsLoading(true);
      setError(null);
      
      const response = await fetch(`/workflows/devtools/${sessionId}/status`);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data: DevToolsStatusResponse = await response.json();
      
      if (data.success) {
        setStatus(data.status);
      } else {
        throw new Error(data.message || 'Failed to fetch status');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setStatus(null);
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    fetchStatus();
    
    // Poll for status updates every 2 seconds while waiting
    const interval = setInterval(() => {
      if (status?.status === "waiting") {
        fetchStatus();
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [fetchStatus, status?.status]);

  return {
    status,
    isLoading,
    error,
    refresh: fetchStatus
  };
} 