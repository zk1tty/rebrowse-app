import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
  User, 
  Settings, 
  BarChart3, 
  Clock, 
  CheckCircle, 
  XCircle, 
  Eye,
  Activity,
  TrendingUp,
  Calendar,
  Download,
  Filter
} from 'lucide-react';
import EnhancedWorkflowDashboard from '@/components/EnhancedWorkflowDashboard';
import WorkflowStatsCard from '@/components/WorkflowStatsCard';
import { useAppContext } from '@/contexts/AppContext';
import { useTheme } from '@/contexts/ThemeContext';
import { hasValidSessionToken } from '@/utils/authUtils';

interface UserConsoleProps {
  onClose?: () => void;
}

export const UserConsole: React.FC<UserConsoleProps> = ({ onClose }) => {
  const { 
    workflows, 
    activeExecutions, 
    currentUserSessionToken 
  } = useAppContext();
  const { theme } = useTheme();
  const [selectedPeriod, setSelectedPeriod] = useState<'7d' | '30d' | '90d' | 'all'>('30d');

  const hasSessionToken = hasValidSessionToken(currentUserSessionToken);

  if (!hasSessionToken) {
    return (
      <div className={`min-h-screen flex items-center justify-center ${
        theme === 'dark' ? 'bg-gray-900' : 'bg-gray-50'
      }`}>
        <Card className={`max-w-md mx-auto ${
          theme === 'dark' ? 'bg-gray-800 border-gray-700' : ''
        }`}>
          <CardHeader className="text-center">
            <User className="w-12 h-12 mx-auto mb-4 text-gray-400" />
            <CardTitle className={theme === 'dark' ? 'text-white' : 'text-gray-900'}>
              Login Required
            </CardTitle>
          </CardHeader>
          <CardContent className="text-center">
            <p className={`mb-4 ${theme === 'dark' ? 'text-gray-300' : 'text-gray-600'}`}>
              Please login through the Chrome extension to access your workflow analytics.
            </p>
            {onClose && (
              <Button onClick={onClose} variant="outline">
                Go Back
              </Button>
            )}
          </CardContent>
        </Card>
      </div>
    );
  }

  // Calculate additional metrics
  const workflowsWithStats = workflows.filter(w => w.execution_stats && w.execution_stats.total_executions > 0);
  const totalExecutions = workflowsWithStats.reduce((sum, w) => sum + (w.execution_stats?.total_executions || 0), 0);
  const totalSuccessful = workflowsWithStats.reduce((sum, w) => sum + (w.execution_stats?.successful_executions || 0), 0);
  const avgExecutionTime = workflowsWithStats.length > 0 
    ? workflowsWithStats.reduce((sum, w) => sum + (w.execution_stats?.average_execution_time || 0), 0) / workflowsWithStats.length
    : 0;

  const formatTime = (seconds: number) => {
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    return `${(seconds / 60).toFixed(1)}m`;
  };

  return (
    <div className={`min-h-screen ${
      theme === 'dark' ? 'bg-gray-900' : 'bg-gray-50'
    }`}>
      <div className="max-w-7xl mx-auto p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className={`text-3xl font-bold ${
              theme === 'dark' ? 'text-white' : 'text-gray-900'
            }`}>
              <BarChart3 className="inline-block w-8 h-8 mr-3" />
              Analytics
            </h1>
            <p className={`text-lg ${
              theme === 'dark' ? 'text-gray-300' : 'text-gray-600'
            }`}>
              User analytics and management
            </p>
          </div>
          
          <div className="flex items-center gap-4">
            {/* Period Filter */}
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-gray-500" />
              <select 
                value={selectedPeriod}
                onChange={(e) => setSelectedPeriod(e.target.value as any)}
                className={`px-3 py-2 rounded border ${
                  theme === 'dark' 
                    ? 'bg-gray-800 border-gray-600 text-white' 
                    : 'bg-white border-gray-300'
                }`}
              >
                <option value="7d">Last 7 days</option>
                <option value="30d">Last 30 days</option>
                <option value="90d">Last 90 days</option>
                <option value="all">All time</option>
              </select>
            </div>

            {onClose && (
              <Button onClick={onClose} variant="outline">
                Close
              </Button>
            )}
          </div>
        </div>

        {/* Global Dashboard */}
        <div className="mb-8">
          <h2 className={`text-2xl font-semibold mb-4 ${
            theme === 'dark' ? 'text-white' : 'text-gray-900'
          }`}>
            Overview
          </h2>
          <EnhancedWorkflowDashboard 
            workflows={workflows} 
            activeExecutions={activeExecutions}
          />
        </div>

        {/* Additional Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <Card className={theme === 'dark' ? 'bg-gray-800 border-gray-700' : ''}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className={`text-sm font-medium ${
                theme === 'dark' ? 'text-gray-200' : 'text-gray-700'
              }`}>
                Total Executions
              </CardTitle>
              <Activity className="h-4 w-4 text-blue-600" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-blue-600">
                {totalExecutions}
              </div>
              <p className={`text-xs ${
                theme === 'dark' ? 'text-gray-400' : 'text-gray-500'
              }`}>
                Across all workflows
              </p>
            </CardContent>
          </Card>

          <Card className={theme === 'dark' ? 'bg-gray-800 border-gray-700' : ''}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className={`text-sm font-medium ${
                theme === 'dark' ? 'text-gray-200' : 'text-gray-700'
              }`}>
                Success Rate
              </CardTitle>
              <CheckCircle className="h-4 w-4 text-green-600" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600">
                {totalExecutions > 0 ? ((totalSuccessful / totalExecutions) * 100).toFixed(1) : 0}%
              </div>
              <p className={`text-xs ${
                theme === 'dark' ? 'text-gray-400' : 'text-gray-500'
              }`}>
                Overall performance
              </p>
            </CardContent>
          </Card>

          <Card className={theme === 'dark' ? 'bg-gray-800 border-gray-700' : ''}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className={`text-sm font-medium ${
                theme === 'dark' ? 'text-gray-200' : 'text-gray-700'
              }`}>
                Avg Execution Time
              </CardTitle>
              <Clock className="h-4 w-4 text-purple-600" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-purple-600">
                {formatTime(avgExecutionTime)}
              </div>
              <p className={`text-xs ${
                theme === 'dark' ? 'text-gray-400' : 'text-gray-500'
              }`}>
                Average duration
              </p>
            </CardContent>
          </Card>

          <Card className={theme === 'dark' ? 'bg-gray-800 border-gray-700' : ''}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className={`text-sm font-medium ${
                theme === 'dark' ? 'text-gray-200' : 'text-gray-700'
              }`}>
                Active Workflows
              </CardTitle>
              <TrendingUp className="h-4 w-4 text-orange-600" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-orange-600">
                {workflowsWithStats.length}
              </div>
              <p className={`text-xs ${
                theme === 'dark' ? 'text-gray-400' : 'text-gray-500'
              }`}>
                With execution history
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Individual Workflow Analytics */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className={`text-2xl font-semibold ${
              theme === 'dark' ? 'text-white' : 'text-gray-900'
            }`}>
              Workflow Performance
            </h2>
            <Button variant="outline" size="sm">
              <Download className="w-4 h-4 mr-2" />
              Export Data
            </Button>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {workflowsWithStats.map((workflow) => (
              <div key={workflow.id || workflow.name} className="space-y-2">
                <h3 className={`text-lg font-medium ${
                  theme === 'dark' ? 'text-white' : 'text-gray-900'
                }`}>
                  {workflow.name}
                </h3>
                <WorkflowStatsCard 
                  workflow={workflow} 
                  compact={true}
                  showRecentExecutions={false}
                />
              </div>
            ))}
          </div>

          {workflowsWithStats.length === 0 && (
            <Card className={theme === 'dark' ? 'bg-gray-800 border-gray-700' : ''}>
              <CardContent className="text-center py-12">
                <BarChart3 className={`w-12 h-12 mx-auto mb-4 ${
                  theme === 'dark' ? 'text-gray-400' : 'text-gray-400'
                }`} />
                <h3 className={`text-lg font-medium mb-2 ${
                  theme === 'dark' ? 'text-white' : 'text-gray-900'
                }`}>
                  No Workflow Data Yet
                </h3>
                <p className={`text-sm ${
                  theme === 'dark' ? 'text-gray-400' : 'text-gray-500'
                }`}>
                  Execute some workflows to see detailed analytics here.
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
};

export default UserConsole; 