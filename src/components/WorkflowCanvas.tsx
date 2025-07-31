import React, { useCallback, useMemo, useRef } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  Edge,
  Node,
  MarkerType,
  ReactFlowInstance,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { WorkflowStepNode } from './WorkflowStepNode';
import { useAppContext } from '@/contexts/AppContext';
import { useTheme } from '@/contexts/ThemeContext';

const nodeTypes = {
  workflowStep: WorkflowStepNode,
};

export function WorkflowCanvas() {
  const { currentWorkflowData } = useAppContext();
  const { theme } = useTheme();
  const reactFlowInstanceRef = useRef<ReactFlowInstance | null>(null);

  const initialNodes: Node[] = useMemo(() => {
    if (!currentWorkflowData) {
      return [
        {
          id: 'placeholder',
          type: 'workflowStep',
          position: { x: 250, y: 200 },
          data: {
            label: 'Select a workflow to visualize',
            action: 'info',
            target: '',
            stepNumber: 1,
          },
        },
      ];
    }

    return currentWorkflowData.steps.map((step, index) => ({
      id: `step-${index + 1}`,
      type: 'workflowStep',
      position: { x: 100, y: 100 + index * 150 },
      data: {
        description: step.description,
        action: step.type,
        target: step.cssSelector,
        value: step.value,
        stepNumber: index + 1,
      },
    }));
  }, [currentWorkflowData]);

  const initialEdges: Edge[] = useMemo(() => {
    if (!currentWorkflowData) return [];

    return currentWorkflowData.steps.slice(0, -1).map((_, index) => ({
      id: `e-step-${index + 1}-step-${index + 2}`,
      source: `step-${index + 1}`,
      target: `step-${index + 2}`,
      type: 'smoothstep',
      markerEnd: { type: MarkerType.ArrowClosed },
    }));
  }, [currentWorkflowData]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  // Update nodes when currentWorkflowData changes
  React.useEffect(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
    requestAnimationFrame(() => {
      reactFlowInstanceRef.current?.fitView({ padding: 0.2 });
    });
  }, [currentWorkflowData, initialNodes, initialEdges, setNodes, setEdges]);

  // Theme-based styling
  const canvasStyle = {
    backgroundColor: theme === 'dark' ? '#000000' : '#f9fafb'
  };
  
  const backgroundClass = theme === 'dark' ? 'bg-black canvas-dots-dark' : 'bg-gray-50';
  const backgroundGridColor = theme === 'dark' ? '#333333' : '#e5e7eb';
  const controlsClass = theme === 'dark' 
    ? 'bg-gray-800 border border-gray-600 rounded-lg shadow-sm text-white' 
    : 'bg-white border border-gray-200 rounded-lg shadow-sm';
  const minimapClass = theme === 'dark'
    ? 'bg-gray-800 border border-gray-600 rounded-lg shadow-sm'
    : 'bg-white border border-gray-200 rounded-lg shadow-sm';

  return (
    <div className={`w-full h-full ${backgroundClass}`}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        onInit={(instance) => {
          reactFlowInstanceRef.current = instance;
        }}
        fitView
        style={canvasStyle}
        defaultViewport={{ x: 0, y: 0, zoom: 0 }}
      >
        <Background color={backgroundGridColor} gap={20} />
        <Controls className={controlsClass} />
        <MiniMap
          className={minimapClass}
          nodeColor={(node) => {
            // Enhanced colors for dark mode visibility
            if (node.data?.action === 'navigation') return theme === 'dark' ? '#60a5fa' : '#3b82f6';
            if (node.data?.action === 'click') return theme === 'dark' ? '#34d399' : '#10b981';
            if (node.data?.action === 'input') return theme === 'dark' ? '#fbbf24' : '#f59e0b';
            if (node.data?.action === 'key_press') return theme === 'dark' ? '#a78bfa' : '#8b5cf6';
            if (node.data?.action === 'agent') return theme === 'dark' ? '#9ca3af' : '#6b7280';
            if (node.data?.action === 'select_change') return theme === 'dark' ? '#22d3ee' : '#06b6d4';
            if (node.data?.action === 'clipboard_copy') return theme === 'dark' ? '#fb923c' : '#ea580c';
            if (node.data?.action === 'clipboard_paste') return theme === 'dark' ? '#f472b6' : '#db2777';
            return theme === 'dark' ? '#9ca3af' : '#6b7280';
          }}
        />
      </ReactFlow>
    </div>
  );
}
