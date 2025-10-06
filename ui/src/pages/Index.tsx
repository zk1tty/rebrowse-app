import { useState, useRef, useCallback, useEffect } from 'react';
import { SidebarProvider } from '@/components/ui/sidebar';
import { WorkflowSidebar } from '@/components/WorkflowSidebar';
import { WorkflowCanvas } from '@/components/WorkflowCanvas';
import { WorkflowEditor } from '@/components/WorkflowEditor';
import { RunWorkflowDialog } from '@/components/RunWorkflowDialog';
import { RunAsToolDialog } from '@/components/RunAsToolDialog';
import { TopToolbar } from '@/components/TopToolbar';
import { useAppContext } from '@/contexts/AppContext';
import { useTheme } from '@/contexts/ThemeContext';
import { LogViewer } from '@/components/LogViewer';
import { VisualPanel } from '@/components/VisualPanel';
import { Welcome } from '@/components/Welcome';
import { Loader2, Terminal, ChevronRight, ChevronLeft, GripVertical, Footprints, Eye, XCircle } from 'lucide-react';
import { useAppContext as useAppContextRaw } from '@/contexts/AppContext';
import { useRunEventsWebSocket } from '@/hooks/useRunEventsWebSocket';
import { sessionApiFetch, apiFetch } from '@/lib/api';

