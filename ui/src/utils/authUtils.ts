/**
 * Auth utilities for session token handling and workflow ownership
 * Supports UUID-based ownership with NULL legacy workflows (Option B)
 */

export interface OwnershipCheckResponse {
  is_owner: boolean;
  owner_id: string | null;
  is_legacy: boolean;
}

/**
 * Check if current user owns a workflow
 * Uses session-based authentication with query parameter
 * Based on working backend API: GET /workflows/{id}/ownership?session_token=TOKEN
 */
export const checkWorkflowOwnership = async (
  sessionToken: string, 
  workflowId: string
): Promise<boolean> => {
  try {
    console.log('🔐 [Auth] Checking ownership for workflow:', workflowId);
    console.log('🔐 [Auth] Session token type:', sessionToken.startsWith('eyJ') ? 'JWT' : 'Other');
    
    const API = import.meta.env.VITE_PUBLIC_API_URL;
    const url = `${API}/workflows/${workflowId}/ownership?session_token=${encodeURIComponent(sessionToken)}`;
    
    console.log('🔐 [Auth] Making ownership request to:', url.replace(sessionToken, '[TOKEN]'));
    
    const response = await fetch(url, {
      method: 'GET',
      headers: { 
        'Content-Type': 'application/json'
      }
    });
    
    console.log(`🔐 [Auth] Response status: ${response.status} ${response.statusText}`);
    
    if (response.ok) {
      const data: OwnershipCheckResponse = await response.json();
      console.log('🔐 [Auth] ✅ Ownership check successful:', data);
      return data.is_owner;
    } else {
      const errorText = await response.text();
      console.error(`🔐 [Auth] ❌ Ownership check failed: ${response.status} - ${errorText}`);
      
      if (response.status === 401) {
        console.log('🔐 [Auth] Unauthorized - invalid or expired session token');
      } else if (response.status === 404) {
        console.log('🔐 [Auth] Workflow not found');
      }
      
      return false;
    }
    
  } catch (error) {
    console.error('🔐 [Auth] Error checking ownership:', error);
    return false;
  }
};

/**
 * Get stored session token from sessionStorage
 */
export const getStoredSessionToken = (): string | null => {
  try {
    return sessionStorage.getItem('workflow_session_token');
  } catch (error) {
    console.error('🔐 [Auth] Error getting stored session token:', error);
    return null;
  }
};

/**
 * Check if user came from Chrome extension
 * @deprecated Use isFromExtension from extensionUtils instead
 */
export const isFromExtension = (): boolean => {
  try {
    return sessionStorage.getItem('from_extension') === 'true';
  } catch (error) {
    console.error('🔐 [Auth] Error checking extension origin:', error);
    return false;
  }
};

/**
 * Initialize session from Chrome extension (simplified)
 * This replaces complex JWT handling with simple session token storage
 */
export const initializeSessionFromExtension = (sessionToken: string): void => {
  try {
    storeSessionToken(sessionToken);
    console.log('🔐 [Auth] Session initialized from Chrome extension');
  } catch (error) {
    console.error('🔐 [Auth] Error initializing session from extension:', error);
  }
};

/**
 * Clear stored auth data
 */
export const clearStoredAuth = (): void => {
  try {
    sessionStorage.removeItem('workflow_session_token');
    sessionStorage.removeItem('workflow_auth_type');
    sessionStorage.removeItem('from_extension');
    console.log('🔐 [Auth] Cleared stored auth data');
  } catch (error) {
    console.error('🔐 [Auth] Error clearing auth data:', error);
  }
};

/**
 * Check if session token exists (simplified - no client-side validation)
 * Note: All validation is done by backend with Supabase
 */
export const hasValidSessionToken = (sessionToken: string | null): boolean => {
  // Simple existence check - backend will validate with Supabase
  return typeof sessionToken === 'string' && sessionToken.trim().length > 0;
};

/**
 * Store session token and mark auth type
 */
export const storeSessionToken = (sessionToken: string): void => {
  try {
    sessionStorage.setItem('workflow_session_token', sessionToken);
    sessionStorage.setItem('workflow_auth_type', 'session');
    sessionStorage.setItem('from_extension', 'true');
    console.log('🔐 [Auth] Session token stored successfully');
  } catch (error) {
    console.error('🔐 [Auth] Error storing session token:', error);
  }
};

/**
 * Get auth type from storage
 */
export const getAuthType = (): string | null => {
  try {
    return sessionStorage.getItem('workflow_auth_type');
  } catch (error) {
    console.error('🔐 [Auth] Error getting auth type:', error);
    return null;
  }
};

/**
 * Determine edit permissions (simplified logic)
 */
export const canEditWorkflow = (
  sessionToken: string | null,
  isOwner: boolean,
  isPublicWorkflow: boolean,
  isLegacyWorkflow: boolean = false
): boolean => {
  console.log('🔍 [canEditWorkflow] Input parameters:', {
    sessionToken: sessionToken ? `${sessionToken.slice(0,8)}...` : null,
    isOwner,
    isPublicWorkflow,
    isLegacyWorkflow
  });

  // No session token = no editing
  if (!hasValidSessionToken(sessionToken)) {
    console.log('🔍 [canEditWorkflow] Result: false (no valid session token)');
    return false;
  }
  
  // Owner can always edit their workflows
  if (isOwner) {
    console.log('🔍 [canEditWorkflow] Result: true (user is owner)');
    return true;
  }
  
  // Legacy workflows (owner_id = NULL) can be edited by any authenticated user
  if (isLegacyWorkflow) {
    console.log('🔍 [canEditWorkflow] Result: true (legacy workflow)');
    return true;
  }
  
  // Public workflows owned by others = read-only (fork required)
  if (isPublicWorkflow && !isOwner) {
    console.log('🔍 [canEditWorkflow] Result: false (public workflow, not owner)');
    return false;
  }
  
  // Private workflows = owner only
  const result = isOwner;
  console.log('🔍 [canEditWorkflow] Result:', result, '(private workflow, owner check)');
  return result;
}; 