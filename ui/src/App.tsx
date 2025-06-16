import { Toaster } from '@/components/ui/toaster';
import { Toaster as Sonner } from '@/components/ui/sonner';
import { TooltipProvider } from '@/components/ui/tooltip';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AppProvider } from './contexts/AppContext';
import { ThemeProvider } from './contexts/ThemeContext';
import Index from './pages/Index';
import WorkflowLoader from './pages/WorkflowLoader';
import ProcessingPage from './pages/ProcessingPage.tsx';
import NotFound from './pages/NotFound';
import { useExtensionIntegration } from './hooks/useExtensionIntegration';

const queryClient = new QueryClient();

// Extension Integration Wrapper Component
const ExtensionIntegrationWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isFromExtension, context, error } = useExtensionIntegration();
  
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

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <ThemeProvider>
        <AppProvider>
          <ExtensionIntegrationWrapper>
            <Toaster />
            <Sonner />
            <BrowserRouter>
              <Routes>
                <Route path="/" element={<Index />} />
                {/* TODO: remove workflows/:id from routes later */}
                <Route path="/workflows/:id" element={<WorkflowLoader />} />
                <Route path="/wf/processing/:jobId" element={<ProcessingPage />} />
                <Route path="/wf/:id" element={<WorkflowLoader />} />
                <Route path="*" element={<NotFound />} />
              </Routes>
            </BrowserRouter>
          </ExtensionIntegrationWrapper>
        </AppProvider>
      </ThemeProvider>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
