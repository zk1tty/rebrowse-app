import React from "react";
import { useWorkflow } from "../context/workflow-provider";
import { ensureAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { EventViewer } from "./event-viewer";
import { debugStorageContents } from "@/lib/storage-debug";
import { inspectJWT, validateJWTForAPI } from "@/lib/jwt-debug";

export const StoppedView: React.FC = () => {
  const { discardAndStartNew, workflow } = useWorkflow();

  const [uploading, setUploading] = React.useState(false);
  const [link, setLink] = React.useState<string | null>(null);
  const [err, setErr] = React.useState<string | null>(null);
  const [showSessionToken, setShowSessionToken] = React.useState(false);
  const [sessionToken, setSessionToken] = React.useState<string | null>(null);
  const [tokenCopied, setTokenCopied] = React.useState(false);

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
    if (!showSessionToken) {
      // Get the token when revealing
      const token = await getSessionToken();
      setSessionToken(token);
    }
    setShowSessionToken(!showSessionToken);
    setTokenCopied(false); // Reset copy status when toggling
  };

  const copyTokenToClipboard = async () => {
    if (sessionToken) {
      try {
        await navigator.clipboard.writeText(sessionToken);
        setTokenCopied(true);
        setTimeout(() => setTokenCopied(false), 2000); // Reset after 2 seconds
      } catch (error) {
        console.error('Failed to copy token:', error);
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = sessionToken;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        setTokenCopied(true);
        setTimeout(() => setTokenCopied(false), 2000);
      }
    }
  };

  /* ─────────── upload handler ────────────────────────────────────── */
  const uploadJson = async () => {
    if (!workflow) return;
    setUploading(true);
    setErr(null);
    setLink(null);
    
    console.group("🚀 [Upload] Starting session-based workflow upload...");
    
    try {
      // 🔄 NEW APPROACH: Get session token instead of JWT
      const jwt = await ensureAuth(); // Still ensure user is authenticated
      console.log("🔐 [Upload] Got session token for authenticated upload");
      
      // 🔄 NEW ENDPOINT: Use session-based upload endpoint
      const requestUrl = `${import.meta.env.VITE_API_URL}/workflows/upload/session`;
      const requestBody = {
        recording: workflow,
        goal: "Automated workflow",
        name: workflow.name ?? "Untitled workflow",
        session_token: jwt, // 👈 KEY CHANGE: Pass token in body, not header
      };
      
      console.log("🚀 [Upload] Making session-based upload request:");
      console.log("📡 URL:", requestUrl);
      console.log("📦 Body preview:", {
        name: requestBody.name,
        goal: requestBody.goal,
        stepCount: requestBody.recording?.steps?.length || 0,
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

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between p-4 border-b border-border">
        <h2 className="text-lg font-semibold">Recording Finished</h2>
        <div className="space-x-2">
          <Button variant="outline" size="sm" onClick={discardAndStartNew}>
            🔄 Restart
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={uploadJson}
            disabled={!workflow || uploading}
          >
            {uploading ? "Uploading…" : "🧠 Process"}
          </Button>
          {/* <Button
            size="sm"
            onClick={downloadJson}
            disabled={!workflow}
          >
            💾 JSON
          </Button> */}
          <Button
            variant="outline"
            size="sm"
            onClick={handleRevealToken}
          >
            🔑 Token
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
                    {tokenCopied ? "✅ Copied!" : "📋 Copy"}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setShowSessionToken(false)}
                  >
                    Close
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
    </div>
  );
};
