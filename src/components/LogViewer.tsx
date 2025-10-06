import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useAppContext } from '@/contexts/AppContext';
import { Button } from '@/components/ui/button';
import { 
  Terminal, 
  Play, 
  Download, 
  Copy, 
  Loader2,
  AlertCircle,
  CheckCircle,
  XCircle
} from 'lucide-react';
import { useTheme } from '@/contexts/ThemeContext';
import { VariableSizeList as List, ListOnScrollProps } from 'react-window';

export const LogViewer: React.FC = () => {
  const {
    logData,
    workflowStatus,
    workflowError,
    currentTaskId,
    cancelWorkflowExecution,
  } = useAppContext();
  const { theme } = useTheme();
  const logContainerRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<List>(null);
  const rowHeightsRef = useRef<Record<number, number>>({});
  const [autoScroll, setAutoScroll] = useState(true);
  const [containerHeight, setContainerHeight] = useState<number>(400);

  // Custom scroll outer element for themed scrollbar (stable across renders)
  const OuterElement = useMemo(() => (
    React.forwardRef<HTMLDivElement, any>(function Outer(props, ref) {
      const cls = `${props.className ?? ''} overscroll-contain ${theme === 'dark' ? 'scrollbar-dark' : 'scrollbar-light'}`.trim();
      return <div {...props} ref={ref} className={cls} />;
    })
  ), [theme]);

  const defaultRowHeight = 22;
  const getItemSize = useCallback((index: number) => {
    return rowHeightsRef.current[index] ?? defaultRowHeight;
  }, []);

  const setRowHeight = useCallback((index: number, size: number) => {
    const current = rowHeightsRef.current[index];
    if (current !== size) {
      rowHeightsRef.current[index] = size;
      // Recalculate from the changed row to keep offsets in sync (prevents big gaps)
      listRef.current?.resetAfterIndex(index, true);
    }
  }, []);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (listRef.current && autoScroll && logData.length > 0) {
      // Use requestAnimationFrame to avoid layout thrash that can cause flicker
      const id = requestAnimationFrame(() => {
        listRef.current?.scrollToItem(logData.length - 1, 'smart');
      });
      return () => cancelAnimationFrame(id);
    }
  }, [logData.length, autoScroll]);

  // Track container height with ResizeObserver
  useEffect(() => {
    const el = logContainerRef.current;
    if (!el) return;
    const update = () => setContainerHeight(el.clientHeight || 400);
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const handleCopyLogs = () => {
    const logsText = logData.join('\n');
    navigator.clipboard.writeText(logsText);
  };

  const handleDownloadLogs = () => {
    const logsText = logData.join('\n');
    const blob = new Blob([logsText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `workflow-logs-${new Date().toISOString().slice(0, 19)}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleCancelWorkflow = () => {
    if (currentTaskId) {
      cancelWorkflowExecution(currentTaskId);
    }
  };

  const getStatusIcon = () => {
    switch (workflowStatus) {
      case 'running':
        return <Loader2 className="w-4 h-4 animate-spin text-blue-500" />;
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-500" />;
      case 'cancelled':
        return <AlertCircle className="w-4 h-4 text-yellow-500" />;
      default:
        return <Terminal className="w-4 h-4 text-gray-500" />;
    }
  };

  const getStatusText = () => {
    switch (workflowStatus) {
      case 'running':
        return 'Running...';
      case 'completed':
        return 'Completed';
      case 'failed':
        return 'Failed';
      case 'cancelled':
        return 'Cancelled';
      default:
        return 'Ready';
    }
  };

  return (
    <div className={`h-full flex flex-col ${
      theme === 'dark' 
        ? 'bg-gray-900 border-gray-700' 
        : 'bg-white border-gray-200'
    }`}>
      {/* Header */}
      <div className={`p-4 border-b flex items-center justify-between ${
        theme === 'dark' ? 'border-gray-700' : 'border-gray-200'
      }`}>
        <div className="flex items-center space-x-3">
          {getStatusIcon()}
          <div>
            <h3 className={`font-semibold text-sm ${
              theme === 'dark' ? 'text-white' : 'text-gray-900'
            }`}>
              Workflow Execution Logs
            </h3>
            <p className={`text-xs ${
              theme === 'dark' ? 'text-gray-400' : 'text-gray-500'
            }`}>
              Status: {getStatusText()}
            </p>
          </div>
        </div>
        <div className="flex items-center space-x-1">
          {workflowStatus === 'running' && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleCancelWorkflow}
              className="text-red-600 hover:text-red-700 hover:bg-red-50 p-2"
              title="Cancel workflow"
            >
              <XCircle className="w-3 h-3" />
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={handleCopyLogs}
            className={`${
              theme === 'dark' 
                ? 'text-gray-300 hover:text-white hover:bg-gray-800' 
                : 'text-gray-600 hover:text-gray-800 hover:bg-gray-100'
            } p-2`}
            title="Copy logs"
          >
            <Copy className="w-3 h-3" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleDownloadLogs}
            className={`${
              theme === 'dark' 
                ? 'text-gray-300 hover:text-white hover:bg-gray-800' 
                : 'text-gray-600 hover:text-gray-800 hover:bg-gray-100'
            } p-2`}
            title="Download logs"
          >
            <Download className="w-3 h-3" />
          </Button>
        </div>
      </div>

      {/* Log content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {workflowError && (
          <div className="p-3 bg-red-50 border-b border-red-200">
            <div className="flex items-start space-x-2">
              <XCircle className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-sm font-medium text-red-800">Error</p>
                <p className="text-xs text-red-600 mt-1">{workflowError}</p>
              </div>
            </div>
          </div>
        )}

        <div 
          ref={logContainerRef}
          className={`flex-1 overflow-hidden p-0 font-mono text-xs leading-relaxed ${
            theme === 'dark' 
              ? 'bg-gray-900 text-gray-300' 
              : 'bg-gray-50 text-gray-800'
          }`}
        >
          {logData.length === 0 ? (
            <div className={`flex items-center justify-center h-full ${
              theme === 'dark' ? 'text-gray-500' : 'text-gray-400'
            }`}>
              <div className="text-center">
                <Terminal className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm">No logs yet</p>
                <p className="text-xs mt-1">Workflow execution logs will appear here</p>
              </div>
            </div>
          ) : (
            <List
              ref={listRef}
              outerElementType={OuterElement}
              height={containerHeight}
              width={'100%'}
              itemCount={logData.length}
              itemSize={getItemSize}
              itemKey={(index: number) => index}
              onScroll={({ scrollOffset }: ListOnScrollProps) => {
                // Determine near-bottom by comparing offset to total height
                const totalHeight = logData.reduce((sum, _, idx) => sum + (rowHeightsRef.current[idx] ?? defaultRowHeight), 0);
                const maxOffset = Math.max(0, totalHeight - containerHeight);
                const distance = maxOffset - scrollOffset;
                setAutoScroll(distance < 4);
              }}
              style={{
                // Prevent outer page from scrolling
                overflowX: 'hidden'
              }}
            >
              {({ index, style }: { index: number; style: React.CSSProperties }) => {
                return (
                  <Row
                    index={index}
                    style={style}
                    text={String(logData[index] ?? '')}
                    theme={theme}
                    setRowHeight={setRowHeight}
                  />
                );
              }}
            </List>
          )}
        </div>

        {/* Auto-scroll indicator */}
        {!autoScroll && (
          <div className="p-2 border-t border-gray-200">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setAutoScroll(true);
                if (logContainerRef.current) {
                  logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
                }
              }}
              className="w-full text-xs"
            >
              <Play className="w-3 h-3 mr-1" />
              Resume auto-scroll
            </Button>
          </div>
        )}
      </div>
    </div>
  );
};

type RowProps = {
  index: number;
  style: React.CSSProperties;
  text: string;
  theme: string | undefined;
  setRowHeight: (index: number, size: number) => void;
};

const Row: React.FC<RowProps> = ({ index, style, text, theme, setRowHeight }) => {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    const el = ref.current;
    const measure = () => {
      const size = Math.ceil(el.getBoundingClientRect().height);
      if (Number.isFinite(size) && size > 0) {
        setRowHeight(index, size);
      }
    };
    // Measure now and on next frame to account for font/layout settle
    measure();
    const id = requestAnimationFrame(measure);
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => {
      cancelAnimationFrame(id);
      ro.disconnect();
    };
  }, [index, setRowHeight, text]);

  return (
    <div style={style}>
      <div
        ref={ref}
        className={`px-4 py-0.5 w-full whitespace-pre-wrap break-words ${
          (theme || 'light') === 'dark' ? 'text-gray-300' : 'text-gray-700'
        }`}
      >
        {text}
      </div>
    </div>
  );
};