const Index2 = () => {
  const { 
    displayMode, 
    workflowStatus, 
    currentWorkflowData,
    currentStreamingSession,
    overlayWorkflowInfo
  } = useAppContext();
  const { theme } = useTheme();
  const [showLogViewer, setShowLogViewer] = useState(false);
  const { currentUserSessionToken } = useAppContextRaw();
  const { currentRunId } = useAppContextRaw();
  useRunEventsWebSocket(currentRunId || undefined);
  
  // Initialize with stored width or default
  const [logPanelWidth, setLogPanelWidth] = useState(() => {
    try {
      const storedWidth = localStorage.getItem('logPanelWidth');
      return storedWidth ? parseInt(storedWidth, 10) : 384;
    } catch {
      return 384; // Default width (w-96 = 384px)
    }
  });
  
  const [isDragging, setIsDragging] = useState(false);
  const dragRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const [showVisualPanel, setShowVisualPanel] = useState(false);
  const [visualPanelWidth, setVisualPanelWidth] = useState(() => {
    try {
      const storedWidth = localStorage.getItem('visualPanelWidth');
      if (storedWidth) return parseInt(storedWidth, 10);
      // Default to half the container width; fallback to 600px
      const viewport = typeof window !== 'undefined' ? window.innerWidth : 1200;
      return Math.max(480, Math.floor(viewport * 0.5));
    } catch {
      return 600;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem('visualPanelWidth', visualPanelWidth.toString());
    } catch {}
  }, [visualPanelWidth]);

  const handleLeftMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return;
      const containerRect = containerRef.current.getBoundingClientRect();
      const newWidth = e.clientX - containerRect.left;
      const minWidth = 280;
      const maxWidth = containerRect.width * 0.6;
      const constrainedWidth = Math.max(minWidth, Math.min(maxWidth, newWidth));
      setVisualPanelWidth(constrainedWidth);
    };
    const handleMouseUp = () => {
      setIsDragging(false);
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, []);

  const handleLeftDoubleClick = useCallback(() => {
    setVisualPanelWidth(384);
  }, []);

  const toggleLogViewer = () => setShowLogViewer((prev) => !prev);

  // Save width to localStorage whenever it changes
  useEffect(() => {
    try {
      localStorage.setItem('logPanelWidth', logPanelWidth.toString());
    } catch (error) {
      console.log('📦 [Index] Could not save panel width to localStorage:', error);
    }
  }, [logPanelWidth]);

  // Drag functionality for resizing the log panel
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
    
    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return;
      
      const containerRect = containerRef.current.getBoundingClientRect();
      const newWidth = containerRect.right - e.clientX;
      
      // Set min and max constraints
      const minWidth = 280; // Minimum readable width
      const maxWidth = containerRect.width * 0.6; // Maximum 60% of container width
      
      const constrainedWidth = Math.max(minWidth, Math.min(maxWidth, newWidth));
      setLogPanelWidth(constrainedWidth);
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      
      console.log('📦 [Index] Log panel width saved:', logPanelWidth + 'px');
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, [logPanelWidth]);

  // Double-click to reset to default width
  const handleDoubleClick = useCallback(() => {
    const defaultWidth = 384;
    setLogPanelWidth(defaultWidth);
    console.log('📦 [Index] Log panel width reset to default:', defaultWidth + 'px');
  }, []);

  return (
    <SidebarProvider defaultOpen={true}>
      <div className="min-h-screen flex w-full bg-gray-50">
        {/* Sidebar */}
        <WorkflowSidebar />

        {/* Main Content Area */}
        <div className="flex-1 flex flex-col">
          <TopToolbar />

          <div className="flex-1 flex flex-col overflow-hidden">
            {displayMode === 'start' ? (
              <Welcome />
            ) : displayMode === 'canvas' ? (
              <div className="flex-1 flex flex-col overflow-hidden">
                {/* Workflow Title Header */}
                {currentWorkflowData && (
                  <div className={`border-b px-6 py-3 ${
                    theme === 'dark' 
                      ? 'bg-gray-900 border-gray-700' 
                      : 'bg-white border-gray-200'
                  }`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <div className={`w-2 h-2 rounded-full ${
                          workflowStatus === 'running' 
                            ? 'bg-green-500 animate-pulse' 
                            : 'bg-gray-400'
                        }`} />
                        <h1 className={`text-xl font-semibold ${
                          theme === 'dark' ? 'text-white' : 'text-gray-900'
                        }`}>
                          {currentWorkflowData.name}
                        </h1>
                        {currentWorkflowData.description && (
                          <p className={`text-sm ${
                            theme === 'dark' ? 'text-gray-400' : 'text-gray-600'
                          }`}>
                            {currentWorkflowData.description}
                          </p>
                        )}
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className={`text-xs px-2 py-1 rounded-full flex items-center space-x-1 ${
                          theme === 'dark' 
                            ? 'bg-gray-800 text-gray-300' 
                            : 'bg-gray-100 text-gray-600'
                        }`}>
                          <span>{currentWorkflowData.steps?.length || 0}</span>
                          <Footprints className="w-3 h-3" />
                        </span>
                        {/* Legacy overlay toggle removed */}
                        <button
                          type="button"
                          onClick={async () => {
                            try {
                              // Resolve active execution ID
                              let executionId: string | null = null;
                              if (currentUserSessionToken !== null && currentUserSessionToken !== undefined) {
                                const response = await apiFetch<{ active_executions: Record<string, any> }>(
                                  `/workflows/executions/active?session_token=${currentUserSessionToken}`,
                                  { auth: false }
                                );
                                const entries = Object.entries(((response as any)?.active_executions ?? {}) as Record<string, any>);
                                if (entries.length > 0) {
                                  const firstEntry = entries[0] as [string, any] | undefined;
                                  if (firstEntry && firstEntry[0]) {
                                    executionId = String(firstEntry[0]);
                                  }
                                }
                              }
                              if (!executionId) return;
                              const body = { mode: 'stop_then_kill' as const, timeout_ms: 5000, reason: 'user_requested_stop' };
                              await sessionApiFetch<any>(`/workflows/executions/${executionId}/terminate`, {
                                sessionToken: currentUserSessionToken || undefined,
                                body: JSON.stringify(body)
                              });
                            } catch (e) {
                              // Silent fail on UI button
                            }
                          }}
                          disabled={!currentStreamingSession || !overlayWorkflowInfo}
                          title="Terminate this execution"
                          className="justify-center whitespace-nowrap font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 border bg-background h-11 rounded-md flex items-center gap-2 text-base px-4 py-3 text-white border-gray-600 hover:bg-gray-800"
                        >
                          <XCircle className="w-5 h-5 text-red-600" />
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {/* Canvas Area */}
                <div className="flex-1 flex overflow-hidden" ref={containerRef}>
                  {/* Left visual panel: for live-streaming iframe */}
                  <VisualPanel 
                    isOpen={showVisualPanel}
                    width={visualPanelWidth}
                    sessionId={currentStreamingSession}
                    onResizeMouseDown={handleLeftMouseDown}
                    onResizeDoubleClick={handleLeftDoubleClick}
                  />

                  {/* Main canvas area - center */}
                  <div className="relative flex-1 overflow-auto">
                    <WorkflowCanvas />
                    
                    {/* Toggle buttons - left Visual, right Logs */}
                    <div className="absolute top-4 left-4">
                      <button
                        onClick={() => setShowVisualPanel(prev => !prev)}
                        className={`${
                          currentStreamingSession && overlayWorkflowInfo
                            ? 'bg-green-700 hover:bg-green-500'
                            : 'bg-gray-500 hover:bg-gray-600 cursor-not-allowed'
                        } text-white rounded-lg px-3 py-2 shadow-lg flex items-center transition-all duration-200 hover:shadow-xl`}
                        title="Toggle Visual Stream"
                        disabled={!currentStreamingSession || !overlayWorkflowInfo}
                      >
                        <div className="bg-white bg-opacity-20 rounded-full p-1.5 flex items-center justify-center mr-2">
                          {workflowStatus === 'running' ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <Eye className="w-4 h-4" />
                          )}
                        </div>
                        <span className="text-sm font-medium">Visual</span>
                        {showVisualPanel ? (
                          <ChevronLeft className="w-4 h-4 ml-2" />
                        ) : (
                          <ChevronRight className="w-4 h-4 ml-2" />
                        )}
                      </button>
                    </div>

                    <div className="absolute top-4 right-4">
                      <button
                        onClick={toggleLogViewer}
                        className={`${
                          workflowStatus === 'running'
                            ? 'bg-green-700 hover:bg-green-500'
                            : 'bg-gray-500 hover:bg-gray-600'
                        } text-white rounded-lg px-3 py-2 shadow-lg flex items-center transition-all duration-200 hover:shadow-xl`}
                        title="Toggle Execution Logs"
                      >
                        <div className="bg-white bg-opacity-20 rounded-full p-1.5 flex items-center justify-center mr-2">
                          {workflowStatus === 'running' ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <Terminal className="w-4 h-4" />
                          )}
                        </div>
                        <span className="text-sm font-medium">Logs</span>
                        {showLogViewer ? (
                          <ChevronRight className="w-4 h-4 ml-2" />
                        ) : (
                          <ChevronLeft className="w-4 h-4 ml-2" />
                        )}
                      </button>
                    </div>
                  </div>

                  {/* Draggable divider */}
                  {showLogViewer && (
                    <div
                      ref={dragRef}
                      className={`relative w-1 bg-gray-300 hover:bg-blue-400 cursor-col-resize flex items-center justify-center transition-all duration-200 ${
                        isDragging ? 'bg-blue-500 shadow-lg w-2' : ''
                      }`}
                      onMouseDown={handleMouseDown}
                      onDoubleClick={handleDoubleClick}
                      title="Drag to resize panel • Double-click to reset"
                    >
                      {/* Drag handle indicator */}
                      <div className={`absolute inset-y-0 w-4 flex items-center justify-center -translate-x-1.5 rounded transition-all duration-200 ${
                        isDragging ? 'bg-blue-500 bg-opacity-20 shadow-md' : 'hover:bg-gray-200 hover:bg-opacity-70'
                      }`}>
                        <GripVertical className={`w-3 h-3 text-gray-600 transition-colors duration-200 ${
                          isDragging ? 'text-blue-600' : ''
                        }`} />
                      </div>

                      {/* Width indicator tooltip during drag */}
                      {isDragging && (
                        <div className="absolute top-1/2 -translate-y-1/2 -left-16 bg-gray-900 text-white text-xs px-2 py-1 rounded shadow-lg z-50">
                          {Math.round(logPanelWidth)}px
                          <div className="absolute top-1/2 -translate-y-1/2 -right-1 w-2 h-2 bg-gray-900 rotate-45"></div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Right side Log panel - now with dynamic width */}
                  <div
                    className={`${
                      showLogViewer ? 'opacity-100' : 'opacity-0 w-0'
                    } border-l border-gray-200 bg-white overflow-hidden transform transition-all duration-300 ease-in-out flex-shrink-0 z-20`}
                    style={{
                      width: showLogViewer ? `${logPanelWidth}px` : '0px'
                    }}
                  >
                    <div className={`${showLogViewer ? 'opacity-100' : 'opacity-0'} h-full transition-opacity duration-300`}>
                      <LogViewer />
                    </div>
                  </div>
                </div>
              </div>
            ) : displayMode === 'editor' ? (
              <WorkflowEditor />
            ) : (
              <WorkflowCanvas />
            )}
          </div>

          {/* Dialogs */}
          <RunWorkflowDialog />
          <RunAsToolDialog />
        </div>
      </div>
    </SidebarProvider>
  );
};

export default Index2;
