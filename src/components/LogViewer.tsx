import React, { useEffect, useRef, useState } from 'react';
import { useAppContext } from '@/contexts/AppContext';
import { Button } from '@/components/ui/button';
import { 
  Terminal, 
  Square, 
  Play, 
  Trash2, 
  Download, 
  Copy, 
  Loader2,
  AlertCircle,
  CheckCircle,
  XCircle
} from 'lucide-react';
import { useTheme } from '@/contexts/ThemeContext';

export const LogViewer: React.FC = () => {
  const {
    logData,
    workflowStatus,
    workflowError,
    currentTaskId,
    cancelWorkflowExecution,
  } = useAppContext();
  const { theme } = useTheme();
  const logContainerRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (autoScroll && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logData, autoScroll]);

  const handleCopyLogs = () => {
    const logsText = logData.join('\n');
    navigator.clipboard.writeText(logsText);
  };

  const handleDownloadLogs = () => {
    const logsText = logData.join('\n');
    const blob = new Blob([logsText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `workflow-logs-${new Date().toISOString().slice(0, 19)}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleClearLogs = () => {
    // Clear logs functionality would need to be implemented in AppContext
    console.log('Clear logs requested');
  };

  const handleCancelWorkflow = () => {
    if (currentTaskId) {
      cancelWorkflowExecution(currentTaskId);
    }
  };

  const getStatusIcon = () => {
    switch (workflowStatus) {
      case 'running':
        return <Loader2 className="w-4 h-4 animate-spin text-blue-500" />;
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-500" />;
      case 'cancelled':
        return <AlertCircle className="w-4 h-4 text-yellow-500" />;
      default:
        return <Terminal className="w-4 h-4 text-gray-500" />;
    }
  };

  const getStatusText = () => {
    switch (workflowStatus) {
      case 'running':
        return 'Running...';
      case 'completed':
        return 'Completed';
      case 'failed':
        return 'Failed';
      case 'cancelled':
        return 'Cancelled';
      default:
        return 'Ready';
    }
  };

  return (
    <div className={`h-full flex flex-col ${
      theme === 'dark' 
        ? 'bg-gray-900 border-gray-700' 
        : 'bg-white border-gray-200'
    }`}>
      {/* Header */}
      <div className={`p-4 border-b flex items-center justify-between ${
        theme === 'dark' ? 'border-gray-700' : 'border-gray-200'
      }`}>
        <div className="flex items-center space-x-3">
          {getStatusIcon()}
          <div>
            <h3 className={`font-semibold text-sm ${
              theme === 'dark' ? 'text-white' : 'text-gray-900'
            }`}>
              Workflow Execution Logs
            </h3>
            <p className={`text-xs ${
              theme === 'dark' ? 'text-gray-400' : 'text-gray-500'
            }`}>
              Status: {getStatusText()}
            </p>
          </div>
        </div>
        
        {/* Action buttons */}
        <div className="flex items-center space-x-1">
          {workflowStatus === 'running' && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleCancelWorkflow}
              className="text-red-600 hover:text-red-700 hover:bg-red-50 p-2"
              title="Cancel workflow"
            >
              <XCircle className="w-3 h-3" />
            </Button>
          )}
          
          <Button
            variant="ghost"
            size="sm"
            onClick={handleCopyLogs}
            className={`p-2 ${
              theme === 'dark' 
                ? 'text-gray-300 hover:text-white hover:bg-gray-800' 
                : 'text-gray-600 hover:text-gray-800 hover:bg-gray-100'
            }`}
            title="Copy logs"
          >
            <Copy className="w-3 h-3" />
          </Button>
          
          <Button
            variant="ghost"
            size="sm"
            onClick={handleDownloadLogs}
            className={`p-2 ${
              theme === 'dark' 
                ? 'text-gray-300 hover:text-white hover:bg-gray-800' 
                : 'text-gray-600 hover:text-gray-800 hover:bg-gray-100'
            }`}
            title="Download logs"
          >
            <Download className="w-3 h-3" />
          </Button>
        </div>
      </div>

      {/* Log content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {workflowError && (
          <div className="p-3 bg-red-50 border-b border-red-200">
            <div className="flex items-start space-x-2">
              <XCircle className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-sm font-medium text-red-800">Error</p>
                <p className="text-xs text-red-600 mt-1">{workflowError}</p>
              </div>
            </div>
          </div>
        )}

        <div 
          ref={logContainerRef}
          className={`flex-1 overflow-y-auto p-4 font-mono text-xs leading-relaxed ${
            theme === 'dark' 
              ? 'bg-gray-900 text-gray-300' 
              : 'bg-gray-50 text-gray-800'
          }`}
          onScroll={(e) => {
            const target = e.target as HTMLDivElement;
            const isAtBottom = target.scrollHeight - target.scrollTop === target.clientHeight;
            setAutoScroll(isAtBottom);
          }}
        >
          {logData.length === 0 ? (
            <div className={`flex items-center justify-center h-full ${
              theme === 'dark' ? 'text-gray-500' : 'text-gray-400'
            }`}>
              <div className="text-center">
                <Terminal className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm">No logs yet</p>
                <p className="text-xs mt-1">Workflow execution logs will appear here</p>
              </div>
            </div>
          ) : (
            <div className="space-y-1">
              {logData.map((log, index) => (
                <div 
                  key={index} 
                  className={`whitespace-pre-wrap break-words ${
                    theme === 'dark' ? 'text-gray-300' : 'text-gray-700'
                  }`}
                >
                  {log}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Auto-scroll indicator */}
        {!autoScroll && (
          <div className="p-2 border-t border-gray-200">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setAutoScroll(true);
                if (logContainerRef.current) {
                  logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
                }
              }}
              className="w-full text-xs"
            >
              <Play className="w-3 h-3 mr-1" />
              Resume auto-scroll
            </Button>
          </div>
        )}
      </div>
    </div>
  );
};
