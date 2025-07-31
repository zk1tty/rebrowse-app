import { fetchClient, apiFetch, sessionApiFetch } from '../lib/api';
import {
  Workflow,
  WorkflowMetadata,
  inputFieldSchema,
} from '../types/workflow-layout.types';
import { z } from 'zod';

export interface WorkflowService {
  getWorkflows(): Promise<Workflow[]>;
  getWorkflowByName(name: string): Promise<any>;
  getPublicWorkflowById(id: string): Promise<any>;
  uploadWorkflow(recordingData: any, sessionToken?: string): Promise<{ job_id: string }>;
  getUploadStatus(jobId: string): Promise<any>;
  updateWorkflowMetadata(
    workflowId: string,
    metadata: WorkflowMetadata,
    sessionToken?: string
  ): Promise<any>;
  executeWorkflow(
    workflowId: string,
    inputFields: z.infer<typeof inputFieldSchema>[],
    sessionToken?: string,
    mode?: 'cloud-run' | 'local-run',
    visual?: boolean
  ): Promise<{
    success: boolean;
    task_id: string;
    workflow: string;
    log_position: number;
    message: string;
    mode: string;
    devtools_url?: string;
    visual_enabled?: boolean;
  }>;
  getWorkflowCategory(timestamp: number): string;
  addWorkflow(name: string, content: string): Promise<void>;
  deleteWorkflow(name: string): Promise<void>;
  buildWorkflow(name: string, prompt: string, workflow: any): Promise<any>;
  recordWorkflow(): Promise<any>;
  stopRecording(): Promise<any>;
  fetchWorkflowLogs(taskId: string, position: number): Promise<any>;
  cancelWorkflow(taskId: string): Promise<any>;
  updateWorkflow(
    workflowId: string,
    workflowData: any,
    sessionToken?: string
  ): Promise<any>;
  deleteStep(
    workflowId: string,
    stepIndex: number,
    sessionToken?: string
  ): Promise<{ success: boolean; error?: string }>;
}

class WorkflowServiceImpl implements WorkflowService {
  // Utility function to normalize workflow data
  private normalizeWorkflowData(workflow: any): any {
    return {
      ...workflow,
      steps: workflow.steps?.map((step: any) => ({
        // Ensure all required fields are present with proper defaults
        description: step.description ?? null,
        output: step.output ?? null,
        timestamp: step.timestamp ?? null,
        tabId: step.tabId ?? null,
        type: step.type,
        // Optional fields - only include if they exist
        ...(step.url !== undefined && { url: step.url }),
        ...(step.cssSelector !== undefined && { cssSelector: step.cssSelector }),
        ...(step.xpath !== undefined && { xpath: step.xpath }),
        ...(step.elementTag !== undefined && { elementTag: step.elementTag }),
        ...(step.elementText !== undefined && { elementText: step.elementText }),
        ...(step.selectedText !== undefined && { selectedText: step.selectedText }),
        ...(step.value !== undefined && { value: step.value }),
        ...(step.task !== undefined && { task: step.task }),
      })) || [],
      // Normalize input_schema to ensure required field is always boolean
      input_schema: workflow.input_schema?.map((input: any) => ({
        name: input.name,
        type: input.type,
        // Convert null required to false, ensure it's always boolean
        required: input.required === null ? false : Boolean(input.required),
        value: input.value ?? '',
      })) || []
    };
  }
  async getWorkflows(): Promise<Workflow[]> {
    const response = await fetchClient.GET('/api/workflows');

    const workflowNames = response.data?.workflows ?? [];

    // Fetch full workflow data for each workflow name
    const workflows = await Promise.all(
      workflowNames.map((name) => this.getWorkflowByName(name))
    );

    return workflows;
  }

