import React, { useState } from "react";
import { useWorkflow } from "../context/workflow-provider";
import { ensureAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { EventViewer } from "./event-viewer";
import { UploadModal } from "./upload-modal";
import { RotateCcw, Brain, Download, Key, Copy, Check, X } from "lucide-react";

export const StoppedView: React.FC = () => {
  const { discardAndStartNew, workflow } = useWorkflow();

  const [uploading, setUploading] = useState(false);
  const [link, setLink] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [showSessionToken, setShowSessionToken] = useState(false);
  const [sessionToken, setSessionToken] = useState<string | null>(null);
  const [tokenCopied, setTokenCopied] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);

  /* ─────────── session token handler ────────────────────────────────────── */
  const getSessionToken = async (): Promise<string | null> => {
    try {
      // Get the session token from Chrome storage (Supabase auth data)
      const result = await chrome.storage.local.get(['supabase.auth.token']);
      const authData = result['supabase.auth.token'];
      
      if (authData && authData.access_token) {
        return authData.access_token;
      }
      
      // Alternative: try to get from ensureAuth() which should return the token
      const token = await ensureAuth();
      return token;
    } catch (error) {
      console.error('Failed to get session token:', error);
      return null;
    }
  };

  const handleRevealToken = async () => {
    try {
      const token = await ensureAuth();
      console.log("🔑 Current JWT token:", token);
      
      // Set the token in state so it can be copied
      setSessionToken(token);
      setShowSessionToken(true);
      
      // Also copy to console for backup
      console.log("🔑 Token available for copying:", token);
    } catch (err) {
      console.error("Failed to get token:", err);
      alert("Failed to get authentication token. Please try signing in again.");
    }
  };

  const copyTokenToClipboard = async () => {
    if (!sessionToken) {
      console.warn("No session token available to copy");
      alert("No token available. Please try revealing the token again.");
      return;
    }

    try {
      // Try modern clipboard API first
      await navigator.clipboard.writeText(sessionToken);
      setTokenCopied(true);
      setTimeout(() => setTokenCopied(false), 2000);
      console.log("✅ Token copied to clipboard successfully");
    } catch (error) {
      console.warn('Modern clipboard API failed, trying fallback:', error);
      
      try {
        // Fallback for older browsers or restricted contexts
        const textArea = document.createElement('textarea');
        textArea.value = sessionToken;
        textArea.style.position = 'fixed';
        textArea.style.left = '-9999px';
        textArea.style.top = '-9999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        const successful = document.execCommand('copy');
        document.body.removeChild(textArea);
        
        if (successful) {
          setTokenCopied(true);
          setTimeout(() => setTokenCopied(false), 2000);
          console.log("✅ Token copied using fallback method");
        } else {
          throw new Error("execCommand copy failed");
        }
      } catch (fallbackError) {
        console.error('Both clipboard methods failed:', fallbackError);
        alert(`Failed to copy token to clipboard. Please copy manually:\n\n${sessionToken.substring(0, 50)}...`);
      }
    }
  };

  /* ─────────── upload handler ────────────────────────────────────── */
  const handleModalClose = () => {
    if (!uploading) {
      setShowUploadModal(false);
    }
  };

  // Function to process workflow screenshots and remove data URL prefixes
  const processWorkflowScreenshots = (workflow: any) => {
    if (!workflow?.steps) return workflow;

    let originalScreenshotCount = 0;
    let processedScreenshotCount = 0;
    let screenshotSizes: Array<{stepIndex: number, originalSize: number, processedSize: number}> = [];

    const processedWorkflow = {
      ...workflow,
      steps: workflow.steps.map((step: any, index: number) => {
        if (!step.screenshot) return step;

        originalScreenshotCount++;
        const originalSize = step.screenshot.length;

        // Remove data URL prefix (e.g., "data:image/jpeg;base64," or "data:image/png;base64,")
        let processedScreenshot = step.screenshot;
        if (typeof processedScreenshot === 'string' && processedScreenshot.includes('base64,')) {
          processedScreenshot = processedScreenshot.split('base64,')[1];
          processedScreenshotCount++;
          
          screenshotSizes.push({
            stepIndex: index,
            originalSize,
            processedSize: processedScreenshot.length
          });
        }

        return {
          ...step,
          screenshot: processedScreenshot
        };
      })
    };

    // Enhanced logging
    console.group("📸 Screenshot Processing Summary:");
    console.log(`🔢 Total steps: ${workflow.steps.length}`);
    console.log(`📷 Steps with screenshots: ${originalScreenshotCount}`);
    console.log(`✂️ Screenshots processed (had data URL): ${processedScreenshotCount}`);
    console.log("📊 Screenshot size reductions:", screenshotSizes);
    console.groupEnd();

    return processedWorkflow;
  };

  // Debug function to inspect workflow screenshots (call from console)
  const debugWorkflowScreenshots = () => {
    if (!workflow?.steps) {
      console.log("❌ No workflow data available");
      return;
    }

    console.group("🔍 Workflow Screenshot Debug Report:");
    console.log(`📋 Workflow: "${workflow.name}"`);
    console.log(`🔢 Total steps: ${workflow.steps.length}`);
    
    const stepsWithScreenshots = workflow.steps.filter((step: any) => step.screenshot);
    console.log(`📷 Steps with screenshots: ${stepsWithScreenshots.length}`);
    
    workflow.steps.forEach((step: any, index: number) => {
      const hasScreenshot = !!step.screenshot;
      const screenshotSize = step.screenshot ? step.screenshot.length : 0;
      const isDataUrl = step.screenshot?.includes('base64,') || false;
      
      const stepInfo: any = {
        hasScreenshot,
        screenshotSize: hasScreenshot ? `${screenshotSize} chars` : 'N/A',
        isDataUrl,
        screenshotPreview: hasScreenshot ? step.screenshot.substring(0, 50) + '...' : 'None'
      };

      // Add specific info for clipboard steps
      if (step.type === 'clipboard_copy' || step.type === 'clipboard_paste') {
        stepInfo.clipboardContent = step.content ? 
          `"${step.content.substring(0, 30)}${step.content.length > 30 ? '...' : ''}"`  : 
          'None';
        stepInfo.targetElement = step.cssSelector || step.xpath || 'Unknown';
      }
      
      console.log(`📍 Step ${index + 1} (${step.type}):`, stepInfo);
    });
    
    console.groupEnd();
    return { workflow, stepsWithScreenshots };
  };

  // Expose debug function to window for console access
  React.useEffect(() => {
    (window as any).debugWorkflowScreenshots = debugWorkflowScreenshots;
    (window as any).currentWorkflow = workflow;
    
    return () => {
      delete (window as any).debugWorkflowScreenshots;
      delete (window as any).currentWorkflow;
    };
  }, [workflow]);

  const uploadJson = async (data: { name: string | null; goal: string }) => {
    if (!workflow) return;
    setUploading(true);
    setErr(null);
    setLink(null);
    
    console.group("🚀 [Upload] Starting session-based workflow upload...");
    
    try {
      // 🔄 NEW APPROACH: Get session token instead of JWT
      const jwt = await ensureAuth(); // Still ensure user is authenticated
      console.log("🔐 [Upload] Got session token for authenticated upload");
      
      // 📸 Process workflow to fix screenshot format (remove data URL prefixes)
      const processedWorkflow = processWorkflowScreenshots(workflow);
      console.log("📸 [Upload] Processed screenshots - removed data URL prefixes");
      
      // 🔄 NEW ENDPOINT: Use session-based upload endpoint
      const requestUrl = `${import.meta.env.VITE_API_URL}/workflows/upload/session`;
      const requestBody = {
        recording: processedWorkflow, // Use processed workflow with fixed screenshots
        goal: data.goal, // Use the goal from the modal
        name: data.name || workflow.name || "Untitled workflow", // Use modal name, fallback to workflow name, then default
        session_token: jwt, // 👈 KEY CHANGE: Pass token in body, not header
      };
      
      console.log("🚀 [Upload] Making session-based upload request:");
      console.log("📡 URL:", requestUrl);
      console.log("📦 Body preview:", {
        name: requestBody.name,
        goal: requestBody.goal,
        stepCount: requestBody.recording?.steps?.length || 0,
        screenshotCount: requestBody.recording?.steps?.filter((s: any) => s.screenshot)?.length || 0,
        hasSessionToken: !!requestBody.session_token
      });
      
      const res = await fetch(requestUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          // 🔄 NO Authorization header needed - token is in body
        },
        body: JSON.stringify(requestBody),
      });
      
      console.log("📥 [Upload] Response status:", res.status);
      console.log("📥 [Upload] Response headers:", Object.fromEntries(res.headers.entries()));

      if (!res.ok) {
        // Get error details
        let errorDetails = `Backend returned ${res.status}`;
        try {
          const errorBody = await res.text();
          console.log("❌ [Upload] Error response body:", errorBody);
          errorDetails += ` - ${errorBody}`;
        } catch (e) {
          console.log("❌ [Upload] Could not read error response body");
        }
        throw new Error(errorDetails);
      }
      
      const result = await res.json();
      const job_id = result.job_id;
      console.log("🎉 [Upload] Session-based upload success! Job ID:", job_id);

      // 👈 Store session token for frontend access
      const processingUrl = `${import.meta.env.VITE_APP_ORIGIN}/wf/processing/${job_id}`;
      
      // Store session token in sessionStorage for frontend to use
      chrome.tabs.create({ 
        url: processingUrl,
        active: true 
      }, (tab) => {
        // Inject session token into the new tab's sessionStorage
        chrome.scripting.executeScript({
          target: { tabId: tab.id! },
          func: (token) => {
            sessionStorage.setItem('workflow_auth', token);
            sessionStorage.setItem('from_extension', 'true');
          },
          args: [jwt]
        });
      });
      
      setLink(processingUrl);
      setShowUploadModal(false); // Close modal on success
    } catch (err: any) {
      console.error("❌ [Upload] Session-based upload failed:", err);
      setErr(err.message ?? String(err));
      chrome.notifications.create({
        type: "basic",
        iconUrl: "icon.png",
        title: "Workflow upload failed",
        message: String(err),
      });
    } finally {
      setUploading(false);
      console.groupEnd();
    }
  };

  const downloadJson = () => {
    if (!workflow) return;

    // Sanitize workflow name for filename
    const safeName = workflow.name
      ? workflow.name.replace(/[^a-z0-9\.\-\_]/gi, "_").toLowerCase()
      : "workflow";

    const blob = new Blob([JSON.stringify(workflow, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    // Generate filename e.g., my_workflow_name_2023-10-27_10-30-00.json
    const timestamp = new Date()
      .toISOString()
      .replace(/[:.]/g, "-")
      .slice(0, 19);
    // Use sanitized name instead of domain
    a.download = `${safeName}_${timestamp}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleProcessClick = () => {
    if (!workflow) return;
    setShowUploadModal(true);
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between p-4 border-b border-border">
        <h2 className="text-lg font-semibold">Recording Finished</h2>
        <div className="space-x-2">
          <Button variant="outline" size="sm" onClick={discardAndStartNew}>
            <RotateCcw className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleProcessClick}
            disabled={!workflow || uploading}
          >
            {uploading ? (
              <div className="flex items-center space-x-1">
                <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-current"></div>
                <span className="text-xs">Uploading</span>
              </div>
            ) : (
              <Brain className="h-4 w-4" />
            )}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={downloadJson}
            disabled={!workflow}
          >
            <Download className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleRevealToken}
          >
            <Key className="h-4 w-4" />
          </Button>
        </div>
      </div>
      {link && (
        <div className="px-4 text-xs mt-2">
          Uploaded!{' '}
          <a href={link} target="_blank" rel="noreferrer" className="underline">
            open workflow ↗
          </a>
        </div>
      )}
      {err && (
        <div className="px-4 text-xs text-red-500 mt-2">{err}</div>
      )}
      
      {/* Session Token Panel */}
      {showSessionToken && (
        <div className="mx-4 mt-4 bg-gray-50 rounded-lg border border-gray-200">
          <div className="p-4">
            <h3 className="font-medium text-gray-900 mb-3">Session Token for Web UI</h3>
            
            {/* Instructions */}
            <div className="bg-blue-50 rounded-lg p-3 mb-4">
              <div className="text-sm text-blue-800">
                Copy token and go to <a href="https://app.rebrowse.me" target="_blank" rel="noopener noreferrer" className="underline font-medium">app.rebrowse.me</a>
              </div>
            </div>
            
            {/* Token Display */}
            {sessionToken ? (
              <div className="space-y-3">
                <div className="bg-white rounded border p-3">
                  <div className="text-xs text-gray-500 mb-1">Session Token:</div>
                  <div className="font-mono text-xs text-gray-800 break-all bg-gray-50 p-2 rounded">
                    {sessionToken}
                  </div>
                </div>
                
                <div className="flex space-x-2">
                  <Button
                    size="sm"
                    onClick={copyTokenToClipboard}
                    className="flex-1"
                  >
                    {tokenCopied ? (
                      <Check className="h-4 w-4" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setShowSessionToken(false)}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ) : (
              <div className="text-center py-4">
                <div className="text-gray-500 mb-2">Loading session token...</div>
                <div className="text-xs text-gray-400">
                  Make sure you're logged in to the extension
                </div>
              </div>
            )}
          </div>
        </div>
      )}
      
      <div className="flex-grow overflow-hidden p-4">
        <EventViewer />
      </div>

      {showUploadModal && (
        <UploadModal
          isOpen={showUploadModal}
          onClose={handleModalClose}
          onSubmit={uploadJson}
          isUploading={uploading}
        />
      )}
    </div>
  );
};
