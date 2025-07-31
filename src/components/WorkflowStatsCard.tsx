import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { 
  Clock, 
  CheckCircle, 
  XCircle, 
  Eye,
  BarChart3,
  TrendingUp,
  TrendingDown,
  Minus,
  Activity
} from 'lucide-react';
import { EnhancedWorkflow } from '@/types/workflow-layout.types';
import { useTheme } from '@/contexts/ThemeContext';

interface WorkflowStatsCardProps {
  workflow: EnhancedWorkflow;
  compact?: boolean;
  showRecentExecutions?: boolean;
}

export const WorkflowStatsCard: React.FC<WorkflowStatsCardProps> = ({
  workflow,
  compact = false,
  showRecentExecutions = false
}) => {
  const { theme } = useTheme();

  const formatExecutionTime = (seconds: number | null) => {
    if (!seconds) return 'N/A';
    return seconds < 60 ? `${seconds.toFixed(1)}s` : `${(seconds/60).toFixed(1)}m`;
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleDateString();
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'text-green-600 bg-green-100';
      case 'failed': return 'text-red-600 bg-red-100';
      case 'running': return 'text-blue-600 bg-blue-100';
      case 'cancelled': return 'text-gray-600 bg-gray-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getTrendIcon = (trend?: string) => {
    switch (trend) {
      case 'improving': return <TrendingUp className="w-4 h-4 text-green-600" />;
      case 'declining': return <TrendingDown className="w-4 h-4 text-red-600" />;
      default: return <Minus className="w-4 h-4 text-gray-600" />;
    }
  };

  const stats = workflow.execution_stats;
  const performance = workflow.performance;
  const recentExecutions = workflow.recent_executions || [];

  // If no execution stats, show a placeholder
  if (!stats || stats.total_executions === 0) {
    return (
      <Card className={`${theme === 'dark' ? 'bg-gray-900 border-gray-700' : ''} ${compact ? 'p-3' : ''}`}>
        <CardHeader className={compact ? 'pb-2' : ''}>
          <CardTitle className={`flex items-center gap-2 ${compact ? 'text-sm' : 'text-base'} ${
            theme === 'dark' ? 'text-gray-200' : 'text-gray-700'
          }`}>
            <BarChart3 className="w-4 h-4" />
            Workflow Statistics
          </CardTitle>
        </CardHeader>
        <CardContent className={compact ? 'pt-0' : ''}>
          <div className={`text-center py-4 ${
            theme === 'dark' ? 'text-gray-400' : 'text-gray-500'
          }`}>
            <Activity className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">No executions yet</p>
            <p className="text-xs mt-1">Run this workflow to see statistics</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={`${theme === 'dark' ? 'bg-gray-900 border-gray-700' : ''} ${compact ? 'p-3' : ''}`}>
      <CardHeader className={compact ? 'pb-2' : ''}>
        <div className="flex items-center justify-between">
          <CardTitle className={`flex items-center gap-2 ${compact ? 'text-sm' : 'text-base'} ${
            theme === 'dark' ? 'text-gray-200' : 'text-gray-700'
          }`}>
            <BarChart3 className="w-4 h-4" />
            Workflow Statistics
          </CardTitle>
          <div className="flex items-center gap-2">
            {getTrendIcon(performance?.trend)}
            <Badge variant="outline" className="text-xs">
              {performance?.reliability_score || 0}% reliable
            </Badge>
          </div>
        </div>
      </CardHeader>

      <CardContent className={compact ? 'pt-0' : ''}>
        <div className="space-y-4">
          {/* Key Metrics Grid */}
          <div className={`grid ${compact ? 'grid-cols-2' : 'grid-cols-2 md:grid-cols-4'} gap-4`}>
            <div className="text-center">
              <div className="text-lg font-bold text-blue-600">
                {stats.total_executions}
              </div>
              <div className={`text-xs ${theme === 'dark' ? 'text-gray-400' : 'text-gray-500'}`}>
                Total Runs
              </div>
            </div>

            <div className="text-center">
              <div className="text-lg font-bold text-green-600">
                {stats.successful_executions}
              </div>
              <div className={`text-xs ${theme === 'dark' ? 'text-gray-400' : 'text-gray-500'}`}>
                Successful
              </div>
            </div>

            {!compact && (
              <>
                <div className="text-center">
                  <div className="text-lg font-bold text-purple-600">
                    {formatExecutionTime(stats.average_execution_time)}
                  </div>
                  <div className={`text-xs ${theme === 'dark' ? 'text-gray-400' : 'text-gray-500'}`}>
                    Avg Time
                  </div>
                </div>

                <div className="text-center">
                  <div className="text-lg font-bold text-orange-600">
                    {stats.visual_streaming_usage_rate?.toFixed(0) || 0}%
                  </div>
                  <div className={`text-xs ${theme === 'dark' ? 'text-gray-400' : 'text-gray-500'}`}>
                    Visual Mode
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Success Rate Progress */}
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className={theme === 'dark' ? 'text-gray-300' : 'text-gray-600'}>
                Success Rate
              </span>
              <span className={`font-medium ${
                stats.success_rate >= 90 ? 'text-green-600' :
                stats.success_rate >= 70 ? 'text-yellow-600' : 'text-red-600'
              }`}>
                {stats.success_rate.toFixed(1)}%
              </span>
            </div>
            <Progress value={stats.success_rate} className="h-2" />
          </div>

          {/* Quick Stats Row */}
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-1">
                <CheckCircle className="w-4 h-4 text-green-600" />
                <span className={theme === 'dark' ? 'text-gray-300' : 'text-gray-600'}>
                  {stats.successful_executions}
                </span>
              </div>
              {stats.failed_executions > 0 && (
                <div className="flex items-center gap-1">
                  <XCircle className="w-4 h-4 text-red-600" />
                  <span className={theme === 'dark' ? 'text-gray-300' : 'text-gray-600'}>
                    {stats.failed_executions}
                  </span>
                </div>
              )}
              <div className="flex items-center gap-1">
                <Eye className="w-4 h-4 text-blue-600" />
                <span className={theme === 'dark' ? 'text-gray-300' : 'text-gray-600'}>
                  {stats.visual_streaming_usage_rate?.toFixed(0) || 0}%
                </span>
              </div>
            </div>
            
            <div className="flex items-center gap-1 text-xs">
              <Clock className="w-3 h-3 text-gray-500" />
              <span className={theme === 'dark' ? 'text-gray-400' : 'text-gray-500'}>
                Last: {formatDate(stats.last_execution_at)}
              </span>
            </div>
          </div>

          {/* Recent Executions */}
          {showRecentExecutions && recentExecutions.length > 0 && (
            <div className="space-y-2 pt-2 border-t">
              <h4 className={`text-sm font-medium ${
                theme === 'dark' ? 'text-gray-200' : 'text-gray-700'
              }`}>
                Recent Executions
              </h4>
              <div className="space-y-1">
                {recentExecutions.slice(0, 3).map((execution) => (
                  <div 
                    key={execution.execution_id}
                    className="flex items-center justify-between text-xs"
                  >
                    <div className="flex items-center gap-2">
                      <Badge 
                        variant="outline" 
                        className={`text-xs ${getStatusColor(execution.status)}`}
                      >
                        {execution.status}
                      </Badge>
                      <span className={theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}>
                        {formatDate(execution.created_at)}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      {execution.visual_streaming_enabled && (
                        <Eye className="w-3 h-3 text-blue-600" />
                      )}
                      <span className={theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}>
                        {formatExecutionTime(execution.execution_time_seconds)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

export default WorkflowStatsCard; 