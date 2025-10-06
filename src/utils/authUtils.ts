/**
 * Auth utilities for session token handling and workflow ownership
 * Supports UUID-based ownership with NULL legacy workflows (Option B)
 */

import { API_BASE_URL } from '@/lib/constants';

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
    const url = `${API_BASE_URL}/workflows/${workflowId}/ownership?session_token=${encodeURIComponent(sessionToken)}`;
    
    const response = await fetch(url, {
      method: 'GET',
      headers: { 
        'Content-Type': 'application/json'
      }
    });
    
    if (response.ok) {
      const data: OwnershipCheckResponse = await response.json();
      return data.is_owner;
    } else {
      if (response.status !== 401 && response.status !== 404) {
        const errorText = await response.text();
        console.error(`❌ [Auth] Ownership check failed: ${response.status} - ${errorText}`);
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
  } catch (error) {
    console.error('❌ [Auth] Error initializing session from extension:', error);
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
  } catch (error) {
    console.error('❌ [Auth] Error clearing auth data:', error);
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
  } catch (error) {
    console.error('❌ [Auth] Error storing session token:', error);
  }
};

/**
 * Store anonymous session token and mark auth type
 */
export const storeAnonymousSessionToken = (sessionToken: string): void => {
  try {
    sessionStorage.setItem('workflow_session_token', sessionToken);
    sessionStorage.setItem('workflow_auth_type', 'anonymous');
  } catch (error) {
    console.error('❌ [Auth] Error storing anonymous session token:', error);
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
  // No session token = no editing
  if (!hasValidSessionToken(sessionToken)) {
    return false;
  }
  
  // Owner can always edit their workflows
  if (isOwner) {
    return true;
  }
  
  // Legacy workflows (owner_id = NULL) can be edited by any authenticated user
  if (isLegacyWorkflow) {
    return true;
  }
  
  // Public workflows owned by others = read-only (fork required)
  if (isPublicWorkflow && !isOwner) {
    return false;
  }
  
  // Private workflows = owner only
  return isOwner;
};

/**
 * Validate session token with backend
 * Makes a lightweight API call to check if the token is still valid
 */
export const validateSessionToken = async (sessionToken: string): Promise<boolean> => {
  try {
    // Safety check: Don't validate null, undefined, or empty tokens
    if (!sessionToken || typeof sessionToken !== 'string' || sessionToken.trim().length === 0) {
      return false;
    }
    
    // Safety check: Ensure API URL exists
    if (!API_BASE_URL) {
      console.error('❌ [Auth] API URL not configured');
      return false;
    }

    // Use a lightweight endpoint to validate the token
    const url = `${API_BASE_URL}/auth/validate?session_token=${encodeURIComponent(sessionToken)}`;
    
    const response = await fetch(url, {
      method: 'GET',
      headers: { 
        'Content-Type': 'application/json'
      }
    });
    
    const isValid = response.ok;
    
    // If invalid, clear the stored token unless it's an anonymous session
    if (!isValid) {
      const authType = getAuthType();
      if (authType !== 'anonymous') {
        clearStoredAuth();
      }
    }
    
    return isValid;
    
  } catch (error) {
    console.error('❌ [Auth] Error validating session token:', error);
    return false;
  }
};

/**
 * Check if session token exists and is valid with backend
 * Replaces the simple hasValidSessionToken for critical operations
 */
export const hasValidAndAuthenticatedSession = async (sessionToken: string | null): Promise<boolean> => {
  // First check if token exists
  if (!hasValidSessionToken(sessionToken)) {
    return false;
  }
  
  // Then validate with backend
  return await validateSessionToken(sessionToken!);
}; 

/**
 * Check if current user is an anonymous user
 */
export const isAnonymousUser = async (): Promise<boolean> => {
  try {
    // Use the existing supabase client from api/index.ts
    const { supabase } = await import('@/lib/api');
    
    if (!supabase) {
      console.warn('Supabase not configured, cannot check anonymous status');
      return false;
    }
    
    const { data: { session } } = await supabase.auth.getSession();
    
    if (!session?.user) {
      return false;
    }
    
    // Check if user is anonymous based on JWT claims or user metadata
    return session.user.is_anonymous === true;
  } catch (error) {
    console.error('Error checking anonymous user status:', error);
    return false;
  }
}; 