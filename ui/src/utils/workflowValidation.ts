/**
 * Workflow validation utilities
 */

/**
 * Validates if a workflow ID is safe to use with API endpoints
 */
export function isValidWorkflowId(workflowId: any): workflowId is string {
  return (
    workflowId &&
    typeof workflowId === 'string' &&
    workflowId !== 'undefined' &&
    workflowId !== 'null' &&
    workflowId.trim().length > 0
  );
}

/**
 * Validates if a workflow object has a valid ID for API calls
 */
export function hasValidWorkflowId(workflow: any): boolean {
  return workflow && isValidWorkflowId(workflow.id);
}

/**
 * Gets a safe workflow identifier for logging purposes
 */
export function getWorkflowIdentifier(workflow: any): string {
  if (!workflow) return 'unknown';
  if (workflow.name) return `${workflow.name}${workflow.id ? ` (${workflow.id})` : ''}`;
  if (workflow.id) return workflow.id;
  return 'unnamed workflow';
}

/**
 * Validates workflow data structure
 */
export function isValidWorkflow(workflow: any): boolean {
  return (
    workflow &&
    typeof workflow === 'object' &&
    typeof workflow.name === 'string' &&
    workflow.name.trim().length > 0
  );
} 