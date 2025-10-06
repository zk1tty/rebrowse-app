import { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import {
  MousePointerClick,
  Type,
  Navigation,
  Clock,
  Info,
  FileSearch,
  Copy,
  ClipboardPaste,
  ClipboardCopy,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTheme } from '@/contexts/ThemeContext';
import { CheckCircle2, XCircle, Bot, LoaderCircle } from 'lucide-react';

interface WorkflowStepNodeData {
  description: string;
  action:
    | 'navigation'
    | 'click'
    | 'select_change'
    | 'input'
    | 'agent'
    | 'key_press'
    | 'clipboard_copy'
    | 'clipboard_paste'
    | 'click_to_copy';
  target: string;
  value?: string;
  stepNumber: number;
  // Live status fields (optional - provided during runs)
  status?: 'ready' | 'running' | 'AI-fallback' | 'success' | 'fail';
  fallbackLabel?: string;
}

interface WorkflowStepNodeProps {
  data: WorkflowStepNodeData;
  selected?: boolean;
}

const actionIcons = {
  click: MousePointerClick,
  input: Type,
  navigation: Navigation,
  key_press: Clock,
  agent: Info,
  select_change: FileSearch,
  clipboard_copy: Copy,
  clipboard_paste: ClipboardPaste,
  click_to_copy: ClipboardCopy,
};

const actionColors = {
  click: 'bg-green-500',
  input: 'bg-amber-500',
  navigation: 'bg-blue-500',
  key_press: 'bg-purple-500',
  agent: 'bg-gray-500',
  select_change: 'bg-cyan-500',
  clipboard_copy: 'bg-orange-500',
  clipboard_paste: 'bg-pink-500',
  click_to_copy: 'bg-indigo-500',
};

export const WorkflowStepNode = memo(
  ({ data, selected }: WorkflowStepNodeProps) => {
    const { theme } = useTheme();
    const Icon = actionIcons[data.action] || Info; // Fallback to Info icon if action not found
    const colorClass = actionColors[data.action] || 'bg-gray-500'; // Fallback to gray if color not found

    return (
      <div
        className={cn(
          'relative rounded-lg border-2 shadow-sm p-4 w-[380px] h-[100px] transition-all',
          theme === 'dark' ? 'bg-gray-800 text-white' : 'bg-white text-gray-900',
          selected 
            ? 'border-purple-500 shadow-md' 
            : theme === 'dark' 
              ? 'border-gray-600' 
              : 'border-gray-200',
          'hover:shadow-md',
          data.status === 'running' && 'border-red-400 animate-pulse',
          data.status === 'AI-fallback' && 'border-yellow-400 animate-pulse',
          data.status === 'success' && 'border-green-500',
          data.status === 'fail' && 'border-red-600'
        )}
      >
        {data.stepNumber > 1 && (
          <Handle
            type="target"
            position={Position.Top}
            className={cn(
              "w-3 h-3 border-2",
              theme === 'dark' 
                ? "bg-gray-400 border-gray-800" 
                : "bg-gray-400 border-white"
            )}
          />
        )}

        <div className="flex items-start gap-3">
          <div className={cn('p-3 rounded-lg text-white shrink-0', colorClass)}>
            <Icon className="w-8 h-8" />
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              {data.stepNumber > 0 && (
                <span className={cn(
                  "text-xs font-medium px-2 py-1 rounded-full",
                  theme === 'dark'
                    ? "text-gray-300 bg-gray-700"
                    : "text-gray-500 bg-gray-100"
                )}>
                  Step {data.stepNumber}
                </span>
              )}
              <span className={cn(
                "text-xs font-medium px-2 py-1 rounded-full capitalize",
                theme === 'dark'
                  ? "bg-purple-800 text-purple-200"
                  : "bg-purple-100 text-purple-700"
              )}>
                {data.action}
              </span>
            </div>

            <h3 className={cn(
              "font-medium text-sm mb-2 break-words line-clamp-2",
              theme === 'dark' ? 'text-white' : 'text-gray-900'
            )}>
              {data.description || 'No description provided for this step'}
            </h3>
          </div>
        </div>

        {/* RunEvent Streaming: Event Status icon overlay */}
        {data.status && (
          <div className="absolute bottom-2 right-2 flex items-center gap-1">
            {data.status === 'running' && (
              <span className={cn(
                'flex items-center gap-1 text-xs px-2 py-1 rounded-full',
                theme === 'dark' ? 'bg-blue-900 text-blue-200' : 'bg-blue-100 text-blue-800'
              )}>
                <LoaderCircle className="w-6 h-6 animate-spin" />
              </span>
            )}
            {data.status === 'AI-fallback' && (
              <span className={cn(
                'flex items-center gap-1 text-xs px-2 py-1 rounded-full',
                theme === 'dark' ? 'bg-yellow-900 text-yellow-200' : 'bg-yellow-100 text-yellow-800'
              )}>
                <Bot className="w-8 h-8" />
                {data.fallbackLabel}
              </span>
            )}
            {data.status === 'success' && (
              <span className={cn(
                'flex items-center gap-1 text-xs px-2 py-1 rounded-full',
                theme === 'dark' ? 'bg-green-900 text-green-200' : 'bg-green-100 text-green-800'
              )}>
                <CheckCircle2 className="w-8 h-8" />
              </span>
            )}
            {data.status === 'fail' && (
              <span className={cn(
                'flex items-center gap-1 text-xs px-2 py-1 rounded-full',
                theme === 'dark' ? 'bg-red-900 text-red-200' : 'bg-red-100 text-red-800'
              )}>
                <XCircle className="w-8 h-8" />
              </span>
            )}
          </div>
        )}

        {data.stepNumber >= 0 && (
          <Handle
            type="source"
            position={Position.Bottom}
            className={cn(
              "w-3 h-3 border-2",
              theme === 'dark' 
                ? "bg-gray-400 border-gray-800" 
                : "bg-gray-400 border-white"
            )}
          />
        )}
      </div>
    );
  }
);

WorkflowStepNode.displayName = 'WorkflowStepNode';
