// components/WorkflowCategoryBlock.tsx
import React from 'react';
import { Separator } from '@/components/ui/separator';
import { WorkflowItem } from '@/components/WorkflowItem';
import { Workflow } from '@/types/workflow-layout.types';
import { useTheme } from '@/contexts/ThemeContext';

interface Props {
  label: string;
  workflows: Workflow[];
  onDeleteWorkflow: (workflowId: string) => void;
}

export const WorkflowCategoryBlock: React.FC<Props> = ({
  label,
  workflows,
  onDeleteWorkflow,
}) => {
  const { theme } = useTheme();
  
  if (!workflows || workflows.length === 0) return null;

  return (
    <>
      <div className="flex items-center justify-center px-4 py-3">
        <div className="flex items-center w-full">
          <Separator className="flex-1" />
          <span className={`px-3 text-xs font-medium ${
            theme === 'dark' 
              ? 'text-gray-400 bg-black' 
              : 'text-gray-500 bg-white'
          }`}>
            {label}
          </span>
          <Separator className="flex-1" />
        </div>
      </div>
      {workflows.map((workflow) => (
        <WorkflowItem
          key={`${workflow.name}-${workflow.version}`}
          workflow={workflow}
          onDeleteWorkflow={onDeleteWorkflow}
        />
      ))}
    </>
  );
};
