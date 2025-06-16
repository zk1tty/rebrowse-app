/**
 * Chrome Extension Integration Utilities
 * Handles detection, communication, and integration with Chrome extension
 */

export interface ExtensionContext {
  isExtension: boolean;
  hasTabsPermission: boolean;
  hasStoragePermission: boolean;
  extensionId?: string;
  version?: string;
}

export interface ExtensionMessage {
  type: string;
  data?: any;
  sessionToken?: string;
  workflowId?: string;
  jobId?: string;
}

/**
 * Detect if running in Chrome extension context
 */
export const detectExtensionContext = (): ExtensionContext => {
  const isExtension = typeof (globalThis as any).chrome !== 'undefined' && 
                     !!(globalThis as any).chrome.runtime;
  
  if (!isExtension) {
    return {
      isExtension: false,
      hasTabsPermission: false,
      hasStoragePermission: false
    };
  }

  const chrome = (globalThis as any).chrome;
  
  return {
    isExtension: true,
    hasTabsPermission: !!(chrome.tabs && chrome.tabs.create),
    hasStoragePermission: !!(chrome.storage && chrome.storage.local),
    extensionId: chrome.runtime?.id,
    version: chrome.runtime?.getManifest?.()?.version
  };
};

/**
 * Check if user came from Chrome extension (stored flag)
 */
export const isFromExtension = (): boolean => {
  try {
    return sessionStorage.getItem('from_extension') === 'true';
  } catch (error) {
    console.error('🔧 [Extension] Error checking extension origin:', error);
    return false;
  }
};

/**
 * Mark user as coming from Chrome extension
 */
export const markFromExtension = (): void => {
  try {
    sessionStorage.setItem('from_extension', 'true');
    console.log('🔧 [Extension] Marked user as from extension');
  } catch (error) {
    console.error('🔧 [Extension] Error marking extension origin:', error);
  }
};

/**
 * Clear extension origin flag
 */
export const clearExtensionOrigin = (): void => {
  try {
    sessionStorage.removeItem('from_extension');
    console.log('🔧 [Extension] Cleared extension origin flag');
  } catch (error) {
    console.error('🔧 [Extension] Error clearing extension origin:', error);
  }
};

/**
 * Open URL in new tab (extension context)
 */
export const openInNewTab = async (url: string, active: boolean = true): Promise<boolean> => {
  const context = detectExtensionContext();
  
  if (!context.isExtension || !context.hasTabsPermission) {
    console.warn('🔧 [Extension] Cannot open new tab - not in extension context or missing permissions');
    return false;
  }

  try {
    const chrome = (globalThis as any).chrome;
    await chrome.tabs.create({
      url: url.startsWith('http') ? url : `${window.location.origin}${url}`,
      active
    });
    console.log('🔧 [Extension] Opened new tab:', url);
    return true;
  } catch (error) {
    console.error('🔧 [Extension] Failed to open new tab:', error);
    return false;
  }
};

/**
 * Send message to extension background script
 */
export const sendMessageToExtension = async (message: ExtensionMessage): Promise<any> => {
  const context = detectExtensionContext();
  
  if (!context.isExtension) {
    console.warn('🔧 [Extension] Cannot send message - not in extension context');
    return null;
  }

  try {
    const chrome = (globalThis as any).chrome;
    const response = await chrome.runtime.sendMessage(message);
    console.log('🔧 [Extension] Message sent:', message.type, 'Response:', response);
    return response;
  } catch (error) {
    console.error('🔧 [Extension] Failed to send message:', error);
    return null;
  }
};

/**
 * Listen for messages from extension
 */
export const listenForExtensionMessages = (
  callback: (message: ExtensionMessage, sender: any, sendResponse: (response: any) => void) => void
): (() => void) => {
  const context = detectExtensionContext();
  
  if (!context.isExtension) {
    console.warn('🔧 [Extension] Cannot listen for messages - not in extension context');
    return () => {};
  }

  const chrome = (globalThis as any).chrome;
  chrome.runtime.onMessage.addListener(callback);
  
  console.log('🔧 [Extension] Started listening for extension messages');
  
  // Return cleanup function
  return () => {
    chrome.runtime.onMessage.removeListener(callback);
    console.log('🔧 [Extension] Stopped listening for extension messages');
  };
};

/**
 * Get extension storage data
 */
export const getExtensionStorage = async (keys: string | string[]): Promise<any> => {
  const context = detectExtensionContext();
  
  if (!context.isExtension || !context.hasStoragePermission) {
    console.warn('🔧 [Extension] Cannot access storage - not in extension context or missing permissions');
    return null;
  }

  try {
    const chrome = (globalThis as any).chrome;
    const result = await chrome.storage.local.get(keys);
    console.log('🔧 [Extension] Retrieved storage:', keys, result);
    return result;
  } catch (error) {
    console.error('🔧 [Extension] Failed to get storage:', error);
    return null;
  }
};

/**
 * Set extension storage data
 */
export const setExtensionStorage = async (data: Record<string, any>): Promise<boolean> => {
  const context = detectExtensionContext();
  
  if (!context.isExtension || !context.hasStoragePermission) {
    console.warn('🔧 [Extension] Cannot set storage - not in extension context or missing permissions');
    return false;
  }

  try {
    const chrome = (globalThis as any).chrome;
    await chrome.storage.local.set(data);
    console.log('🔧 [Extension] Set storage:', data);
    return true;
  } catch (error) {
    console.error('🔧 [Extension] Failed to set storage:', error);
    return false;
  }
};

/**
 * Handle extension-specific navigation
 */
export const handleExtensionNavigation = async (path: string): Promise<void> => {
  const context = detectExtensionContext();
  
  if (context.isExtension && context.hasTabsPermission) {
    // In extension context, open new tab
    const success = await openInNewTab(path);
    if (!success) {
      // Fallback to regular navigation
      window.location.href = path;
    }
  } else {
    // Regular web navigation
    window.location.href = path;
  }
};

/**
 * Initialize extension integration
 */
export const initializeExtensionIntegration = async (): Promise<ExtensionContext> => {
  const context = detectExtensionContext();
  
  console.log('🔧 [Extension] Initializing extension integration:', context);
  
  if (context.isExtension) {
    // Mark as from extension
    markFromExtension();
    
    // Send initialization message to extension
    await sendMessageToExtension({
      type: 'WEB_APP_INITIALIZED',
      data: {
        url: window.location.href,
        timestamp: Date.now()
      }
    });
  }
  
  return context;
};

/**
 * Cleanup extension integration
 */
export const cleanupExtensionIntegration = (): void => {
  clearExtensionOrigin();
  console.log('🔧 [Extension] Extension integration cleaned up');
}; 