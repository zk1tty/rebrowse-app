import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { Button } from './ui/button';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error?: Error;
  errorInfo?: ErrorInfo;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    console.log('🛡️ [ErrorBoundary] Constructor called at:', new Date().toISOString());
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('🚨 [ErrorBoundary] Caught error:', error);
    console.error('🚨 [ErrorBoundary] Error info:', errorInfo);
    
    this.setState({ error, errorInfo });
    
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
  }

  handleReset = () => {
    this.setState({ hasError: false, error: undefined, errorInfo: undefined });
  };

  render() {
    console.log('🛡️ [ErrorBoundary] Render called at:', new Date().toISOString(), 'hasError:', this.state.hasError);
    
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="h-full flex items-center justify-center bg-gray-50 p-4">
          <div className="text-center max-w-md">
            <AlertTriangle className="h-12 w-12 mx-auto mb-4 text-red-500" />
            <h2 className="text-lg font-semibold text-gray-900 mb-2">
              Component Error
            </h2>
            <p className="text-gray-600 mb-4">
              Something went wrong with the visual streaming component.
            </p>
            
            {this.state.error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4 text-left">
                <p className="text-sm text-red-800 font-medium mb-1">Error:</p>
                <p className="text-xs text-red-700 font-mono">
                  {this.state.error.message}
                </p>
              </div>
            )}
            
            <div className="flex gap-2 justify-center">
              <Button onClick={this.handleReset} variant="outline">
                <RefreshCw className="h-4 w-4 mr-2" />
                Try Again
              </Button>
              <Button 
                onClick={() => window.location.reload()} 
                variant="default"
              >
                Reload Page
              </Button>
            </div>
            
            <p className="text-xs text-gray-500 mt-4">
              If this problem persists, try refreshing the page or contact support.
            </p>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary; 