  async getWorkflowByName(name: string): Promise<any> {
    const res = await fetchClient.GET('/api/workflows/{name}', {
      params: { path: { name } },
    });

    /** ------------------------------------------------------------------
     *  <openapi-fetch> puts the parsed JSON under `.data` in production
     *  bundles, but under `.body` when the client is built in dev / mock
     *  mode.  Accept either so the caller doesn't have to care.
     *  ------------------------------------------------------------------ */
    const data = (res as any).data ?? (res as any).body ?? null;

    if (!data) {
      console.error('[workflowService] 🛑 unexpected response shape', res);
      throw new Error('Failed to return data from server');
    }

    // Normalize the workflow data to ensure consistent schema
    return this.normalizeWorkflowData(data);
  }

  async getPublicWorkflowById(id: string): Promise<any> {
    try {
      // Since there's no direct /workflows/{id} endpoint, we need to:
      // 1. Fetch all public workflows from /workflows/
      // 2. Find the one with matching ID      
      const allWorkflows = await apiFetch<any[]>('/workflows/', { auth: false });
            
      if (!Array.isArray(allWorkflows)) {
        throw new Error('Invalid response format: expected array of workflows');
      }
      
      // Find the workflow with matching ID
      const targetWorkflow = allWorkflows.find((wf: any) => {
        // The workflow might have the ID in different places
        const workflowData = wf.json || wf;
        return wf.id === id || workflowData.id === id || 
               wf.name === id || workflowData.name === id;
      });
      
      if (!targetWorkflow) {
        throw new Error(`Workflow with ID "${id}" not found`);
      }      
      // Extract the actual workflow data from the nested structure
      const workflow = targetWorkflow.json || targetWorkflow;
      
      if (!workflow) {
        throw new Error('No workflow data found in response');
      }
      
      // Normalize the workflow data to match our Zod schema expectations
      const normalizedWorkflow = this.normalizeWorkflowData(workflow);
      
      return normalizedWorkflow;
    } catch (error) {
      console.error('[workflowService] Failed to fetch public workflow:', error);
      throw new Error('Failed to load public workflow');
    }
  }

  async uploadWorkflow(recordingData: any, sessionToken?: string): Promise<{ job_id: string }> {
    try {
      // If session token is provided, use session-based auth
      if (sessionToken) {
        const response = await apiFetch<{ job_id: string }>('/workflows/upload/session', {
          method: 'POST',
          body: JSON.stringify({
            ...recordingData,
            session_token: sessionToken
          }),
          auth: false
        });
        
        return response;
      } else {
        // Fallback to public upload (no auth)
        const response = await apiFetch<{ job_id: string }>('/workflows/upload', {
          method: 'POST',
          body: JSON.stringify(recordingData),
          auth: false
        });
        
        return response;
      }
    } catch (error) {
      console.error('[workflowService] Failed to upload workflow:', error);
      throw new Error('Failed to upload workflow');
    }
  }

  async getUploadStatus(jobId: string): Promise<any> {
    try {
      const status = await apiFetch<any>(`/workflows/upload/${jobId}/status`, { auth: false });
      return status;
    } catch (error) {
      console.error('[workflowService] Failed to get upload status:', error);
      throw new Error('Failed to get upload status');
    }
  }

  async updateWorkflowMetadata(
    workflowId: string,
    metadata: WorkflowMetadata,
    sessionToken?: string
  ): Promise<any> {
    // Use session-based API if session token is provided
    if (sessionToken) {
      try {
        const data = await apiFetch<{ success: boolean; error?: string }>(`/workflows/${workflowId}/metadata/session`, {
          method: 'PATCH',
          body: JSON.stringify({
            name: metadata.name,
            description: metadata.description,
            workflow_analysis: metadata.workflow_analysis,
            version: metadata.version,
            session_token: sessionToken
          }),
          auth: false
        });
        
        console.log('Response from updateWorkflowMetadata (session-based):', data);
        if (!data.success) {
          throw new Error(data.error || 'Failed to update workflow metadata');
        }
        
        return data;
      } catch (error) {
        console.error('Session-based updateWorkflowMetadata failed:', error);
        throw error;
      }
    }
    
    // Fallback to JWT-based API (legacy support)
    throw new Error('JWT-based workflow metadata updates are no longer supported. Please use session authentication.');
  }

