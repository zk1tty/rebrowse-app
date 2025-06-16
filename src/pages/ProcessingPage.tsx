import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Progress } from '@/components/ui/progress';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Loader2, CheckCircle2, XCircle, Brain, ArrowLeft } from 'lucide-react';
import { apiFetch } from '@/lib/api';
import '@/styles/brainAnimation.css';
import { useTheme } from '@/contexts/ThemeContext';

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

  // Debug logging
  console.log('🔍 [ProcessingPage] Component mounted with jobId:', jobId);
  console.log('🔍 [ProcessingPage] Current state:', { jobStatus, isPolling, error, isLoading });

  const pollJobStatus = async (id: string) => {
    try {
      console.log('🔍 [ProcessingPage] Polling job status for ID:', id);
      setIsLoading(true);
      
      const status = await apiFetch<JobStatus>(`/workflows/upload/${id}/status`, { auth: false });
      console.log('🔍 [ProcessingPage] Received status:', status);
      
      setJobStatus(status);
      setIsLoading(false);

      if (status.status === 'completed' && status.workflow_id) {
        console.log('🔍 [ProcessingPage] Job completed, redirecting to workflow:', status.workflow_id);
        setIsPolling(false);
        // Wait a moment to show completion, then redirect
        setTimeout(() => {
          navigate(`/wf/${status.workflow_id}`, { replace: true });
        }, 1500);
      } else if (status.status === 'failed') {
        console.log('🔍 [ProcessingPage] Job failed:', status.error);
        setIsPolling(false);
        setError(status.error || 'Processing failed');
      } else if (status.status === 'processing' || status.status === 'pending') {
        console.log('🔍 [ProcessingPage] Job still processing, will poll again in 2s');
        // Continue polling
        setTimeout(() => pollJobStatus(id), 2000);
      }
    } catch (err) {
      console.error('🔍 [ProcessingPage] Failed to poll job status:', err);
      setIsPolling(false);
      setIsLoading(false);
      setError(err instanceof Error ? err.message : 'Failed to check processing status');
    }
  };

  useEffect(() => {
    console.log('🔍 [ProcessingPage] useEffect triggered with jobId:', jobId, 'isPolling:', isPolling);
    
    if (!jobId) {
      console.error('🔍 [ProcessingPage] No jobId provided, redirecting to home');
      setError('No job ID provided');
      setIsLoading(false);
      return;
    }

    if (jobId && isPolling) {
      pollJobStatus(jobId);
    }
  }, [jobId, isPolling]);

  const handleRetry = () => {
    if (jobId) {
      console.log('🔍 [ProcessingPage] Retrying job:', jobId);
      setError(null);
      setIsPolling(true);
      setJobStatus({ status: 'pending' });
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

  const getStatusMessage = () => {
    switch (jobStatus.status) {
      case 'completed':
        return 'Processing completed! Redirecting to your workflow...';
      case 'failed':
        return error || 'Processing failed';
      case 'processing':
        return jobStatus.message || 'Processing your recording...';
      case 'pending':
      default:
        return 'Preparing to process your recording...';
    }
  };

  const formatTime = (seconds: number) => {
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds}s`;
  };

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
              {getStatusMessage()}
            </p>
          </div>

          {/* Progress Bar */}
          {(jobStatus.status === 'processing' || jobStatus.status === 'pending') && (
            <div className="space-y-2">
              <Progress 
                value={jobStatus.progress || 0} 
                className="w-full"
              />
              <div className={`flex justify-between text-xs ${
                theme === 'dark' ? 'text-gray-400' : 'text-gray-500'
              }`}>
                <span>{jobStatus.progress || 0}% complete</span>
                {jobStatus.estimated_remaining_seconds && (
                  <span>~{formatTime(jobStatus.estimated_remaining_seconds)} remaining</span>
                )}
              </div>
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