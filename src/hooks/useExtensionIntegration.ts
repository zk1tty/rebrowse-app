import { useEffect, useState, useCallback } from 'react';
import { 
  detectExtensionContext, 
  isFromExtension, 
  initializeExtensionIntegration,
  listenForExtensionMessages,
  sendMessageToExtension,
  type ExtensionContext,
  type ExtensionMessage
} from '@/utils/extensionUtils';

export interface ExtensionIntegrationState {
  context: ExtensionContext | null;
  isFromExtension: boolean;
  isInitialized: boolean;
  lastMessage: ExtensionMessage | null;
  error: string | null;
}

export interface ExtensionIntegrationActions {
  sendMessage: (message: ExtensionMessage) => Promise<any>;
  reinitialize: () => Promise<void>;
  clearError: () => void;
}

export const useExtensionIntegration = (): ExtensionIntegrationState & ExtensionIntegrationActions => {
  const [state, setState] = useState<ExtensionIntegrationState>({
    context: null,
    isFromExtension: false,
    isInitialized: false,
    lastMessage: null,
    error: null
  });

  // Initialize extension integration
  const initialize = useCallback(async () => {
    try {
      const context = await initializeExtensionIntegration();
      const fromExtension = isFromExtension();
      
      setState(prev => ({
        ...prev,
        context,
        isFromExtension: fromExtension,
        isInitialized: true,
        error: null
      }));
    } catch (error) {
      console.error('❌ [useExtensionIntegration] Initialization failed:', error);
      setState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : String(error),
        isInitialized: false
      }));
    }
  }, []);

  // Handle incoming messages from extension
  const handleExtensionMessage = useCallback((
    message: ExtensionMessage, 
    sender: any, 
    sendResponse: (response: any) => void
  ) => {
    setState(prev => ({
      ...prev,
      lastMessage: message
    }));

    // Handle specific message types
    switch (message.type) {
      case 'SESSION_TOKEN_UPDATE':
        if (message.sessionToken) {
          // Store the new session token
          sessionStorage.setItem('workflow_session_token', message.sessionToken);
        }
        sendResponse({ success: true });
        break;
        
      case 'WORKFLOW_UPLOAD_REQUEST':
        // Extension is requesting to upload workflow data
        sendResponse({ 
          success: true, 
          message: 'Upload request received' 
        });
        break;
        
      case 'PING':
        sendResponse({ 
          success: true, 
          timestamp: Date.now(),
          url: window.location.href
        });
        break;
        
      default:
        sendResponse({ success: false, error: 'Unknown message type' });
    }
  }, []);

  // Send message to extension
  const sendMessage = useCallback(async (message: ExtensionMessage): Promise<any> => {
    try {
      const response = await sendMessageToExtension(message);
      return response;
    } catch (error) {
      console.error('❌ [useExtensionIntegration] Failed to send message:', error);
      setState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : String(error)
      }));
      throw error;
    }
  }, []);

  // Reinitialize integration
  const reinitialize = useCallback(async () => {
    setState(prev => ({ ...prev, isInitialized: false, error: null }));
    await initialize();
  }, [initialize]);

  // Clear error
  const clearError = useCallback(() => {
    setState(prev => ({ ...prev, error: null }));
  }, []);

  // Initialize on mount
  useEffect(() => {
    initialize();
  }, [initialize]);

  // Set up message listener
  useEffect(() => {
    if (state.context?.isExtension) {
      const cleanup = listenForExtensionMessages(handleExtensionMessage);
      return cleanup;
    }
  }, [state.context?.isExtension, handleExtensionMessage]);

  return {
    ...state,
    sendMessage,
    reinitialize,
    clearError
  };
};

export default useExtensionIntegration; 