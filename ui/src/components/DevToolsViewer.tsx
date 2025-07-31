/**
 * LEGACY/FALLBACK COMPONENT - DevTools Browser Viewer
 * 
 * This component serves as a fallback when RRWeb streaming is not available.
 * Used when: result.visual_enabled && result.devtools_url but no visual_streaming_enabled
 * 
 * Primary Method: RRWebVisualizer (/visual/:sessionId) - Full-width live streaming
 * Fallback Method: DevToolsViewer (/devtools/:taskId) - Opens in new window when streaming fails
 * 
 * Status: Active fallback system, kept for reliability
 */
import React, { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { DevToolsStatus } from '@/components/DevToolsStatus';
import DevToolsIframe from '@/components/DevToolsIframe';
import { useDevToolsWebSocket } from '@/hooks/useDevToolsWebSocket';
import { useDevToolsStatus } from '@/hooks/useDevToolsStatus';
import { useAppContext } from '@/contexts/AppContext';
import { 
  ArrowLeft, 
  RefreshCw, 
  Maximize2, 
  Minimize2, 
  Activity,
  Eye,
  Terminal,
  CheckCircle2,
  XCircle,
  Loader2,
  Send,
  MessageSquare
} from 'lucide-react';

interface DevToolsViewerProps {
  taskId?: string;
}

interface WorkflowStatus {
  status: 'connecting' | 'connected' | 'running' | 'completed' | 'failed' | 'disconnected';
  message?: string;
  progress?: number;
  currentStep?: string;
}

export function DevToolsViewer({ taskId: propTaskId }: DevToolsViewerProps) {
  const { taskId: urlTaskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const taskId = propTaskId || urlTaskId;
  
  // Get execution mode and workflow info from context for mode hint and execution trigger
  const { 
    currentExecutionMode, 
    currentTaskId, 
    currentWorkflowData,
    currentUserSessionToken,
    currentExecutionInputs
  } = useAppContext();
  
  // Use the new hooks for enhanced DevTools management
  const { status: devToolsStatus, isLoading: statusLoading } = useDevToolsStatus(taskId || '');
  const { 
    isConnected, 
    connectionStatus, 
    messages, 
    sendMessage, 
    lastStatusUpdate,
    reconnect 
  } = useDevToolsWebSocket(taskId || '');
  
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const [command, setCommand] = useState('');
  const [showCommands, setShowCommands] = useState(false);

  // DevTools iframe is now handled by the DevToolsIframe component
  // No need for manual iframe initialization

  // Process WebSocket messages and update logs
  useEffect(() => {
    const workflowMessages = messages.filter(msg => 
      msg.type === 'log' || msg.type === 'workflow_status' || msg.type === 'error' || msg.type === 'completed'
    );
    
    const newLogs = workflowMessages.map(msg => {
      const timestamp = new Date(msg.timestamp).toLocaleTimeString();
      if (msg.type === 'log') {
        return `[${timestamp}] ${msg.data.message}`;
      } else if (msg.type === 'workflow_status') {
        return `[${timestamp}] Status: ${msg.data.message}`;
      } else if (msg.type === 'error') {
        return `[${timestamp}] ERROR: ${msg.data.message}`;
      } else if (msg.type === 'completed') {
        return `[${timestamp}] COMPLETED: ${msg.data.message}`;
      }
      return `[${timestamp}] ${JSON.stringify(msg.data)}`;
    });
    
    setLogs(newLogs);
  }, [messages]);

  // DevTools iframe is now handled by the DevToolsIframe component

  const handleSendCommand = () => {
    if (!command.trim()) return;
    
    try {
      // Try to parse as JSON first
      const parsedCommand = JSON.parse(command);
      sendMessage(parsedCommand);
    } catch {
      // If not JSON, send as Runtime.evaluate
      sendMessage({
        id: Date.now(),
        method: 'Runtime.evaluate',
        params: { expression: command }
      });
    }
    
    setCommand('');
  };

  const getStatusIcon = () => {
    if (statusLoading) {
      return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />;
    }
    
    if (!isConnected) {
      return <XCircle className="h-4 w-4 text-red-500" />;
    }
    
    if (devToolsStatus?.status === 'ready') {
      return <Eye className="h-4 w-4 text-green-500" />;
    }
    
    return <Activity className="h-4 w-4 text-yellow-500" />;
  };

  const getStatusColor = () => {
    if (statusLoading) {
      return 'bg-blue-500';
    }
    
    if (!isConnected) {
      return 'bg-red-500';
    }
    
    if (devToolsStatus?.status === 'ready') {
      return 'bg-green-500';
    }
    
    return 'bg-yellow-500';
  };

  const getStatusMessage = () => {
    if (statusLoading) {
      return 'Loading DevTools status...';
    }
    
    if (!taskId) {
      return 'No task ID provided';
    }
    
    if (!isConnected) {
      return `Connection ${connectionStatus}`;
    }
    
    if (devToolsStatus?.status === 'ready') {
      return 'DevTools ready';
    }
    
    if (devToolsStatus?.placeholder) {
      return 'Setting up browser...';
    }
    
    return lastStatusUpdate?.message || 'Connecting to DevTools...';
  };

  const toggleFullscreen = () => {
    setIsFullscreen(!isFullscreen);
  };

  return (
    <div className={`h-screen flex flex-col bg-gray-100 ${isFullscreen ? 'fixed inset-0 z-50' : ''}`}>
      {/* Header */}
      <div className="bg-gray-900 border-b border-gray-700 shadow-sm">
        <div className="flex items-center justify-between p-4">
          <div className="flex items-center space-x-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate('/')}
              className="flex items-center space-x-2 text-gray-300 hover:text-white hover:bg-gray-800"
            >
              <ArrowLeft className="h-4 w-4" />
              <span>Back to Workflows</span>
            </Button>
            
            <Separator orientation="vertical" className="h-6 bg-gray-600" />
            
            <div className="flex items-center space-x-2">
              {getStatusIcon()}
              <span className="font-medium text-white">DevTools Viewer</span>
              <Badge variant="outline" className="text-xs border-gray-600 text-gray-300">
                Task: {taskId?.slice(0, 8)}...
              </Badge>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <div className="flex items-center space-x-2 text-sm text-gray-300">
              <div className={`w-2 h-2 rounded-full ${getStatusColor()}`} />
              <span>{getStatusMessage()}</span>
            </div>
            
            <Button 
              variant="outline" 
              size="sm" 
              onClick={reconnect}
              className="border-gray-600 text-gray-300 hover:bg-gray-800 hover:text-white"
            >
              <RefreshCw className="h-4 w-4" />
            </Button>
            
            <Button 
              variant="outline" 
              size="sm" 
              onClick={() => setShowCommands(!showCommands)}
              title="Toggle Command Interface"
              className="border-gray-600 text-gray-300 hover:bg-gray-800 hover:text-white"
            >
              <MessageSquare className="h-4 w-4" />
            </Button>
            
            <Button 
              variant="outline" 
              size="sm" 
              onClick={() => {
                console.log('🔍 [DevToolsViewer] Debug Info:');
                console.log('Task ID:', taskId);
                console.log('Connection Status:', connectionStatus);
                console.log('DevTools Status:', devToolsStatus);
                console.log('Is Connected:', isConnected);
                console.log('Messages:', messages.length);
                console.log('Current URL:', window.location.href);
                const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                console.log('WebSocket URL would be:', `${wsProtocol}//${window.location.host}/workflows/devtools/${taskId}`);
                alert(`Debug: Task ID is ${taskId}, Status: ${connectionStatus}, DevTools: ${devToolsStatus?.status}`);
              }}
              title="Debug Connection"
              className="border-gray-600 text-gray-300 hover:bg-gray-800 hover:text-white"
            >
              🔍
            </Button>
            
            <Button 
              variant="outline" 
              size="sm" 
              onClick={toggleFullscreen}
              className="border-gray-600 text-gray-300 hover:bg-gray-800 hover:text-white"
            >
              {isFullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
            </Button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex">
        {/* DevTools Browser View */}
        <div className="flex-1 bg-white">
          {statusLoading || (!isConnected && connectionStatus === 'connecting') ? (
            <div className="h-full flex items-center justify-center">
              <div className="text-center">
                <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4 text-blue-500" />
                <p className="text-gray-600">{getStatusMessage()}</p>
              </div>
            </div>
          ) : (!isConnected || connectionStatus === 'session_not_found') ? (
            <div className="h-full flex items-center justify-center">
              <div className="text-center max-w-md">
                <XCircle className="h-8 w-8 mx-auto mb-4 text-red-500" />
                <p className="text-gray-600 mb-4">{getStatusMessage()}</p>
                {connectionStatus === 'session_not_found' && (
                  <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-4 text-left">
                    <p className="text-yellow-800 font-medium text-sm mb-2">🔍 Troubleshooting Tips:</p>
                    <ul className="text-yellow-700 text-xs space-y-1">
                      <li>• Check if the backend enabled visual mode properly</li>
                      <li>• Verify the workflow execution returned visual_enabled: true</li>
                      <li>• The workflow may have completed too quickly</li>
                      <li>• Check backend logs for DevTools session creation</li>
                    </ul>
                  </div>
                )}
                <Button onClick={reconnect}>Try Again</Button>
              </div>
            </div>
          ) : (
            <div className="h-full flex flex-col">
              {/* Enhanced Status Bar */}
              <div className="bg-gray-50 border-b px-4 py-2">
                <DevToolsStatus sessionId={taskId || ''} />
              </div>

              {/* Command Interface */}
              {showCommands && (
                <div className="bg-gray-100 border-b px-4 py-2">
                  <div className="flex items-center space-x-2">
                    <input
                      type="text"
                      value={command}
                      onChange={(e) => setCommand(e.target.value)}
                      placeholder="Enter DevTools command or JavaScript..."
                      className="flex-1 px-3 py-1 text-sm border rounded"
                      onKeyPress={(e) => e.key === 'Enter' && handleSendCommand()}
                      disabled={!isConnected}
                    />
                    <Button 
                      size="sm" 
                      onClick={handleSendCommand} 
                      disabled={!isConnected || !command.trim()}
                    >
                      <Send className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}

              {/* Enhanced DevTools Iframe with Execution Trigger */}
              <div className="flex-1 p-4">
                <DevToolsIframe 
                  sessionId={taskId || ''} 
                  expectedMode={
                    // Use execution mode from context if this task matches current execution
                    (taskId && currentTaskId === taskId && currentExecutionMode) 
                      ? currentExecutionMode 
                      : undefined
                  }
                  workflowId={
                    // Pass workflow ID if this task matches current execution
                    (taskId && currentTaskId === taskId && currentWorkflowData) 
                      ? (currentWorkflowData.id || currentWorkflowData.name)
                      : undefined
                  }
                  inputs={
                    // Pass inputs if this task matches current execution
                    (taskId && currentTaskId === taskId && currentExecutionInputs) 
                      ? currentExecutionInputs
                      : undefined
                  }
                  sessionToken={currentUserSessionToken || undefined}
                  onExecutionStart={() => {
                    console.log('🎯 [DevToolsViewer] Workflow execution started!');
                    // Could show a toast or update UI state here
                  }}
                  // Mode will be auto-detected from backend if not provided:
                  // - 'cloud-run' for port 9223 (server/headless execution)
                  // - 'local-run' for port 9224 (local browser with GUI)
                />
              </div>
            </div>
          )}
        </div>

        {/* Sidebar with Enhanced Logs */}
        {!isFullscreen && (
          <div className="w-80 bg-white border-l">
            <Card className="h-full rounded-none border-0">
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center justify-between text-sm">
                  <div className="flex items-center space-x-2">
                    <Terminal className="h-4 w-4" />
                    <span>DevTools Messages</span>
                  </div>
                  <Badge variant="outline" className="text-xs">
                    {messages.length}
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="h-96 overflow-y-auto bg-gray-900 text-green-400 p-3 rounded text-xs font-mono">
                  {messages.length === 0 ? (
                    <p className="text-gray-500">Waiting for DevTools messages...</p>
                  ) : (
                    messages.slice(-50).map((message, index) => (
                      <div key={index} className={`mb-2 p-2 rounded ${
                        message.type === 'status' ? 'bg-blue-900/30 text-blue-300' :
                        message.type === 'error' ? 'bg-red-900/30 text-red-300' :
                        message.type === 'completed' ? 'bg-green-900/30 text-green-300' :
                        message.type === 'protocol' ? 'bg-gray-800/50 text-gray-300' :
                        'bg-yellow-900/30 text-yellow-300'
                      }`}>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs opacity-70">
                            {message.type.toUpperCase()}
                          </span>
                          <span className="text-xs opacity-50">
                            {new Date(message.timestamp).toLocaleTimeString()}
                          </span>
                        </div>
                        <div className="text-xs">
                          {message.type === 'protocol' ? 
                            JSON.stringify(message.data, null, 2) :
                            message.data.message || JSON.stringify(message.data)
                          }
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}

export default DevToolsViewer; 