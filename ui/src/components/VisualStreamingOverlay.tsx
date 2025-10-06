import React, { memo } from 'react';
import { X } from 'lucide-react';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { RRWebVisualizer } from './RRWebVisualizer';
import ErrorBoundary from './ErrorBoundary';
import { useAppContext } from '@/contexts/AppContext';

interface VisualStreamingOverlayProps {
  sessionId: string;
  workflowInfo: {
    name: string;
    taskId: string;
    mode: string;
    hasStreamingSupport?: boolean;
  };
  isOpen: boolean;
  onClose: () => void;
  onCompleted?: () => void;
}

const VisualStreamingOverlayComponent = memo(function VisualStreamingOverlay({
  sessionId,
  workflowInfo,
  isOpen,
  onClose,
  onCompleted
}: VisualStreamingOverlayProps) {

  
  // CRITICAL FIX: Stabilize onClose callback to prevent infinite remounts
  const stableOnCloseRef = React.useRef(onClose);
  stableOnCloseRef.current = onClose;
  
  const stableOnClose = React.useCallback(() => {
    stableOnCloseRef.current();
  }, []); // Empty deps = stable reference forever

  useAppContext();

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
      {/* 80% Screen Overlay */}
      <div className="w-[80%] h-[80%] bg-white rounded-lg shadow-2xl flex flex-col overflow-hidden">
        {/* Overlay Header */}
        <div className="bg-gray-900 text-white px-4 py-3 flex items-center justify-between shrink-0">
          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
            </div>
            <Badge variant="outline" className={`text-xs border-gray-600 ${
              workflowInfo.hasStreamingSupport 
                ? 'text-green-300 border-green-600' 
                : 'text-yellow-300 border-yellow-600'
            }`}>
              {workflowInfo.hasStreamingSupport ? 'Live Streaming' : 'Limited'}
            </Badge>
          </div>
          
          <div className="flex items-center space-x-2">
            <div className="text-sm text-gray-300">
              <span className="font-medium">{workflowInfo.name}</span>
              <span className="mx-2">•</span>
              <span className="capitalize">{workflowInfo.mode}</span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={stableOnClose}
              className="text-gray-300 hover:text-white hover:bg-gray-800"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* RRWeb Visualizer Content */}
        <div className="flex-1 relative overflow-hidden">
          <ErrorBoundary
            onError={(error, errorInfo) => {
              console.error('🚨 [VisualStreamingOverlay] RRWebVisualizer error:', error);
              console.error('🚨 [VisualStreamingOverlay] Error info:', errorInfo);
            }}
          >
            <RRWebVisualizer 
              key={`visualizer-${sessionId}`} // Stable key with prefix
              sessionId={sessionId}
              onClose={stableOnClose}
              onCompleted={onCompleted}
            />
          </ErrorBoundary>
        </div>

        {/* Overlay Footer (Optional) */}
        <div className="bg-gray-50 px-4 py-2 border-t flex items-center justify-between shrink-0">
          <div className="flex items-center space-x-4 text-xs text-gray-600">
            <span>Session: {sessionId.slice(0, 16)}...</span>
            <span>Task ID: {workflowInfo.taskId.slice(0, 8)}...</span>
          </div>
          <div className="text-xs text-gray-600">
            {workflowInfo.hasStreamingSupport ? (
              <span className="text-green-600">✅ Visual mode active</span>
            ) : (
              <span className="text-yellow-600">⚠️ Limited view</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
});

// Enhanced memoization to prevent unnecessary re-renders
const EnhancedVisualStreamingOverlay = memo(VisualStreamingOverlayComponent, (prevProps, nextProps) => {
  const propsChanged = (
    prevProps.sessionId !== nextProps.sessionId ||
    prevProps.isOpen !== nextProps.isOpen ||
    prevProps.onClose !== nextProps.onClose ||
    JSON.stringify(prevProps.workflowInfo) !== JSON.stringify(nextProps.workflowInfo)
  );
  
  // Return true if props are the same (prevent re-render), false if different (allow re-render)
  return !propsChanged;
});

// Add display name for debugging
EnhancedVisualStreamingOverlay.displayName = 'EnhancedVisualStreamingOverlay';

export const VisualStreamingOverlay = EnhancedVisualStreamingOverlay;
export default EnhancedVisualStreamingOverlay; 