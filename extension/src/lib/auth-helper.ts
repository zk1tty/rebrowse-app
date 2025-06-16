/**
 * auth-helper.ts - Helper functions for proper token handling
 */

import { ensureAuth } from './auth';

/**
 * Makes an authenticated API request with proper token handling
 * This ensures the Authorization header is always attached with a fresh token
 */
export async function makeAuthenticatedRequest(
  url: string, 
  options: RequestInit = {}
): Promise<Response> {
  // Always get a fresh token - this handles refresh automatically
  const token = await ensureAuth();
  
  // Merge headers, ensuring Authorization is set
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
    Authorization: `Bearer ${token}`, // Always use fresh token
  };

  return fetch(url, {
    ...options,
    headers,
  });
}

/**
 * Alternative pattern for direct usage - ensures fresh session after auth
 */
export async function getAuthenticatedFetch(): Promise<{
  token: string;
  fetch: (url: string, options?: RequestInit) => Promise<Response>;
}> {
  const token = await ensureAuth();
  
  const authenticatedFetch = (url: string, options: RequestInit = {}) => {
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers,
      Authorization: `Bearer ${token}`,
    };
    
    return fetch(url, { ...options, headers });
  };
  
  return { token, fetch: authenticatedFetch };
}

/**
 * Corrected pattern for the issue you mentioned
 */
export async function getCorrectedAuthPattern(): Promise<string> {
  // ❌ WRONG PATTERN:
  // const { data } = await supabase.auth.getSession();
  // if (!data.session) await supabase.auth.signInWithOAuth({ provider: 'google' });
  // const token = data.session?.access_token; // Uses stale session data!
  
  // ✅ CORRECT PATTERN:
  // Always use ensureAuth() which handles the full flow and returns fresh token
  const token = await ensureAuth();
  
  return token;
} 