  async updateWorkflow(
    workflowId: string,
    workflowData: any,
    sessionToken?: string
  ): Promise<any> {
    // Use session-based API if session token is provided
    if (sessionToken) {
      try {
        const data = await apiFetch<{ success: boolean; error?: string }>(`/workflows/${workflowId}/session`, {
          method: 'PATCH',
          body: JSON.stringify({
            workflow_data: workflowData,
            session_token: sessionToken
          }),
          auth: false
        });
        
        console.log('Response from updateWorkflow (session-based):', data);
        if (!data.success) {
          throw new Error(data.error || 'Failed to update workflow');
        }
        
        return data;
      } catch (error) {
        console.error('Session-based updateWorkflow failed:', error);
        throw error;
      }
    }
    
    // Fallback to JWT-based API (legacy support)
    throw new Error('JWT-based workflow updates are no longer supported. Please use session authentication.');
  }

  async deleteStep(workflowId: string, stepIndex: number, sessionToken?: string): Promise<any> {
    // Use session-based API if session token is provided
    if (sessionToken) {
      try {
        const data = await apiFetch<{ success: boolean; error?: string }>(`/workflows/${workflowId}/steps/${stepIndex}/session`, {
          method: 'DELETE',
          body: JSON.stringify({
            step_index: stepIndex,
            session_token: sessionToken
          }),
          auth: false
        });
        
        console.log('Response from deleteStep (session-based):', data);
        if (!data.success) {
          throw new Error(data.error || 'Failed to delete step');
        }
        
        return data;
      } catch (error) {
        console.error('Session-based deleteStep failed:', error);
        throw error;
      }
    }
    
    // Fallback to JWT-based API (legacy support) 
    throw new Error('JWT-based step deletion is no longer supported. Please use session authentication.');
  }

  async executeWorkflow(
    workflowId: string,
    inputFields: z.infer<typeof inputFieldSchema>[],
    sessionToken?: string,
    mode: 'cloud-run' | 'local-run' = 'cloud-run',
    visual: boolean = false
  ): Promise<{
    success: boolean;
    task_id: string;
    workflow: string;
    log_position: number;
    message: string;
    mode: string;
    devtools_url?: string;
    visual_enabled?: boolean;
    visual_streaming_enabled?: boolean;
    session_id?: string;
  }> {
    const inputs: any = {};
    inputFields.forEach((field) => {
      inputs[field.name] = field.value;
    });

    // Use session-based API if session token is provided
    if (sessionToken) {
      try {
        // Use the existing session endpoint for both regular and visual execution
        const endpoint = `/workflows/${workflowId}/execute/session`;
        
        const requestBody = {
          inputs,
          session_token: sessionToken,
          mode: mode,
          visual: visual,
          // ✅ Re-enabled: Backend visual streaming is now working!
          ...(visual && {
            visual_streaming: true,
            visual_quality: 'standard',
            visual_events_buffer: 1000
          })
        };

        console.debug('📤 [WorkflowService] Sending execution request:', {
          endpoint,
          workflowId,
          requestBody: {
            ...requestBody,
            session_token: sessionToken ? `${sessionToken.slice(0,8)}...` : null
          }
        });

        const data = await apiFetch<{
          success: boolean;
          task_id: string;
          workflow: string;
          log_position: number;
          message: string;
          mode: string;
          devtools_url?: string;
          visual_enabled?: boolean;
          visual_streaming_enabled?: boolean;
          session_id?: string;
        }>(endpoint, {
          method: 'POST',
          body: JSON.stringify(requestBody),
          auth: false
        });
        
        console.debug('📥 [WorkflowService] Response from executeWorkflow (session-based):', {
          success: data.success,
          task_id: data.task_id,
          workflow: data.workflow,
          mode: data.mode,
          visual_enabled: data.visual_enabled,
          visual_streaming_enabled: data.visual_streaming_enabled,
          session_id: data.session_id,
          message: data.message
        });
        return data;
      } catch (error) {
        console.error('Session-based executeWorkflow failed:', error);
        throw error;
      }
    }

    // Fallback to JWT-based API (legacy support)
    throw new Error('JWT-based workflow execution is no longer supported. Please use session authentication.');
  }

