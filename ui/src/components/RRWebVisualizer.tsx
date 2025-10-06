import React, { useEffect, useRef, useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
  RefreshCw, 
  Activity,
  Eye,
  XCircle,
  Loader2,
  AlertTriangle
} from 'lucide-react';

import { WorkflowVisualizer } from './WorkflowVisualizer';
import { FrontendScreensaver } from './FrontendScreensaver';

interface RRWebVisualizerProps {
  sessionId?: string;
  onClose?: () => void;
  onCompleted?: () => void;
}

const RRWebVisualizerComponent = React.memo(function RRWebVisualizer({ 
  sessionId: propSessionId, 
  onClose,
  onCompleted
}: RRWebVisualizerProps) {
  const { sessionId: urlSessionId } = useParams<{ sessionId: string }>();
  const sessionId = propSessionId || urlSessionId;
  

  
  const visualizerRef = useRef<WorkflowVisualizer | null>(null);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  
  const [connectionStatus, setConnectionStatus] = useState<'disconnected' | 'connecting' | 'connected' | 'error'>('disconnected');
  // const [connectedSessionId, setConnectedSessionId] = useState<string | null>(null);
  const [stats, setStats] = useState({
    eventsReceived: 0,
    bytesReceived: 0,
    eventsPerSecond: 0,
    totalEvents: 0,
    duration: 0
  });
  const [logs, setLogs] = useState<string[]>([]);
  const [rrwebLoaded, setRrwebLoaded] = useState(false);
  const [playerState, setPlayerState] = useState<'loading' | 'ready' | 'playing' | 'error'>('loading');
  const [playerError, setPlayerError] = useState<string | null>(null);
  
  // 🔄 CONTENT SWITCHING: Track when to switch from screensaver to RRWeb content
  const [hasRealContent, setHasRealContent] = useState(false);
  
  // Simple state (official rrweb stream pattern)
  const [autoCloseTimer, setAutoCloseTimer] = useState<NodeJS.Timeout | null>(null);

  // Load rrweb
  useEffect(() => {
    setRrwebLoaded(true);
    addLog('rrweb library loaded successfully', 'success');
  }, []);

  // Throttled log function
  const logBuffer = useRef<string[]>([]);
  const flushLogsTimer = useRef<NodeJS.Timeout | null>(null);
  
  const flushLogs = useCallback(() => {
    if (logBuffer.current.length > 0) {
      setLogs((prev: string[]) => [...prev.slice(-49), ...logBuffer.current].slice(-50));
      logBuffer.current = [];
    }
    flushLogsTimer.current = null;
  }, []);
  
  const addLog = useCallback((message: string, _type?: 'info' | 'success' | 'warning' | 'error') => {
    const timestamp = new Date().toLocaleTimeString();
    const logEntry = `[${timestamp}] ${message}`;
    
    logBuffer.current.push(logEntry);
    
    if (!flushLogsTimer.current) {
      flushLogsTimer.current = setTimeout(flushLogs, 2000);
    }
  }, [flushLogs]);

  // CSP configuration for enhanced security (Option 3)
  const configureiFrameCSP = useCallback((iframe: HTMLIFrameElement) => {
    try {
      // Wait for iframe to load
      iframe.onload = () => {
        try {
          const iframeDoc = iframe.contentDocument || iframe.contentWindow?.document;
          if (iframeDoc) {
            // Add CSP meta tag to iframe document
            const meta = iframeDoc.createElement('meta');
            meta.httpEquiv = 'Content-Security-Policy';
            meta.content = "default-src 'self' 'unsafe-inline' 'unsafe-eval'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline';";
            
            // Add meta tag to head or create head if it doesn't exist
            let head = iframeDoc.head;
            if (!head) {
              head = iframeDoc.createElement('head');
              iframeDoc.documentElement.appendChild(head);
            }
            head.appendChild(meta);
            
            addLog('✅ CSP headers configured for iframe document', 'success');
          }
        } catch (error) {
          addLog(`⚠️ Could not configure CSP: ${error instanceof Error ? error.message : String(error)}`, 'warning');
        }
      };
    } catch (error) {
      addLog(`⚠️ CSP configuration failed: ${error instanceof Error ? error.message : String(error)}`, 'warning');
    }
  }, [addLog]);

  // Session ID validation helper
  // const validateSessionId = useCallback((sessionId: string) => {
  //   addLog(`🔍 Session ID validation:`);
  //   addLog(`   • Full ID: ${sessionId}`);
  //   addLog(`   • Length: ${sessionId.length} characters`);
  //   const isVisualSession = sessionId.startsWith('visual-');
  //   const uuidPart = isVisualSession ? sessionId.substring(7) : sessionId;
  //   const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  //   const isValidUUID = uuidRegex.test(uuidPart);
  //   addLog(`   • Visual session: ${isVisualSession ? '✅' : '❌'}`);
  //   addLog(`   • Valid UUID core: ${isValidUUID ? '✅' : '❌'}`);
  //   return isValidUUID;
  // }, [addLog]);

  // Simple initialization (official rrweb stream pattern)
  useEffect(() => {
    if (!rrwebLoaded || !sessionId || visualizerRef.current) {
      return;
    }

    // Wait for iframe to be available AND properly rendered by React
    let attempts = 0;
    const maxAttempts = 50; // 5 seconds max
    
    const initializeWhenReady = () => {
      attempts++;
      
      if (!iframeRef.current) {
        if (attempts >= maxAttempts) {
          console.error('❌ [RRWebVisualizer] Timeout waiting for iframe to be rendered');
          addLog('❌ Timeout waiting for iframe to be rendered');
          setConnectionStatus('error');
      return;
    }

        // Iframe not ready yet, wait a bit more
        setTimeout(initializeWhenReady, 100);
      return;
    }
    
      // Iframe ref exists, but now wait for React to finish DOM operations
      
      // Use requestAnimationFrame to ensure React has completed its render cycle
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          // Small delay to ensure iframe is fully stable in DOM
          setTimeout(() => {
            // Re-verify iframe is still good before passing to WorkflowVisualizer
            if (!iframeRef.current || !document.contains(iframeRef.current)) {
              console.error('❌ [RRWebVisualizer] Iframe became invalid');
              addLog('❌ Iframe became invalid');
              setConnectionStatus('error');
              return;
            }

            // Simple visualizer setup
      visualizerRef.current = new WorkflowVisualizer({
        onConnect: (connectedId: string) => {
          setConnectionStatus('connected');
          addLog(`✅ Connected to session: ${connectedId}`, 'success');
        },
        onDisconnect: (event: CloseEvent) => {
          setConnectionStatus('disconnected');
          if (event.code === 1000) {
            if (onCompleted) {
              setTimeout(onCompleted, 3000);
            } else if (onClose) {
              setTimeout(onClose, 3000);
            }
          }
        },
        onEvent: (data: any) => {
          if (data.type === 'player_ready') {
            setPlayerState('playing');
            addLog('🎬 RRWeb player ready - live mode activated!', 'success');
          }
          
          // 🎬 SCREENSAVER → RRWEB SWITCH: Detect FullSnapshot (type=2) to switch from screensaver to recorded content
          if (data.event_data?.type === 2 || data.event?.type === 2) {
            if (!hasRealContent) {
              setHasRealContent(true);
              addLog('🔄 Content detected - switching to RRWeb playback', 'success');
            }
          }
          
          // Update stats
          const newStats = visualizerRef.current?.getStatistics();
          if (newStats) setStats(newStats);
        },
        onError: (error: Error) => {
          setConnectionStatus('error');
          setPlayerError(error.message);
          addLog(`❌ Error: ${error.message}`);
        }
      });

            // Store reference for debugging
            (window as any).debugIframeRef = iframeRef.current;
            
            // Configure CSP for iframe security (Option 3)
            configureiFrameCSP(iframeRef.current);
            
            // Initialize player (now async) and then connect
            // ✅ Uses official RRWeb live mode pattern: startLive() called when first event arrives
            (async () => {
              try {
                await visualizerRef.current!.initializePlayer(iframeRef.current!);
                connectToExistingSession();
              } catch (error) {
                console.error('❌ [RRWebVisualizer] Player initialization failed:', error);
                addLog(`❌ Player initialization failed: ${error instanceof Error ? error.message : String(error)}`, 'error');
                setConnectionStatus('error');
              }
            })();
          }, 100); // Small delay to ensure DOM stability
        });
      });
    };

    // Start the initialization process
    initializeWhenReady();

    return () => {
      visualizerRef.current?.disconnect();
        visualizerRef.current = null;
      if (autoCloseTimer) {
        clearTimeout(autoCloseTimer);
        setAutoCloseTimer(null);
      }
    };
  }, [rrwebLoaded, sessionId, addLog, onClose]);

  const connectToExistingSession = useCallback(async () => {
    if (!visualizerRef.current || !sessionId) return;

    try {
      setConnectionStatus('connecting');
      addLog(`🔗 Connecting to session: ${sessionId}`);
      
      // Direct connection (official rrweb stream pattern)
      await visualizerRef.current.connectToStream(sessionId);
      
      // Fallback: if no FullSnapshot arrives in time (completed session), render cached snapshot
      setTimeout(() => {
        if (!hasRealContent && visualizerRef.current) {
          const rendered = visualizerRef.current.renderCachedSnapshot(sessionId);
          if (rendered) {
            setHasRealContent(true);
            addLog('🖼️ Rendered cached snapshot (session may be completed)');
          } else {
            addLog('⏳ Still waiting for FullSnapshot...');
            // Keep waiting quietly; user can retry
          }
        }
      }, 3000);
      
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      addLog(`❌ Connection failed: ${errorMessage}`);
      setConnectionStatus('error');
    }
  }, [sessionId, addLog, hasRealContent]);

  // Utility functions
  const getStatusIcon = () => {
    switch (connectionStatus) {
      case 'connected':
        return <Eye className="h-4 w-4 text-green-500" />;
      case 'connecting':
        return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />;
      case 'error':
        return <XCircle className="h-4 w-4 text-red-500" />;
      default:
        return <Activity className="h-4 w-4 text-gray-500" />;
    }
  };

  const getStatusColor = () => {
    switch (connectionStatus) {
      case 'connected':
        return 'bg-green-500';
      case 'connecting':
        return 'bg-blue-500';
      case 'error':
        return 'bg-red-500';
      default:
        return 'bg-gray-500';
    }
  };

  // Removed fullscreen-related functions

  if (!rrwebLoaded) {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4 text-blue-500" />
          <p className="text-gray-600">Loading visual mode...</p>
        </div>
      </div>
    );
  }

  // Always embedded mode now
  return (
    <div className="h-full flex flex-col bg-gray-100">
      {/* Visual panel header */}
      <div className="bg-gray-800 border-b border-gray-600 px-4 py-2 shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4 text-sm">
            <div className="flex items-center space-x-2">
              {getStatusIcon()}
              <span className="text-white">Web Stream</span>
              <div className={`w-2 h-2 rounded-full ${getStatusColor()}`} />
              <span className="text-gray-300 capitalize">{connectionStatus}</span>
            </div>
            
            {/* Live Stats Integration */}
            {connectionStatus === 'connected' && (
              <div className="flex items-center space-x-3 text-xs">
                <div className="flex items-center space-x-1">
                  <span className="text-gray-400">Events:</span>
                  <span className="text-blue-400 font-medium">{stats.totalEvents}</span>
                </div>
                <div className="flex items-center space-x-1">
                  <span className="text-gray-400">Rate:</span>
                  <span className="text-green-400 font-medium">{stats.eventsPerSecond}/s</span>
                </div>
                <Badge variant="outline" className="text-xs text-green-600 border-green-400">
                  🟢 LIVE
                </Badge>
              </div>
            )}
          </div>
          
          <div className="flex items-center space-x-2">
            <Button 
              variant="outline" 
              size="sm" 
              onClick={connectToExistingSession}
              disabled={connectionStatus === 'connecting'}
              className="border-gray-600 text-gray-300 hover:bg-gray-700 hover:text-white text-xs"
            >
              <RefreshCw className="h-3 w-3" />
            </Button>
          </div>
        </div>
      </div>

      {/* Content area strictly subtracts header height (using flex layout) */}
      <div className="flex-1 bg-white min-h-0">
        <div className="h-full min-h-0">
          {/* Fill panel height with no extra padding; center content with no top/bottom gaps */}
          <div className="relative w-full h-full bg-gray-50 overflow-hidden">
            <div className="absolute inset-0 w-full h-full">
            {/* 🎬 FRONTEND SCREENSAVER: Show until RRWeb content arrives */}
              <FrontendScreensaver isVisible={!hasRealContent} />

            {/* ✅ RRWeb iframe - shown when real content arrives */}
              <iframe 
                ref={iframeRef} 
                src="about:blank"
                sandbox="allow-scripts allow-same-origin allow-popups allow-forms"
                className="absolute inset-0 w-full h-full overflow-hidden bg-white border-0 rrweb-iframe" 
                title="rrweb-player"
                style={{
                  backgroundColor: '#ffffff',
                  display: hasRealContent ? 'block' : 'none'
                }}
              />
            </div>
            
            {/* Overlay states on top of iframe */}
            {connectionStatus === 'connecting' && (
              <div className="absolute inset-0 flex items-center justify-center z-10 bg-white bg-opacity-90">
                <div className="text-center">
                  <Loader2 className="h-6 w-6 animate-spin mx-auto mb-2 text-blue-500" />
                  <p className="text-sm text-gray-600">Connecting to visual stream...</p>
                  <div className="mt-2 text-xs text-gray-500">
                    Session: {sessionId?.slice(0, 16)}...
                  </div>
                </div>
              </div>
            )}
            
            {connectionStatus === 'error' && (
              <div className="absolute inset-0 flex items-center justify-center z-10 bg-white bg-opacity-90">
                <div className="text-center max-w-sm">
                  <AlertTriangle className="h-6 w-6 mx-auto mb-2 text-yellow-500" />
                  <h3 className="text-sm font-medium text-gray-900 mb-2">Connection Failed</h3>
                  <p className="text-xs text-gray-600 mb-3">Unable to connect to the rrweb streaming endpoint.</p>
                  <Button size="sm" onClick={connectToExistingSession}>Try Again</Button>
                </div>
              </div>
            )}
            
            {playerState === 'loading' && connectionStatus !== 'connecting' && connectionStatus !== 'error' && (
              <div className="absolute inset-0 flex items-center justify-center z-10 bg-white bg-opacity-90">
                <div className="text-center text-gray-600">
                  <div className="text-2xl mb-2">🎥</div>
                  <div>Initializing visual mode...</div>
                  <div className="text-xs mt-2 text-gray-500">
                    View mode will activate when first event arrives
                  </div>
                </div>
              </div>
            )}
            
            {playerState === 'error' && connectionStatus !== 'error' && (
              <div className="absolute inset-0 flex items-center justify-center z-10 bg-white bg-opacity-90">
                <div className="text-center text-red-600">
                  <div className="text-2xl mb-2">❌</div>
                  <div>Player Error</div>
                  <div className="text-xs mt-2 text-red-500">
                    {playerError}
                  </div>
                </div>
              </div>
            )}
            
            {connectionStatus === 'connected' && (
              <div className="absolute top-2 right-2 bg-green-500 text-white px-2 py-1 rounded text-xs font-medium animate-pulse">
                📡 Live
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
});

RRWebVisualizerComponent.displayName = 'RRWebVisualizer';

export const RRWebVisualizer = RRWebVisualizerComponent;
export default RRWebVisualizer; 