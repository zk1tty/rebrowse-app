/**
 * LEGACY/FALLBACK COMPONENT - DevTools Status Display
 * 
 * This component displays DevTools connection status for the legacy fallback system.
 * Used within DevToolsViewer when RRWeb streaming is not available.
 * 
 * Primary Method: RRWebVisualizer top bar stats - Integrated live status display
 * Fallback Method: DevToolsStatus - Separate status component for legacy viewer
 * 
 * Status: Active fallback system, supports legacy DevTools workflow
 */
import React from 'react';
import { useDevToolsStatus } from '@/hooks/useDevToolsStatus';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { 
  Loader2, 
  CheckCircle2, 
  Clock, 
  Users, 
  RefreshCw,
  AlertCircle,
  Activity,
  Cloud,
  Monitor,
  Server
} from 'lucide-react';

interface DevToolsStatusProps {
  sessionId: string;
  className?: string;
}

export function DevToolsStatus({ sessionId, className = '' }: DevToolsStatusProps) {
  const { status, isLoading, error, refresh } = useDevToolsStatus(sessionId);

  if (isLoading) {
    return (
      <div className={`flex items-center space-x-2 ${className}`}>
        <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
        <span className="text-sm text-gray-300">Loading DevTools status...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`flex items-center space-x-2 ${className}`}>
        <AlertCircle className="h-4 w-4 text-red-500" />
        <span className="text-sm text-red-400">Error: {error}</span>
        <Button 
          variant="ghost" 
          size="sm" 
          onClick={refresh}
          className="h-6 px-2 text-xs text-gray-400 hover:text-white"
        >
          <RefreshCw className="h-3 w-3" />
        </Button>
      </div>
    );
  }

  if (!status) {
    return (
      <div className={`flex items-center space-x-2 ${className}`}>
        <AlertCircle className="h-4 w-4 text-gray-500" />
        <span className="text-sm text-gray-400">DevTools status unknown</span>
      </div>
    );
  }

  const getStatusIcon = () => {
    if (status.status === 'ready') {
      return <CheckCircle2 className="h-4 w-4 text-green-500" />;
    } else {
      return <Clock className="h-4 w-4 text-yellow-500" />;
    }
  };

  const getStatusText = () => {
    if (status.status === 'ready') {
      return 'DevTools Ready';
    } else if (status.placeholder) {
      return 'Setting up browser...';
    } else {
      return 'Waiting for DevTools...';
    }
  };

  const getStatusColor = () => {
    return status.status === 'ready' ? 'text-green-400' : 'text-yellow-400';
  };

  const getModeIcon = () => {
    if (status.mode === 'cloud-run') {
      return <Cloud className="h-3 w-3 text-blue-400" />;
    } else if (status.mode === 'local-run') {
      return <Monitor className="h-3 w-3 text-green-400" />;
    } else {
      return <Server className="h-3 w-3 text-gray-400" />;
    }
  };

  const getModeText = () => {
    if (status.mode === 'cloud-run') {
      return 'Cloud-Run';
    } else if (status.mode === 'local-run') {
      return 'Local-Run';
    } else {
      return status.mode || 'Unknown';
    }
  };

  const getModeColor = () => {
    if (status.mode === 'cloud-run') {
      return 'border-blue-600 text-blue-400';
    } else if (status.mode === 'local-run') {
      return 'border-green-600 text-green-400';
    } else {
      return 'border-gray-600 text-gray-400';
    }
  };

  return (
    <div className={`flex items-center space-x-3 ${className}`}>
      {/* Main Status */}
      <div className="flex items-center space-x-2">
        {getStatusIcon()}
        <span className={`text-sm font-medium ${getStatusColor()}`}>
          {getStatusText()}
        </span>
      </div>

      {/* Execution Mode */}
      {status.mode && (
        <Badge variant="outline" className={`text-xs ${getModeColor()}`}>
          {getModeIcon()}
          <span className="ml-1">{getModeText()}</span>
          {status.port && (
            <span className="ml-1 text-gray-500">:{status.port}</span>
          )}
        </Badge>
      )}

      {/* Connection Details */}
      <div className="flex items-center space-x-2">
        <div className="flex items-center space-x-1">
          <Users className="h-3 w-3 text-gray-400" />
          <span className="text-xs text-gray-300">
            {status.active_connections}
          </span>
        </div>
        
        {status.pending_connections > 0 && (
          <Badge variant="outline" className="text-xs border-yellow-600 text-yellow-400">
            {status.pending_connections} pending
          </Badge>
        )}
        
        {status.placeholder && (
          <Badge variant="outline" className="text-xs border-blue-600 text-blue-400">
            <Activity className="h-3 w-3 mr-1" />
            Initializing
          </Badge>
        )}
      </div>

      {/* DevTools URL indicator */}
      {status.devtools_url && (
        <div className="flex items-center">
          <div className="w-2 h-2 rounded-full bg-green-500" />
        </div>
      )}
    </div>
  );
} 