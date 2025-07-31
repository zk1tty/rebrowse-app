import { useState, useEffect, useCallback, useRef } from 'react';
import { 
  getStoredSessionToken, 
  validateSessionToken, 
  clearStoredAuth,
  hasValidSessionToken 
} from '@/utils/authUtils';
import { useAppContext } from '@/contexts/AppContext';

interface SessionValidationState {
  isValid: boolean;
  isChecking: boolean;
  lastChecked: Date | null;
  error: string | null;
}

export const useSessionValidation = (intervalMs: number = 60000) => {
  const { setCurrentUserSessionToken, currentUserSessionToken } = useAppContext();
  const [state, setState] = useState<SessionValidationState>({
    isValid: false,
    isChecking: false,
    lastChecked: null,
    error: null
  });

  // Add validation lock to prevent concurrent validation calls
  const validationLock = useRef(false);
  
  const validateSession = useCallback(async () => {
    // Prevent concurrent validations
    if (validationLock.current) {
      return false;
    }
    
    validationLock.current = true;
    
    try {
      const storedToken = getStoredSessionToken();
      const contextToken = currentUserSessionToken; // Capture current value
      
      // Use the stored token for validation (most up-to-date)
      const tokenToValidate = storedToken;
      
      if (!hasValidSessionToken(tokenToValidate)) {
        setState(prev => ({
          ...prev,
          isValid: false,
          isChecking: false,
          lastChecked: new Date(),
          error: 'No session token found'
        }));
        
        // Clear context if it has a token but storage doesn't
        if (contextToken && !storedToken) {
          setCurrentUserSessionToken(null);
        }
        
        return false;
      }

      setState(prev => ({ ...prev, isChecking: true, error: null }));

      try {
        const isValid = await validateSessionToken(tokenToValidate!);
        
        setState(prev => ({
          ...prev,
          isValid,
          isChecking: false,
          lastChecked: new Date(),
          error: isValid ? null : 'Session token is invalid or expired'
        }));

        if (!isValid) {
          setCurrentUserSessionToken(null);
        } else {
          // Ensure context has the valid token (but only if different to avoid loops)
          // Also check if context is still different (in case another validation updated it)
          const currentContextToken = currentUserSessionToken;
          if (tokenToValidate !== currentContextToken) {
            setCurrentUserSessionToken(tokenToValidate);
          }
        }

        return isValid;
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Session validation failed';
        setState(prev => ({
          ...prev,
          isValid: false,
          isChecking: false,
          lastChecked: new Date(),
          error: errorMessage
        }));
        
        console.error('❌ [SessionValidation] Error:', error);
        return false;
      }
    } finally {
      validationLock.current = false;
    }
  }, [setCurrentUserSessionToken]); // REMOVED currentUserSessionToken dependency to break the loop

  // Periodic validation
  useEffect(() => {
    // Initial validation
    validateSession();

    // Set up interval for periodic validation
    const interval = setInterval(validateSession, intervalMs);

    return () => clearInterval(interval);
  }, [validateSession, intervalMs]);

  // Manual validation function
  const checkSession = useCallback(async (): Promise<boolean> => {
    return await validateSession();
  }, [validateSession]);

  return {
    ...state,
    checkSession,
    refreshSession: validateSession
  };
}; 