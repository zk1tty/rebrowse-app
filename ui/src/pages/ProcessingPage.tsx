import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Loader2, CheckCircle2, XCircle, Brain, ArrowLeft } from 'lucide-react';
import { apiFetch } from '@/lib/api';
import '@/styles/brainAnimation.css';
import { useTheme } from '@/contexts/ThemeContext';

// 🚀 LIVE STREAMING PROGRESS CONFIGURATION
const POLL_INTERVAL = 400; // 400ms for live feel (backend updates every 800ms)
const FAST_POLL_INTERVAL = 200; // Faster during active progress changes
const TIMEOUT_THRESHOLD = 45000; // 45 seconds timeout
const STALL_THRESHOLD = 10000; // 10 seconds without progress change

interface JobStatus {
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress?: number;
  estimated_remaining_seconds?: number;
  workflow_id?: string;
  error?: string;
  message?: string;
}

export default function ProcessingPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const { theme } = useTheme();
  const [jobStatus, setJobStatus] = useState<JobStatus>({ status: 'pending' });
  const [isPolling, setIsPolling] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [startTime] = useState(Date.now()); // Track when processing started
  const [lastProgressUpdate, setLastProgressUpdate] = useState(Date.now());
  const [progressHistory, setProgressHistory] = useState<number[]>([]);

  // Debug logging
  console.log('🔍 [ProcessingPage] Component mounted with jobId:', jobId);
  console.log('🔍 [ProcessingPage] Current state:', { jobStatus, isPolling, error, isLoading });

  // Dynamic status messages matching backend progress phases
  const getProgressMessage = (progress: number, status: string) => {
    if (status === 'completed') return '🎉 Workflow created successfully!';
    if (status === 'failed') return '❌ Processing failed';
    
    // Granular messages matching backend progress phases
    if (progress <= 10) return '🚀 Starting workflow conversion...';
    if (progress <= 20) return '🔧 Processing workflow structure...';
    if (progress <= 30) return '🧠 Analyzing user actions...';
    if (progress <= 40) return '⚡ Optimizing step sequence...';
    if (progress <= 50) return '✨ Generating smart naming...';
    if (progress <= 60) return '📋 Creating input schema...';
    if (progress <= 70) return '🎯 Finalizing workflow logic...';
    if (progress <= 80) return '✅ Conversion completed!';
    if (progress <= 85) return '💾 Starting database operations...';
    if (progress <= 90) return '🧹 Sanitizing content...';
    if (progress <= 95) return '📤 Saving to database...';
    if (progress < 100) return '🔄 Completing final steps...';
    return '✅ Processing complete!';
  };

  // Adaptive polling logic - detect if progress is actively changing
  const isProgressActive = () => {
    if (progressHistory.length < 2) return true;
    const recentChanges = progressHistory.slice(-3);
    return recentChanges.some((p, i) => i > 0 && p !== recentChanges[i-1]);
  };

  // Enhanced polling function with live streaming capabilities
  const pollJobStatus = useCallback(async (id: string, attempt: number = 0) => {
    try {
      console.log(`🔄 [Live Poll #${attempt}] Checking progress...`);
      
      const status = await apiFetch<JobStatus>(`/workflows/upload/${id}/status`, { auth: false });
      const currentTime = Date.now();
      const elapsedTime = currentTime - startTime;
      
      // Update progress history for trend analysis
      setProgressHistory(prev => [...prev.slice(-10), status.progress || 0]);
      
      // Detect progress changes
      const progressChanged = jobStatus.progress !== status.progress;
      if (progressChanged) {
        setLastProgressUpdate(currentTime);
        console.log(`📈 Progress updated: ${jobStatus.progress}% → ${status.progress}%`);
      }

      setJobStatus(status);
      setIsLoading(false);
      setError(null); // Clear any previous errors

      // Enhanced timeout detection
      const timeSinceLastProgress = currentTime - lastProgressUpdate;
      const isStalled = timeSinceLastProgress > STALL_THRESHOLD;
      const isTimedOut = elapsedTime > TIMEOUT_THRESHOLD;

      console.log(`⏱️ Timing: elapsed=${Math.round(elapsedTime/1000)}s, stalled=${Math.round(timeSinceLastProgress/1000)}s`);

      // Handle completion
      if (status.status === 'completed' && status.workflow_id) {
        console.log('🎉 Processing completed successfully!');
        setIsPolling(false);
        setTimeout(() => {
          navigate(`/wf/${status.workflow_id}`, { replace: true });
        }, 2000); // Show completion for 2 seconds
        return;
      }

      // Handle failures  
      if (status.status === 'failed') {
        console.log('❌ Processing failed:', status.error);
        setIsPolling(false);
        setError(status.error || 'Processing failed. Please try again.');
        return;
      }

      // Enhanced timeout handling
      if (isTimedOut || (isStalled && status.progress === 10)) {
        console.log('⏰ Processing timeout detected');
        setIsPolling(false);
        setError(
          isStalled 
            ? `Processing stalled at ${status.progress}%. This might be due to complex content or special characters.`
            : 'Processing is taking longer than expected. Please try again.'
        );
        return;
      }

      // Continue polling if still processing
      if (status.status === 'processing' || status.status === 'pending') {
        // 🚀 ADAPTIVE POLLING - faster when progress is actively changing
        const pollInterval = isProgressActive() ? FAST_POLL_INTERVAL : POLL_INTERVAL;
        
        console.log(`🔄 Continuing poll in ${pollInterval}ms (active: ${isProgressActive()})`);
        setTimeout(() => pollJobStatus(id, attempt + 1), pollInterval);
      }

    } catch (err) {
      console.error('🚨 Polling error:', err);
      
      // Exponential backoff for retries
      const maxRetries = 5;
      if (attempt < maxRetries) {
        const retryDelay = Math.min(1000 * Math.pow(2, attempt), 5000);
        console.log(`🔁 Retrying in ${retryDelay}ms (attempt ${attempt + 1}/${maxRetries})`);
        setTimeout(() => pollJobStatus(id, attempt + 1), retryDelay);
      } else {
        setIsPolling(false);
        setIsLoading(false);
        setError(err instanceof Error ? err.message : 'Connection error. Please check your network.');
      }
    }
  }, [
    jobStatus.progress,
    startTime,
    lastProgressUpdate,
    navigate,
    isProgressActive,
    setProgressHistory,
    setLastProgressUpdate,
    setJobStatus,
    setIsLoading,
    setError,
    setIsPolling
  ]);

  useEffect(() => {
    console.log('🔍 [ProcessingPage] useEffect triggered with jobId:', jobId, 'isPolling:', isPolling);
    
    if (!jobId) {
      console.error('🔍 [ProcessingPage] No jobId provided, redirecting to home');
      setError('No job ID provided');
      setIsLoading(false);
      return;
    }

    if (jobId && isPolling) {
      console.log('🚀 Starting live progress monitoring for job:', jobId);
      pollJobStatus(jobId);
    }
  }, [jobId, pollJobStatus]);

  const handleRetry = () => {
    if (jobId) {
      console.log('🔍 [ProcessingPage] Retrying job:', jobId);
      setError(null);
      setIsPolling(true);
      setJobStatus({ status: 'pending' });
      setProgressHistory([]);
      setLastProgressUpdate(Date.now());
      pollJobStatus(jobId);
    }
  };

  const handleBackToGallery = () => {
    console.log('🔍 [ProcessingPage] Navigating back to gallery');
    navigate('/', { replace: true });
  };

  const getStatusIcon = () => {
    switch (jobStatus.status) {
      case 'completed':
        return <CheckCircle2 className={`w-8 h-8 ${
          theme === 'dark' ? 'text-green-400' : 'text-green-500'
        }`} />;
      case 'failed':
        return <XCircle className={`w-8 h-8 ${
          theme === 'dark' ? 'text-red-400' : 'text-red-500'
        }`} />;
      case 'processing':
      case 'pending':
      default:
        return <Loader2 className={`w-8 h-8 animate-spin ${
          theme === 'dark' ? 'text-cyan-400' : 'text-blue-500'
        }`} />;
    }
  };



  const formatTime = (seconds: number) => {
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds}s`;
  };

  const progress = jobStatus.progress || 0;

  // Show error state if no jobId
  if (!jobId) {
    return (
      <div className={`min-h-screen flex items-center justify-center p-4 ${
        theme === 'dark' ? 'bg-black' : 'bg-gray-50'
      }`}>
        <Card className={`w-full max-w-md ${
          theme === 'dark' ? 'bg-gray-900 border-gray-700' : 'bg-white'
        }`}>
          <CardHeader className="text-center">
            <CardTitle className={`text-2xl ${
              theme === 'dark' ? 'text-red-400' : 'text-red-600'
            }`}>Error</CardTitle>
            <CardDescription className={
              theme === 'dark' ? 'text-gray-300' : 'text-gray-600'
            }>No job ID provided</CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={handleBackToGallery} className="w-full">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Gallery
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Show loading state initially
  if (isLoading && jobStatus.status === 'pending' && !error) {
    return (
      <div className={`min-h-screen flex items-center justify-center p-4 ${
        theme === 'dark' ? 'bg-black' : 'bg-gray-50'
      }`}>
        <Card className={`w-full max-w-md ${
          theme === 'dark' ? 'bg-gray-900 border-gray-700' : 'bg-white'
        }`}>
          <CardHeader className="text-center">
            <div className="flex justify-center mb-4">
              <Brain className={`w-20 h-20 brain-animation ${
                theme === 'dark' ? 'text-cyan-400' : 'text-purple-600'
              }`} />
            </div>
            <CardTitle className={`text-2xl ${
              theme === 'dark' ? 'text-white' : 'text-gray-900'
            }`}>Loading</CardTitle>
            <CardDescription className={
              theme === 'dark' ? 'text-gray-300' : 'text-gray-600'
            }>Connecting to processing service...</CardDescription>
          </CardHeader>
          <CardContent className="text-center">
            <Loader2 className={`w-8 h-8 animate-spin mx-auto mb-4 ${
              theme === 'dark' ? 'text-cyan-400' : 'text-blue-500'
            }`} />
            <p className={`text-sm ${
              theme === 'dark' ? 'text-gray-400' : 'text-gray-600'
            }`}>Job ID: {jobId}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className={`min-h-screen flex items-center justify-center p-4 ${
      theme === 'dark' ? 'bg-black' : 'bg-gray-50'
    }`}>
      <Card className={`w-full max-w-md ${
        theme === 'dark' ? 'bg-gray-900 border-gray-700' : 'bg-white'
      }`}>
        <CardHeader className="text-center">
          <div className="flex justify-center mb-4">
            <Brain className={`w-20 h-20 brain-animation ${
              theme === 'dark' ? 'text-cyan-400' : 'text-purple-600'
            }`} />
          </div>
          <CardTitle className={`text-2xl ${
            theme === 'dark' ? 'text-white' : 'text-gray-900'
          }`}>Processing</CardTitle>
        </CardHeader>

        <CardContent className="space-y-6">
          {/* Status Icon and Message */}
          <div className="text-center space-y-3">
            <div className="flex justify-center">
              {getStatusIcon()}
            </div>
            <p className={`text-sm ${
              theme === 'dark' ? 'text-gray-300' : 'text-gray-600'
            }`}>
              {getProgressMessage(progress, jobStatus.status)}
            </p>
          </div>

          {/* Live Activity Indicator */}
          {isPolling && jobStatus.status === 'processing' && (
            <div className="flex items-center justify-center mb-4">
              <div className="flex space-x-1">
                <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
              <span className="ml-3 text-sm text-gray-600 dark:text-gray-300">
                Live processing...
              </span>
            </div>
          )}

          {/* Enhanced Progress Bar with Animations */}
          {(jobStatus.status === 'processing' || jobStatus.status === 'pending') && (
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Progress
                </span>
                <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  {progress}%
                </span>
              </div>
              
              <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3 relative overflow-hidden">
                {/* Background shimmer for active processing */}
                {isPolling && jobStatus.status === 'processing' && (
                  <div 
                    className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-pulse"
                    style={{ animationDuration: '2s' }}
                  />
                )}
                
                {/* Main progress bar with smooth transitions */}
                <div
                  className="h-full rounded-full transition-all ease-out duration-300 bg-blue-600"
                  style={{ width: `${progress}%` }}
                />
                
                {/* Animated pulse for active progress */}
                {isPolling && progress > 0 && progress < 100 && (
                  <div
                    className="absolute top-0 h-full w-20 bg-gradient-to-r from-transparent via-white/40 to-transparent animate-pulse"
                    style={{
                      left: `${Math.max(0, progress - 10)}%`,
                      animationDuration: '1.5s'
                    }}
                  />
                )}
              </div>

              {/* Estimated time remaining */}
              {jobStatus.estimated_remaining_seconds && (
                <div className="text-center">
                  <span className={`text-xs ${
                    theme === 'dark' ? 'text-gray-400' : 'text-gray-500'
                  }`}>
                    ~{formatTime(jobStatus.estimated_remaining_seconds)} remaining
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Job ID */}
          <div className="text-center">
            <p className={`text-xs ${
              theme === 'dark' ? 'text-gray-500' : 'text-gray-400'
            }`}>
              Job ID: {jobId}
            </p>
          </div>

          {/* Debug Info (remove in production) */}
          <div className={`text-center p-2 rounded text-xs ${
            theme === 'dark' 
              ? 'bg-gray-800 text-gray-300' 
              : 'bg-gray-100 text-gray-700'
          }`}>
            <p>Debug: Status = {jobStatus.status}</p>
            <p>Debug: Polling = {isPolling ? 'Yes' : 'No'}</p>
            <p>Debug: Loading = {isLoading ? 'Yes' : 'No'}</p>
            {error && <p className={
              theme === 'dark' ? 'text-red-400' : 'text-red-600'
            }>Error: {error}</p>}
          </div>

          {/* Action Buttons */}
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={handleBackToGallery}
              className="flex-1"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Gallery
            </Button>

            {jobStatus.status === 'failed' && (
              <Button
                onClick={handleRetry}
                className="flex-1"
              >
                Retry
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
} 