import { Toaster } from '@/components/ui/toaster';
import { Toaster as Sonner } from '@/components/ui/sonner';
import { TooltipProvider } from '@/components/ui/tooltip';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import React, { useCallback, memo } from 'react';
import { AppProvider } from './contexts/AppContext';
import { ThemeProvider } from './contexts/ThemeContext';
import Index from './pages/Index';
import WorkflowLoader from './pages/WorkflowLoader';
import ProcessingPage from './pages/ProcessingPage.tsx';
import NotFound from './pages/NotFound';
import DevToolsViewer from './components/DevToolsViewer';
import RRWebVisualizer from './components/RRWebVisualizer';
import VisualStreamingOverlay from './components/VisualStreamingOverlay';
import { useExtensionIntegration } from './hooks/useExtensionIntegration';
import { Analytics } from "@vercel/analytics/react";
import { useAppContext } from './contexts/AppContext';

const queryClient = new QueryClient();

// Extension Integration Wrapper Component
const ExtensionIntegrationWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { error } = useExtensionIntegration();
  
  return (
    <>
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 m-4">
          <p className="text-sm text-red-800">
            Extension integration error: {error}
          </p>
        </div>
      )}
      {children}
    </>
  );
};

// Overlay Wrapper Component (inside AppProvider) - FIXED: Memoized to prevent infinite re-renders
const OverlayWrapperComponent = memo<{ children: React.ReactNode }>(({ children }) => {
  const { 
    visualOverlayActive, 
    currentStreamingSession, 
    overlayWorkflowInfo,
    setVisualOverlayActive,
    setCurrentStreamingSession,
    setOverlayWorkflowInfo
  } = useAppContext();

  // FIXED: Memoize the callback to prevent recreation on every render
  const handleOverlayClose = useCallback(() => {
    console.log('🚪 [OverlayWrapper] Closing visual overlay...');
    setVisualOverlayActive(false);
    setCurrentStreamingSession(null);
    setOverlayWorkflowInfo(null);
  }, [setVisualOverlayActive, setCurrentStreamingSession, setOverlayWorkflowInfo]);

  return (
    <>
      {children}
      {visualOverlayActive && currentStreamingSession && overlayWorkflowInfo && (
        <VisualStreamingOverlay
          sessionId={currentStreamingSession}
          workflowInfo={overlayWorkflowInfo}
          isOpen={visualOverlayActive}
          onClose={handleOverlayClose}
        />
      )}
    </>
  );
});

// Enhanced memoization
const OverlayWrapper = memo(OverlayWrapperComponent, (prevProps, nextProps) => {
  return prevProps.children === nextProps.children;
});

// Add display name for debugging
OverlayWrapper.displayName = 'OverlayWrapper';

const App = () => {
  return (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <ThemeProvider>
        <AppProvider>
          <OverlayWrapper>
            <ExtensionIntegrationWrapper>
              <Toaster />
              <Sonner />
              <BrowserRouter>
                <Routes>
                  <Route path="/" element={<Index />} />
                  {/* 
                    LEGACY ROUTE: /workflows/:name (for private workflow sharing by name)
                    - Used for private workflow sharing when no ID available
                    - Used for backwards compatibility with existing bookmarks/links
                    - Can be removed when: all private workflows have IDs + migration period complete
                    - New sharing uses: /wf/{id} for both public and private workflows
                  */}
                  <Route path="/workflows/:name" element={<WorkflowLoader />} />
                  <Route path="/wf/processing/:jobId" element={<ProcessingPage />} />
                  <Route path="/wf/:id" element={<WorkflowLoader />} />
                  <Route path="/devtools/:taskId" element={<DevToolsViewer />} />
                  <Route path="/visual/:sessionId" element={<RRWebVisualizer />} />
                  <Route path="*" element={<NotFound />} />
                </Routes>
              </BrowserRouter>
            </ExtensionIntegrationWrapper>
          </OverlayWrapper>
        </AppProvider>
      </ThemeProvider>
    </TooltipProvider>
    <Analytics />
  </QueryClientProvider>
  );
};

export default App;
