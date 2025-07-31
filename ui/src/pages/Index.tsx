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
import { Welcome } from '@/components/Welcome';
import { Loader2, Terminal, ChevronRight, ChevronLeft, GripVertical, Footprints } from 'lucide-react';

const Index2 = () => {
  const { displayMode, workflowStatus, currentWorkflowData } = useAppContext();
  const { theme } = useTheme();
  const [showLogViewer, setShowLogViewer] = useState(false);
  
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
                      </div>
                    </div>
                  </div>
                )}

                {/* Canvas Area */}
                <div className="flex-1 flex overflow-hidden" ref={containerRef}>
                  {/* Main canvas area - now horizontal flex */}
                  <div className="relative flex-1 overflow-auto">
                    <WorkflowCanvas />
                    
                    {/* Toggle button - repositioned for right panel */}
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
                    } border-l border-gray-200 bg-white overflow-hidden transform transition-all duration-300 ease-in-out flex-shrink-0`}
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
        </div>

        {/* Dialogs */}
        <RunWorkflowDialog />
        <RunAsToolDialog />
      </div>
    </SidebarProvider>
  );
};

export default Index2;
