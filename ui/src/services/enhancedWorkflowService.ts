import { apiFetch, sessionApiFetch } from '../lib/api';
import { 
  Workflow, 
  EnhancedWorkflow, 
  ExecutionStats, 
  RecentExecution, 
  PerformanceMetrics,
  ActiveExecution 
} from '../types/workflow-layout.types';
import { workflowService } from './workflowService';
import { hasValidWorkflowId, getWorkflowIdentifier } from '../utils/workflowValidation';

export class EnhancedWorkflowService {
  constructor(private sessionToken: string | null) {}

  /**
   * Fetch workflow with execution statistics
   */
  async getWorkflowWithStats(workflowId: string): Promise<EnhancedWorkflow> {
    try {
      // Fetch basic workflow data (using existing service)
      const workflow = await workflowService.getWorkflowByName(workflowId);
      
      if (!this.sessionToken) {
        // Return basic workflow if no session token
        return this.enrichWorkflowData(workflow, null, null);
      }

      // Only fetch stats if workflow has a valid UUID (id field)
      // The stats API requires a UUID, not a workflow name
      if (!hasValidWorkflowId(workflow)) {
        console.log(`Skipping stats for ${getWorkflowIdentifier(workflow)} - invalid or missing UUID`);
        return this.enrichWorkflowData(workflow, null, null);
      }

      // Use the workflow's UUID for stats API calls
      const statsWorkflowId = workflow.id;

      // Fetch execution statistics
      const stats = await apiFetch<ExecutionStats>(
        `/workflows/executions/stats/${statsWorkflowId}?session_token=${this.sessionToken}`
      ).catch((error) => {
        console.warn(`Failed to fetch stats for ${getWorkflowIdentifier(workflow)}:`, error);
        return null;
      });
      
      // Fetch recent execution history
      const recentExecutions = await sessionApiFetch<{ executions: RecentExecution[] }>(
        '/workflows/executions/history',
        {
          sessionToken: this.sessionToken,
          body: JSON.stringify({
            workflow_id: statsWorkflowId,
            page: 1,
            page_size: 5,
            status_filter: null
          })
        }
      ).catch((error) => {
        console.warn(`Failed to fetch execution history for ${getWorkflowIdentifier(workflow)}:`, error);
        return null;
      });
      
      return this.enrichWorkflowData(workflow, stats, recentExecutions);
    } catch (error) {
      console.error('Error fetching enhanced workflow data:', error);
      // Fallback to basic workflow data
      const workflow = await workflowService.getWorkflowByName(workflowId);
      return this.enrichWorkflowData(workflow, null, null);
    }
  }

  /**
   * Fetch all workflows with execution statistics
   */
  async getAllWorkflowsWithStats(): Promise<EnhancedWorkflow[]> {
    try {
      // Fetch all workflows using existing service
      const workflows = await workflowService.getWorkflows();
      
      if (!this.sessionToken) {
        // Return basic workflows if no session token
        return workflows.map(workflow => this.enrichWorkflowData(workflow, null, null));
      }

      // Fetch stats for each workflow in parallel
      const enrichedWorkflows = await Promise.all(
        workflows.map(async (workflow) => {
          try {
            // Only fetch stats if workflow has a valid UUID (id field)
            // The stats API requires a UUID, not a workflow name
            if (!hasValidWorkflowId(workflow)) {
              console.log(`Skipping stats for ${getWorkflowIdentifier(workflow)} - invalid or missing UUID`);
              return this.enrichWorkflowData(workflow, null, null);
            }
            
            const workflowId = workflow.id;
            
            const [stats, recentExecutions] = await Promise.all([
              apiFetch<ExecutionStats>(
                `/workflows/executions/stats/${workflowId}?session_token=${this.sessionToken}`
              ).catch((error) => {
                console.warn(`Failed to fetch stats for ${getWorkflowIdentifier(workflow)}:`, error);
                return null;
              }),
              
              sessionApiFetch<{ executions: RecentExecution[] }>(
                '/workflows/executions/history',
                {
                  sessionToken: this.sessionToken,
                  body: JSON.stringify({
                    workflow_id: workflowId,
                    page: 1,
                    page_size: 3
                  })
                }
              ).catch((error) => {
                console.warn(`Failed to fetch execution history for ${getWorkflowIdentifier(workflow)}:`, error);
                return null;
              })
            ]);
            
            return this.enrichWorkflowData(workflow, stats, recentExecutions);
          } catch (error) {
            // If stats fail, return workflow with default stats
            console.warn(`Failed to fetch stats for ${getWorkflowIdentifier(workflow)}:`, error);
            return this.enrichWorkflowData(workflow, null, null);
          }
        })
      );
      
      return enrichedWorkflows;
    } catch (error) {
      console.error('Error fetching enhanced workflows:', error);
      throw error;
    }
  }

  /**
   * Enrich workflow data with execution statistics
   */
  private enrichWorkflowData(
    workflow: Workflow, 
    stats: ExecutionStats | null, 
    executionHistory: { executions: RecentExecution[] } | null
  ): EnhancedWorkflow {
    const defaultStats: ExecutionStats = {
      total_executions: 0,
      successful_executions: 0,
      failed_executions: 0,
      success_rate: 0,
      average_execution_time: null,
      last_execution_at: null,
      visual_streaming_usage_rate: 0
    };

    const executionStats: ExecutionStats = stats ? {
      total_executions: stats.total_executions,
      successful_executions: stats.successful_executions,
      failed_executions: stats.failed_executions,
      success_rate: stats.total_executions > 0 
        ? (stats.successful_executions / stats.total_executions) * 100 
        : 0,
      average_execution_time: stats.average_execution_time,
      last_execution_at: stats.last_execution_at,
      visual_streaming_usage_rate: stats.visual_streaming_usage_rate || 0
    } : defaultStats;

    const recentExecutions = executionHistory?.executions || [];
    
    const performance = this.calculatePerformance(executionStats, recentExecutions);

    return {
      ...workflow,
      execution_stats: executionStats,
      recent_executions: recentExecutions,
      performance
    };
  }

  /**
   * Calculate performance indicators
   */
  private calculatePerformance(stats: ExecutionStats, recentExecutions: RecentExecution[]): PerformanceMetrics {
    const reliability_score = Math.round(stats.success_rate);
    
    // Calculate trend based on recent executions
    let trend: 'improving' | 'declining' | 'stable' = 'stable';
    if (recentExecutions.length >= 3) {
      const recent = recentExecutions.slice(0, 3);
      const successCount = recent.filter(e => e.status === 'completed').length;
      const successRate = (successCount / recent.length) * 100;
      
      if (successRate > stats.success_rate + 5) trend = 'improving';
      else if (successRate < stats.success_rate - 5) trend = 'declining';
    }

    return {
      trend,
      reliability_score,
      avg_execution_time_trend: 0 // Could be calculated with historical data
    };
  }

  /**
   * Get active executions for real-time updates
   */
  async getActiveExecutions(): Promise<Record<string, ActiveExecution>> {
    try {
      if (!this.sessionToken) {
        return {};
      }

      const response = await apiFetch<{ active_executions: Record<string, ActiveExecution> }>(
        `/workflows/executions/active?session_token=${this.sessionToken}`
      );
      return response.active_executions;
    } catch (error) {
      console.error('Error fetching active executions:', error);
      return {};
    }
  }

  /**
   * Update session token
   */
  updateSessionToken(sessionToken: string | null) {
    this.sessionToken = sessionToken;
  }
}

export const createEnhancedWorkflowService = (sessionToken: string | null) => {
  return new EnhancedWorkflowService(sessionToken);
}; 