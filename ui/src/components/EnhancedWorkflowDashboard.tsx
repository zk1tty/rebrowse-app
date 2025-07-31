import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { 
  BarChart3, 
  Clock, 
  CheckCircle, 
  XCircle, 
  Eye, 
  TrendingUp,
  Activity
} from 'lucide-react';
import { EnhancedWorkflow, ActiveExecution } from '@/types/workflow-layout.types';
import { useTheme } from '@/contexts/ThemeContext';

interface EnhancedWorkflowDashboardProps {
  workflows: EnhancedWorkflow[];
  activeExecutions: Record<string, ActiveExecution>;
}

export const EnhancedWorkflowDashboard: React.FC<EnhancedWorkflowDashboardProps> = ({
  workflows,
  activeExecutions
}) => {
  const { theme } = useTheme();

  // Calculate summary statistics
  const stats = React.useMemo(() => {
    const workflowsWithStats = workflows.filter(w => w.execution_stats && w.execution_stats.total_executions > 0);
    
    if (workflowsWithStats.length === 0) {
      return {
        totalWorkflows: workflows.length,
        activeExecutions: Object.keys(activeExecutions).length,
        avgSuccessRate: 0,
        avgExecutionTime: 0,
        totalExecutions: 0,
        visualStreamingUsage: 0
      };
    }

    const totalExecutions = workflowsWithStats.reduce((sum, w) => sum + (w.execution_stats?.total_executions || 0), 0);
    const totalSuccessful = workflowsWithStats.reduce((sum, w) => sum + (w.execution_stats?.successful_executions || 0), 0);
    const avgSuccessRate = totalExecutions > 0 ? (totalSuccessful / totalExecutions) * 100 : 0;
    
    const avgExecutionTime = workflowsWithStats.reduce((sum, w) => {
      return sum + (w.execution_stats?.average_execution_time || 0);
    }, 0) / workflowsWithStats.length;

    const avgVisualUsage = workflowsWithStats.reduce((sum, w) => {
      return sum + (w.execution_stats?.visual_streaming_usage_rate || 0);
    }, 0) / workflowsWithStats.length;

    return {
      totalWorkflows: workflows.length,
      activeExecutions: Object.keys(activeExecutions).length,
      avgSuccessRate,
      avgExecutionTime,
      totalExecutions,
      visualStreamingUsage: avgVisualUsage
    };
  }, [workflows, activeExecutions]);

  const formatTime = (seconds: number) => {
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    return `${(seconds / 60).toFixed(1)}m`;
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      {/* Total Workflows */}
      <Card className={theme === 'dark' ? 'bg-gray-900 border-gray-700' : ''}>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className={`text-sm font-medium ${
            theme === 'dark' ? 'text-gray-200' : 'text-gray-700'
          }`}>
            Total Workflows
          </CardTitle>
          <BarChart3 className="h-4 w-4 text-blue-600" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold text-blue-600">
            {stats.totalWorkflows}
          </div>
          <p className={`text-xs ${
            theme === 'dark' ? 'text-gray-400' : 'text-gray-500'
          }`}>
            Available workflows
          </p>
        </CardContent>
      </Card>

      {/* Active Executions */}
      <Card className={theme === 'dark' ? 'bg-gray-900 border-gray-700' : ''}>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className={`text-sm font-medium ${
            theme === 'dark' ? 'text-gray-200' : 'text-gray-700'
          }`}>
            Active Executions
          </CardTitle>
          <Activity className="h-4 w-4 text-green-600" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold text-green-600">
            {stats.activeExecutions}
          </div>
          <p className={`text-xs ${
            theme === 'dark' ? 'text-gray-400' : 'text-gray-500'
          }`}>
            Currently running
          </p>
        </CardContent>
      </Card>

      {/* Average Success Rate */}
      <Card className={theme === 'dark' ? 'bg-gray-900 border-gray-700' : ''}>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className={`text-sm font-medium ${
            theme === 'dark' ? 'text-gray-200' : 'text-gray-700'
          }`}>
            Avg Success Rate
          </CardTitle>
          <CheckCircle className="h-4 w-4 text-purple-600" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold text-purple-600">
            {stats.avgSuccessRate.toFixed(1)}%
          </div>
          <p className={`text-xs ${
            theme === 'dark' ? 'text-gray-400' : 'text-gray-500'
          }`}>
            Overall performance
          </p>
        </CardContent>
      </Card>

      {/* Visual Streaming Usage */}
      <Card className={theme === 'dark' ? 'bg-gray-900 border-gray-700' : ''}>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className={`text-sm font-medium ${
            theme === 'dark' ? 'text-gray-200' : 'text-gray-700'
          }`}>
            Visual Streaming
          </CardTitle>
          <Eye className="h-4 w-4 text-orange-600" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold text-orange-600">
            {stats.visualStreamingUsage.toFixed(1)}%
          </div>
          <p className={`text-xs ${
            theme === 'dark' ? 'text-gray-400' : 'text-gray-500'
          }`}>
            Usage rate
          </p>
        </CardContent>
      </Card>
    </div>
  );
};

export default EnhancedWorkflowDashboard; 