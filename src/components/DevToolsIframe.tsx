import React, { useEffect, useRef, useState } from 'react';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Alert, AlertDescription } from './ui/alert';
import { AlertTriangle, Play, Square, RotateCcw, ExternalLink } from 'lucide-react';

// Port mapping for different browser types
const PORT_MAP = {
  chrome: 9222,
  firefox: 9222,
  edge: 9222,
  safari: 9222
};

// Utility function to get browser info
const getBrowserInfo = () => {
  const userAgent = navigator.userAgent.toLowerCase();
  if (userAgent.includes('chrome')) return { name: 'chrome', port: PORT_MAP.chrome };
  if (userAgent.includes('firefox')) return { name: 'firefox', port: PORT_MAP.firefox };
  if (userAgent.includes('edge')) return { name: 'edge', port: PORT_MAP.edge };
  if (userAgent.includes('safari')) return { name: 'safari', port: PORT_MAP.safari };
  return { name: 'unknown', port: 9222 };
};

interface DevToolsIframeProps {
  sessionId?: string;
  expectedMode?: string;
  workflowId?: string;
  inputs?: any;
  sessionToken?: string;
  onExecutionStart?: () => void;
  onStatusChange?: (status: string) => void;
}

const DevToolsIframe: React.FC<DevToolsIframeProps> = ({ onStatusChange }) => {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [devToolsUrl, setDevToolsUrl] = useState<string>('');

  const browserInfo = getBrowserInfo();

  useEffect(() => {
    const url = `http://localhost:${browserInfo.port}`;
    setDevToolsUrl(url);
  }, [browserInfo.port]);

  const handleConnect = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      // Simple connection check
      const response = await fetch(`${devToolsUrl}/json/version`, {
        method: 'GET',
        mode: 'no-cors'
      });
      
      setIsConnected(true);
      onStatusChange?.('connected');
    } catch (err) {
      setError('Failed to connect to DevTools. Make sure the browser is running with remote debugging enabled.');
      setIsConnected(false);
      onStatusChange?.('error');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDisconnect = () => {
    setIsConnected(false);
    setError(null);
    onStatusChange?.('disconnected');
  };

  const handleRefresh = () => {
    if (iframeRef.current) {
      iframeRef.current.src = iframeRef.current.src;
    }
  };

  const openInNewTab = () => {
    window.open(devToolsUrl, '_blank');
  };

  return (
    <Card className="w-full h-full">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>DevTools Connection</span>
          <Badge variant={isConnected ? "default" : "secondary"}>
            {isConnected ? "Connected" : "Disconnected"}
          </Badge>
        </CardTitle>
      </CardHeader>
      
      <CardContent className="space-y-4">
        {error && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span>Browser: {browserInfo.name}</span>
          <span>Port: {browserInfo.port}</span>
        </div>

        <div className="flex gap-2">
          {!isConnected ? (
            <Button 
              onClick={handleConnect} 
              disabled={isLoading}
              className="flex-1"
            >
              {isLoading ? "Connecting..." : "Connect"}
            </Button>
          ) : (
            <>
              <Button 
                onClick={handleDisconnect} 
                variant="outline"
                className="flex-1"
              >
                Disconnect
              </Button>
              <Button 
                onClick={handleRefresh} 
                variant="outline"
                size="icon"
              >
                <RotateCcw className="h-4 w-4" />
              </Button>
              <Button 
                onClick={openInNewTab} 
                variant="outline"
                size="icon"
              >
                <ExternalLink className="h-4 w-4" />
              </Button>
            </>
          )}
        </div>

        {isConnected && (
          <div className="border rounded-md h-96">
            <iframe
              ref={iframeRef}
              src={devToolsUrl}
              className="w-full h-full border-0"
              title="DevTools"
            />
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default DevToolsIframe;