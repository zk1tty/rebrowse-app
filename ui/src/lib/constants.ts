// 🌐 Global Constants for API Configuration
// This file centralizes all URL configurations to avoid hardcoding

/**
 * Determines if we're in production environment
 */
export const IS_PRODUCTION = window.location.hostname !== 'localhost';

/**
 * Base API URL - automatically switches between development and production
 * In development, use empty string to leverage Vite proxy
 * In production, use the backend API server URL
 */
export const API_BASE_URL = import.meta.env.VITE_PUBLIC_API_URL || 
  (IS_PRODUCTION ? 'https://api.rebrowse.me' : 'http://127.0.0.1:8000');

/**
 * WebSocket base URL - automatically switches between development and production
 * In development, use the frontend host (Vite will proxy to backend)
 * In production, use the backend API server with WebSocket protocol
 */
export const WS_BASE_URL = IS_PRODUCTION ? 
  `wss://api.rebrowse.me` : 
  `ws://${window.location.host}`;

/**
 * API Endpoints Configuration
 */
export const API_ENDPOINTS = {
  // Workflow execution
  EXECUTE_WORKFLOW: (workflowId: string) => `${API_BASE_URL}/workflows/${workflowId}/execute/session`,
  
  // Visual streaming endpoints
  VISUAL_STATUS: (sessionId: string) => `${API_BASE_URL}/workflows/visual/${sessionId}/status`,
  VISUAL_VIEWER: (sessionId: string) => `${API_BASE_URL}/workflows/visual/${sessionId}/viewer`,
  VISUAL_STREAM_WS: (sessionId: string) => `${WS_BASE_URL}/workflows/visual/${sessionId}/stream`,

  // Live logs WebSocket endpoint
  LOGS_STREAM_WS: (executionId: string) => `${WS_BASE_URL}/ws/logs/${executionId}`,
  
  // Standard API endpoints
  WORKFLOWS: `${API_BASE_URL}/workflows`,
  WORKFLOW_LOGS: (taskId: string, position: number) => `${API_BASE_URL}/workflows/${taskId}/logs?position=${position}`,
  CANCEL_WORKFLOW: (taskId: string) => `${API_BASE_URL}/workflows/${taskId}/cancel`,
  
  // Enhanced workflow endpoints
  WORKFLOW_STATS: (workflowId: string) => `${API_BASE_URL}/workflows/executions/stats/${workflowId}`,
  EXECUTION_HISTORY: `${API_BASE_URL}/workflows/executions/history`,
  ACTIVE_EXECUTIONS: `${API_BASE_URL}/workflows/executions/active`,
  // Workflow run events (Snapshot + Event stream)
  RUN_EVENTS_WS: (runId: string) => `${WS_BASE_URL}/runs/${runId}/events`,
} as const;