  async recordWorkflow(): Promise<any> {
    const response = await fetchClient.POST('/api/workflows/record', {
      body: undefined,
    });
    if (!response.data) {
      throw new Error('Failed to return data from server');
    }
    
    const data = response.data;
    if (!data.success) {
      throw new Error(data.error || 'Failed to record workflow');
    }
    
    return data;
  }

  async stopRecording(): Promise<any> {
    const response = await fetchClient.POST('/api/workflows/cancel-recording', {
      body: undefined,
    });
    if (!response.data) {
      throw new Error('Failed to return data from server');
    }
    
    const data = response.data;
    if (!data.success) {
      throw new Error(data.error || 'Failed to stop recording');
    }
    
    return data;
  }

  async buildWorkflow(
    name: string,
    prompt: string,
    workflow: any
  ): Promise<any> {
    const response = await fetchClient.POST(
      '/api/workflows/build-from-recording',
      {
        body: { name, prompt, workflow },
      }
    );
    
    // Handle HTTP errors (like 422 validation errors)
    if (!response.response.ok) {
      const status = response.response.status;
      const statusText = response.response.statusText;
      throw new Error(`Request failed with ${status} ${statusText}. Please check your workflow data.`);
    }
    
    if (!response.data) {
      throw new Error('Failed to return data from server');
    }
    
    const data = response.data;
    if (!data.success) {
      throw new Error(data.error || data.message || 'Failed to build workflow');
    }
    
    return data;
  }

  async addWorkflow(name: string, content: string): Promise<void> {
    const response = await fetchClient.POST('/api/workflows/add', {
      body: { name, content },
    });

    if (!response.data) {
      throw new Error('Failed to add workflow');
    }

    const data = response.data;
    if (!data.success) {
      throw new Error(data.error || 'Failed to add workflow');
    }
  }

  async deleteWorkflow(name: string): Promise<void> {
    const response = await fetchClient.DELETE('/api/workflows/{name}', {
      params: { path: { name } },
    });

    if (!response.data) {
      throw new Error('Failed to delete workflow');
    }

    const data = response.data;
    if (!data.success) {
      throw new Error(data.error || 'Failed to delete workflow');
    }
  }

  async fetchWorkflowLogs(taskId: string, position: number) {
    const response = await fetchClient.GET('/api/workflows/logs/{task_id}', {
      params: { path: { task_id: taskId }, query: { position } },
    });

    if (!response.data) {
      throw new Error('Failed to return data from server');
    }

    return response.data;
  }

  async cancelWorkflow(taskId: string) {
    const response = await fetchClient.POST(
      '/api/workflows/tasks/{task_id}/cancel',
      {
        params: { path: { task_id: taskId } },
      }
    );

    if (!response.data) {
      throw new Error('Failed to return data from server');
    }

    const data = response.data;
    if (!data?.success) {
      throw new Error(data.message || 'Failed to cancel workflow');
    }

    return data;
  }

  getWorkflowCategory(timestamp: number): string {
    const now = new Date();
    const lastRun = new Date(timestamp);

    const diff = now.getTime() - lastRun.getTime();
    const diffInDays = diff / (1000 * 60 * 60 * 24);

    if (diffInDays < 1 && lastRun.getDate() === now.getDate()) return 'today';
    if (diffInDays < 2) return 'yesterday';
    if (diffInDays < 7) return 'last-week';
    if (diffInDays < 30) return 'last-month';
    return 'older';
  }
}

export const workflowService = new WorkflowServiceImpl();
