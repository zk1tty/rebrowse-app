import { workflowService } from '@/services/workflowService';
import { 
  getStoredSessionToken, 
  validateSessionToken,
  hasValidAndAuthenticatedSession,
  clearStoredAuth 
} from '@/utils/authUtils';
import { 
  detectExtensionContext, 
  handleExtensionNavigation, 
  sendMessageToExtension 
} from '@/utils/extensionUtils';
import { withExtensionErrorHandling, createExtensionError, ExtensionErrorCodes } from '@/utils/extensionErrorHandler';

/**
 * Upload workflow recording data and navigate to processing page
 * This function is designed to be called from the Chrome extension
 * Uses session-based authentication when available
 */
export const uploadAndNavigateToProcessing = withExtensionErrorHandling(
  async (recordingData: any): Promise<string> => {
  try {
    const context = detectExtensionContext();
    console.log('🚀 [ExtensionHelpers] Starting upload process, context:', context);
    
    // Get session token for authenticated upload
    const sessionToken = getStoredSessionToken();
    
    // Validate session token before using it
    if (sessionToken) {
      console.log('🚀 [ExtensionHelpers] Validating session token...');
      const isValidSession = await hasValidAndAuthenticatedSession(sessionToken);
      
      if (!isValidSession) {
        const error = createExtensionError(
          ExtensionErrorCodes.SESSION_TOKEN_INVALID,
          'Your session has expired. Please login again through the Chrome extension.',
          null,
          { action: 'upload' }
        );
        
        // Notify extension about session expiry
        if (context.isExtension) {
          await sendMessageToExtension({
            type: 'SESSION_EXPIRED',
            data: { error: error.message }
          });
        }
        
        throw error;
      }
      console.log('🚀 [ExtensionHelpers] Session token is valid');
    } else {
      console.log('🚀 [ExtensionHelpers] No session token found');
    }
    
    // Upload the recording data with session token if available
    const { job_id } = await workflowService.uploadWorkflow(recordingData, sessionToken || undefined);
    console.log('🚀 [ExtensionHelpers] Upload successful, job_id:', job_id);
    
    // Navigate to the processing page
    const processingUrl = `/wf/processing/${job_id}`;
    
    // Notify extension about upload success
    if (context.isExtension) {
      await sendMessageToExtension({
        type: 'UPLOAD_SUCCESS',
        jobId: job_id,
        data: { processingUrl }
      });
    }
    
    // Handle navigation based on context
    await handleExtensionNavigation(processingUrl);
    
    return job_id;
  } catch (error) {
    console.error('🚀 [ExtensionHelpers] Failed to upload and navigate:', error);
    
    // Notify extension about upload failure
    const context = detectExtensionContext();
    if (context.isExtension) {
      await sendMessageToExtension({
        type: 'UPLOAD_ERROR',
        data: { error: error instanceof Error ? error.message : String(error) }
      });
    }
    
    throw error;
  }
}, 'uploadAndNavigateToProcessing');

/**
 * Direct upload function for use in web context
 * Returns the job_id for manual navigation
 * Uses session-based authentication when available
 */
export const uploadWorkflowRecording = withExtensionErrorHandling(
  async (recordingData: any): Promise<string> => {
  try {
    const context = detectExtensionContext();
    console.log('🚀 [ExtensionHelpers] Direct upload, context:', context);
    
    // Get session token for authenticated upload
    const sessionToken = getStoredSessionToken();
    
    // Validate session token before using it
    if (sessionToken) {
      console.log('🚀 [ExtensionHelpers] Validating session token for direct upload...');
      const isValidSession = await hasValidAndAuthenticatedSession(sessionToken);
      
      if (!isValidSession) {
        const error = createExtensionError(
          ExtensionErrorCodes.SESSION_TOKEN_INVALID,
          'Your session has expired. Please login again through the Chrome extension.',
          null,
          { action: 'direct_upload' }
        );
        
        // Notify extension about session expiry
        if (context.isExtension) {
          await sendMessageToExtension({
            type: 'SESSION_EXPIRED',
            data: { error: error.message }
          });
        }
        
        throw error;
      }
      console.log('🚀 [ExtensionHelpers] Session token is valid for direct upload');
    } else {
      console.log('🚀 [ExtensionHelpers] No session token found for direct upload');
    }
    
    const { job_id } = await workflowService.uploadWorkflow(recordingData, sessionToken || undefined);
    console.log('🚀 [ExtensionHelpers] Direct upload successful, job_id:', job_id);
    
    // Notify extension if in extension context
    if (context.isExtension) {
      await sendMessageToExtension({
        type: 'DIRECT_UPLOAD_SUCCESS',
        jobId: job_id
      });
    }
    
    return job_id;
  } catch (error) {
    console.error('🚀 [ExtensionHelpers] Direct upload failed:', error);
    
    // Notify extension about failure
    const context = detectExtensionContext();
    if (context.isExtension) {
      await sendMessageToExtension({
        type: 'DIRECT_UPLOAD_ERROR',
        data: { error: error instanceof Error ? error.message : String(error) }
      });
    }
    
    throw error;
  }
}, 'uploadWorkflowRecording');

/**
 * Navigate to processing page with job_id
 * Uses extension-aware navigation
 */
export async function navigateToProcessing(jobId: string): Promise<void> {
  const processingUrl = `/wf/processing/${jobId}`;
  console.log('🚀 [ExtensionHelpers] Navigating to processing:', processingUrl);
  await handleExtensionNavigation(processingUrl);
}

/**
 * Navigate to final workflow page
 * Uses extension-aware navigation
 */
export async function navigateToWorkflow(workflowId: string): Promise<void> {
  const workflowUrl = `/wf/${workflowId}`;
  console.log('🚀 [ExtensionHelpers] Navigating to workflow:', workflowUrl);
  await handleExtensionNavigation(workflowUrl);
} 