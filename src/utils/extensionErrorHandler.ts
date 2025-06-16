/**
 * Extension-specific error handling utilities
 * Provides better error messages and recovery for Chrome extension scenarios
 */

import { detectExtensionContext, sendMessageToExtension } from './extensionUtils';

export interface ExtensionError {
  type: 'EXTENSION_ERROR';
  code: string;
  message: string;
  originalError?: any;
  context?: any;
  recoverable?: boolean;
  recoveryAction?: string;
}

export const ExtensionErrorCodes = {
  // Permission errors
  MISSING_TABS_PERMISSION: 'MISSING_TABS_PERMISSION',
  MISSING_STORAGE_PERMISSION: 'MISSING_STORAGE_PERMISSION',
  
  // Communication errors
  MESSAGE_SEND_FAILED: 'MESSAGE_SEND_FAILED',
  MESSAGE_TIMEOUT: 'MESSAGE_TIMEOUT',
  EXTENSION_DISCONNECTED: 'EXTENSION_DISCONNECTED',
  
  // Authentication errors
  SESSION_TOKEN_MISSING: 'SESSION_TOKEN_MISSING',
  SESSION_TOKEN_INVALID: 'SESSION_TOKEN_INVALID',
  AUTH_CONTEXT_MISMATCH: 'AUTH_CONTEXT_MISMATCH',
  
  // Upload errors
  UPLOAD_IN_EXTENSION_FAILED: 'UPLOAD_IN_EXTENSION_FAILED',
  NAVIGATION_BLOCKED: 'NAVIGATION_BLOCKED',
  
  // General errors
  EXTENSION_CONTEXT_LOST: 'EXTENSION_CONTEXT_LOST',
  UNKNOWN_EXTENSION_ERROR: 'UNKNOWN_EXTENSION_ERROR'
} as const;

/**
 * Create an extension-specific error
 */
export const createExtensionError = (
  code: string,
  message: string,
  originalError?: any,
  context?: any
): ExtensionError => {
  const recoverable = isRecoverableError(code);
  const recoveryAction = getRecoveryAction(code);
  
  return {
    type: 'EXTENSION_ERROR',
    code,
    message,
    originalError,
    context,
    recoverable,
    recoveryAction
  };
};

/**
 * Check if an error is recoverable
 */
const isRecoverableError = (code: string): boolean => {
  const recoverableErrors = [
    ExtensionErrorCodes.MESSAGE_TIMEOUT,
    ExtensionErrorCodes.SESSION_TOKEN_MISSING,
    ExtensionErrorCodes.NAVIGATION_BLOCKED,
    ExtensionErrorCodes.UPLOAD_IN_EXTENSION_FAILED
  ];
  
  return recoverableErrors.includes(code as any);
};

/**
 * Get recovery action for an error
 */
const getRecoveryAction = (code: string): string | undefined => {
  const recoveryActions: Record<string, string> = {
    [ExtensionErrorCodes.MISSING_TABS_PERMISSION]: 'Grant tabs permission to the extension',
    [ExtensionErrorCodes.MISSING_STORAGE_PERMISSION]: 'Grant storage permission to the extension',
    [ExtensionErrorCodes.MESSAGE_TIMEOUT]: 'Retry the operation',
    [ExtensionErrorCodes.SESSION_TOKEN_MISSING]: 'Re-authenticate through the extension',
    [ExtensionErrorCodes.NAVIGATION_BLOCKED]: 'Allow popups for this site',
    [ExtensionErrorCodes.UPLOAD_IN_EXTENSION_FAILED]: 'Try uploading again or use web interface'
  };
  
  return recoveryActions[code];
};

/**
 * Handle extension-specific errors with appropriate user feedback
 */
export const handleExtensionError = async (error: any, context?: any): Promise<ExtensionError> => {
  console.error('🔧 [ExtensionErrorHandler] Handling error:', error, 'Context:', context);
  
  let extensionError: ExtensionError;
  
  // Detect error type and create appropriate extension error
  if (error?.message?.includes('Extension context invalidated')) {
    extensionError = createExtensionError(
      ExtensionErrorCodes.EXTENSION_CONTEXT_LOST,
      'Extension context was lost. Please refresh the page.',
      error,
      context
    );
  } else if (error?.message?.includes('tabs')) {
    extensionError = createExtensionError(
      ExtensionErrorCodes.MISSING_TABS_PERMISSION,
      'Extension needs tabs permission to open new windows.',
      error,
      context
    );
  } else if (error?.message?.includes('storage')) {
    extensionError = createExtensionError(
      ExtensionErrorCodes.MISSING_STORAGE_PERMISSION,
      'Extension needs storage permission to save data.',
      error,
      context
    );
  } else if (error?.message?.includes('session_token')) {
    extensionError = createExtensionError(
      ExtensionErrorCodes.SESSION_TOKEN_INVALID,
      'Session token is invalid. Please re-authenticate.',
      error,
      context
    );
  } else if (error?.message?.includes('upload')) {
    extensionError = createExtensionError(
      ExtensionErrorCodes.UPLOAD_IN_EXTENSION_FAILED,
      'Failed to upload workflow through extension. Try using the web interface.',
      error,
      context
    );
  } else {
    extensionError = createExtensionError(
      ExtensionErrorCodes.UNKNOWN_EXTENSION_ERROR,
      error?.message || 'An unknown extension error occurred.',
      error,
      context
    );
  }
  
  // Notify extension about the error
  const extensionContext = detectExtensionContext();
  if (extensionContext.isExtension) {
    try {
      await sendMessageToExtension({
        type: 'ERROR_OCCURRED',
        data: {
          error: extensionError,
          timestamp: Date.now(),
          url: window.location.href
        }
      });
    } catch (notificationError) {
      console.warn('🔧 [ExtensionErrorHandler] Failed to notify extension about error:', notificationError);
    }
  }
  
  return extensionError;
};

/**
 * Get user-friendly error message for display
 */
export const getErrorDisplayMessage = (error: ExtensionError): string => {
  const baseMessage = error.message;
  
  if (error.recoverable && error.recoveryAction) {
    return `${baseMessage}\n\nSuggested action: ${error.recoveryAction}`;
  }
  
  return baseMessage;
};

/**
 * Check if current error context suggests extension issues
 */
export const isExtensionRelatedError = (error: any): boolean => {
  if (!error) return false;
  
  const errorString = error.toString().toLowerCase();
  const extensionKeywords = [
    'extension',
    'chrome',
    'tabs',
    'storage',
    'runtime',
    'context invalidated',
    'message passing'
  ];
  
  return extensionKeywords.some(keyword => errorString.includes(keyword));
};

/**
 * Wrap async functions with extension error handling
 */
export const withExtensionErrorHandling = <T extends (...args: any[]) => Promise<any>>(
  fn: T,
  context?: string
): T => {
  return (async (...args: any[]) => {
    try {
      return await fn(...args);
    } catch (error) {
      if (isExtensionRelatedError(error)) {
        const extensionError = await handleExtensionError(error, { context, args });
        throw extensionError;
      }
      throw error;
    }
  }) as T;
}; 