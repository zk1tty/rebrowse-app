// import { eventWithTime } from 'rrweb'; // Type not directly available
import { EventType, IncrementalSource } from "@rrweb/types";
import {
  StoredCustomClickEvent,
  StoredCustomInputEvent,
  StoredCustomKeyEvent,
  StoredEvent,
  StoredRrwebEvent,
} from "../lib/types";
import {
  ClickStep,
  InputStep,
  KeyPressStep,
  NavigationStep,
  ScrollStep,
  Step,
  Workflow,
  ClipboardCopyStep,
  ClipboardPasteStep,
} from "../lib/workflow-types";
import {
  HttpEvent,
  HttpRecordingStartedEvent,
  HttpRecordingStoppedEvent,
  HttpWorkflowUpdateEvent,
  CookieSyncProgressMessage,
  CookieSyncDoneMessage,
} from "../lib/message-bus-types";
import { COOKIE_SITES } from "../lib/cookie-sites";
import type { CookieSiteId } from "../lib/cookie-sites";
import { getSiteHostPermissions, checkOrigins, buildHostPermissionPatternsForDomain } from "../lib/host-permissions";
import { ensureAuth } from '@/lib/auth';

export default defineBackground(() => {
  // In-memory store for rrweb events, keyed by tabId
  const sessionLogs: { [tabId: number]: StoredEvent[] } = {}; // Use StoredEvent type

  // Store tab information (URL, potentially title)
  const tabInfo: { [tabId: number]: { url?: string; title?: string } } = {};

  let isRecordingEnabled = false; // Default to disabled (OFF)
  let lastWorkflowHash: string | null = null; // Cache for the last logged workflow hash
  // Persisted cookie sync statuses (mirror to avoid storage write races)
  let cookieStatusMap: Record<string, { status: string; lastUpdated: number; message?: string }> = {};

  const PYTHON_SERVER_ENDPOINT = `${import.meta.env.VITE_API_URL}/event`;

  // Hashing function using SubtleCrypto (SHA-256)
  async function calculateSHA256(str: string): Promise<string> {
    const encoder = new TextEncoder();
    const data = encoder.encode(str);
    const hashBuffer = await crypto.subtle.digest("SHA-256", data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const hashHex = hashArray
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
    return hashHex;
  }

  // Helper function to send data to the Python server
  async function sendEventToServer(eventData: HttpEvent) {
    try {
      await fetch(PYTHON_SERVER_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(eventData),
      });
    } catch (error) {
      console.warn(
        `Failed to send event to Python server at ${PYTHON_SERVER_ENDPOINT}:`,
        error
      );
    }
  }

  // Function to broadcast workflow data updates to the console bus
  async function broadcastWorkflowDataUpdate(): Promise<Workflow> {
    // console.log("[DEBUG] broadcastWorkflowDataUpdate: Entered function"); // Optional: Keep for debugging
    const allSteps: Step[] = Object.keys(sessionLogs)
      .flatMap((tabIdStr) => {
        const tabId = parseInt(tabIdStr, 10);
        return convertStoredEventsToSteps(sessionLogs[tabId] || []);
      })
      .sort((a, b) => a.timestamp - b.timestamp); // Sort chronologically

    // Create the workflowData object *after* sorting steps, but hash only steps
    const workflowData: Workflow = {
      name: "Recorded Workflow",
      description: `Recorded on ${new Date().toLocaleString()}`,
      version: "1.0.0",
      input_schema: [],
      steps: allSteps, // allSteps is used here
    };

    const allStepsString = JSON.stringify(allSteps); // Hash based on allSteps
    const currentWorkflowHash = await calculateSHA256(allStepsString);

    // console.log("[DEBUG] broadcastWorkflowDataUpdate: Current steps hash:", currentWorkflowHash, "Last steps hash:", lastWorkflowHash); // Optional

    // Condition to skip logging if the hash of steps is the same
    if (lastWorkflowHash !== null && currentWorkflowHash === lastWorkflowHash) {
      // console.log("[DEBUG] broadcastWorkflowDataUpdate: Steps unchanged, skipping log."); // Optional
      return workflowData;
    }

    lastWorkflowHash = currentWorkflowHash;
    // console.log("[DEBUG] broadcastWorkflowDataUpdate: Steps changed, workflowData object:", JSON.parse(JSON.stringify(workflowData))); // Optional

    // Send workflow update to Python server
    const eventToSend: HttpWorkflowUpdateEvent = {
      type: "WORKFLOW_UPDATE",
      timestamp: Date.now(),
      payload: workflowData,
    };
    sendEventToServer(eventToSend);
    return workflowData;
  }

  // Function to broadcast the recording status to all content scripts and sidepanel
  function broadcastRecordingStatus() {
    const statusString = isRecordingEnabled ? "recording" : "stopped"; // Map boolean to string status
    // Broadcast to Tabs
    chrome.tabs.query({}, (tabs) => {
      tabs.forEach((tab) => {
        if (tab.id) {
          chrome.tabs
            .sendMessage(tab.id, {
              type: "SET_RECORDING_STATUS",
              payload: isRecordingEnabled,
            })
            .catch((err: Error) => {
              // Optional: Log if sending to a specific tab failed (e.g., script not injected)
              // console.debug(`Could not send status to tab ${tab.id}: ${err.message}`);
            });
        }
      });
    });
    // Broadcast to Sidepanel (using runtime message)
    chrome.runtime
      .sendMessage({
        type: "recording_status_updated",
        payload: { status: statusString }, // Send string status
      })
      .catch((err) => {
        // console.debug("Could not send status update to sidepanel (might be closed)", err.message);
      });
  }

  // --- Tab Event Listeners ---

  // Function to send tab events (only if recording is enabled)
  function sendTabEvent(type: string, payload: any) {
    if (!isRecordingEnabled) return;
    console.log(`Sending ${type}:`, payload);
    const tabId = payload.tabId;
    if (tabId) {
      if (!sessionLogs[tabId]) {
        sessionLogs[tabId] = [];
      }
      sessionLogs[tabId].push({
        messageType: type,
        timestamp: Date.now(),
        tabId: tabId,
        ...payload,
      });
      broadcastWorkflowDataUpdate(); // Call is async, will not block
    } else {
      console.warn(
        "Tab event received without tabId in payload:",
        type,
        payload
      );
      // Optionally store in a global log?
    }
  }

  chrome.tabs.onCreated.addListener((tab) => {
    sendTabEvent("CUSTOM_TAB_CREATED", {
      tabId: tab.id,
      openerTabId: tab.openerTabId,
      url: tab.pendingUrl || tab.url,
      windowId: tab.windowId,
      index: tab.index,
    });
  });

  chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    // Filter for relevant changes (e.g., url or status complete)
    if (changeInfo.url || changeInfo.status === "complete") {
      sendTabEvent("CUSTOM_TAB_UPDATED", {
        tabId: tabId,
        changeInfo: changeInfo, // includes URL, status, title etc.
        windowId: tab.windowId,
        url: tab.url,
        title: tab.title,
      });
    }
  });

  chrome.tabs.onActivated.addListener((activeInfo) => {
    sendTabEvent("CUSTOM_TAB_ACTIVATED", {
      tabId: activeInfo.tabId,
      windowId: activeInfo.windowId,
    });
  });

  chrome.tabs.onRemoved.addListener((tabId, removeInfo) => {
    sendTabEvent("CUSTOM_TAB_REMOVED", {
      tabId: tabId,
      windowId: removeInfo.windowId,
      isWindowClosing: removeInfo.isWindowClosing,
    });
    // Optional: Clean up logs for the closed tab if desired (we keep them by default)
    // if (sessionLogs[tabId]) {
    //   console.log(`Tab ${tabId} closed, removing logs.`);
    //   delete sessionLogs[tabId];
    //   delete tabInfo[tabId];
    // }
  });

  // --- End Tab Event Listeners ---

  // --- Conversion Function ---

  function convertStoredEventsToSteps(events: StoredEvent[]): Step[] {
    const steps: Step[] = [];

    for (const event of events) {
      switch (event.messageType) {
        case "CUSTOM_CLICK_EVENT": {
          const clickEvent = event as StoredCustomClickEvent;
          // Ensure required fields are present, even if optional in source type for some reason
          if (
            clickEvent.url &&
            clickEvent.frameUrl &&
            clickEvent.xpath &&
            clickEvent.elementTag
          ) {
            const step: ClickStep = {
              type: "click",
              timestamp: clickEvent.timestamp,
              tabId: clickEvent.tabId,
              url: clickEvent.url,
              frameUrl: clickEvent.frameUrl,
              xpath: clickEvent.xpath,
              cssSelector: clickEvent.cssSelector,
              elementTag: clickEvent.elementTag,
              elementText: clickEvent.elementText,
              screenshot: clickEvent.screenshot,
            };
            steps.push(step);
          } else {
            console.warn("Skipping incomplete CUSTOM_CLICK_EVENT:", clickEvent);
          }
          break;
        }

        case "CUSTOM_INPUT_EVENT": {
          const inputEvent = event as StoredCustomInputEvent;
          if (
            inputEvent.url &&
            // inputEvent.frameUrl && // frameUrl might be null/undefined in some cases, let's allow merging if only one is present or both match
            inputEvent.xpath &&
            inputEvent.elementTag
          ) {
            const lastStep = steps.length > 0 ? steps[steps.length - 1] : null;

            // Check if the last step was a mergeable input event
            if (
              lastStep &&
              lastStep.type === "input" &&
              lastStep.tabId === inputEvent.tabId &&
              lastStep.url === inputEvent.url &&
              lastStep.frameUrl === inputEvent.frameUrl && // Ensure frameUrls match if both exist
              lastStep.xpath === inputEvent.xpath &&
              lastStep.cssSelector === inputEvent.cssSelector &&
              lastStep.elementTag === inputEvent.elementTag
            ) {
              // Update the last input step
              (lastStep as InputStep).value = inputEvent.value;
              lastStep.timestamp = inputEvent.timestamp; // Update to latest timestamp
              (lastStep as InputStep).screenshot = inputEvent.screenshot; // Update to latest screenshot
            } else {
              // Add a new input step
              const newStep: InputStep = {
                type: "input",
                timestamp: inputEvent.timestamp,
                tabId: inputEvent.tabId,
                url: inputEvent.url,
                frameUrl: inputEvent.frameUrl,
                xpath: inputEvent.xpath,
                cssSelector: inputEvent.cssSelector,
                elementTag: inputEvent.elementTag,
                value: inputEvent.value,
                screenshot: inputEvent.screenshot,
              };
              steps.push(newStep);
            }
          } else {
            console.warn("Skipping incomplete CUSTOM_INPUT_EVENT:", inputEvent);
          }
          break;
        }

        case "CUSTOM_KEY_EVENT": {
          const keyEvent = event as StoredCustomKeyEvent;
          // Key press might not always have a target element (xpath, etc.)
          // but needs at least url and key
          if (keyEvent.url && keyEvent.key) {
            const step: KeyPressStep = {
              type: "key_press",
              timestamp: keyEvent.timestamp,
              tabId: keyEvent.tabId,
              url: keyEvent.url,
              frameUrl: keyEvent.frameUrl, // Can be missing
              key: keyEvent.key,
              xpath: keyEvent.xpath,
              cssSelector: keyEvent.cssSelector,
              elementTag: keyEvent.elementTag,
              screenshot: keyEvent.screenshot,
            };
            steps.push(step);
          } else {
            console.warn("Skipping incomplete CUSTOM_KEY_EVENT:", keyEvent);
          }
          break;
        }

        case "RRWEB_EVENT": {
          const rrEvent = event as StoredRrwebEvent;
          
          // Handle rrweb Custom Events (type 5) for clipboard operations
          if (rrEvent.type === 5 && rrEvent.data?.tag === 'clipboard') {
            const clipboardData = rrEvent.data.payload;
            
            if (clipboardData.clipboardType === 'copy') {
              const step: ClipboardCopyStep = {
                type: "clipboard_copy",
                timestamp: rrEvent.timestamp,
                tabId: rrEvent.tabId,
                url: clipboardData.url || '',
                frameUrl: clipboardData.frameUrl,
                xpath: clipboardData.xpath,
                cssSelector: clipboardData.cssSelector,
                elementTag: clipboardData.elementTag,
                elementText: clipboardData.elementText,
                content: clipboardData.content || '',
                screenshot: undefined, // TODO: Add screenshot capture for clipboard events
              };
              steps.push(step);
              console.log("📋 Added clipboard copy step:", step);
            } else if (clipboardData.clipboardType === 'paste') {
              const step: ClipboardPasteStep = {
                type: "clipboard_paste",
                timestamp: rrEvent.timestamp,
                tabId: rrEvent.tabId,
                url: clipboardData.url || '',
                frameUrl: clipboardData.frameUrl,
                xpath: clipboardData.xpath,
                cssSelector: clipboardData.cssSelector,
                elementTag: clipboardData.elementTag,
                elementText: clipboardData.elementText,
                content: clipboardData.content,
                screenshot: undefined, // TODO: Add screenshot capture for clipboard events
              };
              steps.push(step);
              console.log("📋 Added clipboard paste step:", step);
            }
          }
          // Handle scroll events from rrweb for scrolling
          else if (
            rrEvent.type === EventType.IncrementalSnapshot &&
            rrEvent.data.source === IncrementalSource.Scroll
          ) {
            const scrollData = rrEvent.data as {
              id: number;
              x: number;
              y: number;
            }; // Type assertion for clarity
            const currentTabInfo = tabInfo[rrEvent.tabId]; // Get associated tab info for URL

            // Check if the last step added was a mergeable scroll event
            const lastStep = steps.length > 0 ? steps[steps.length - 1] : null;
            if (
              lastStep &&
              lastStep.type === "scroll" &&
              lastStep.tabId === rrEvent.tabId &&
              (lastStep as ScrollStep).targetId === scrollData.id
            ) {
              // Update the last scroll step
              (lastStep as ScrollStep).scrollX = scrollData.x;
              (lastStep as ScrollStep).scrollY = scrollData.y;
              lastStep.timestamp = rrEvent.timestamp; // Update to latest timestamp
              // URL should already be set from the first event in the sequence
            } else {
              // Add a new scroll step
              const newStep: ScrollStep = {
                type: "scroll",
                timestamp: rrEvent.timestamp,
                tabId: rrEvent.tabId,
                targetId: scrollData.id,
                scrollX: scrollData.x,
                scrollY: scrollData.y,
                url: currentTabInfo?.url, // Add URL if available
              };
              steps.push(newStep);
            }
          } else if (rrEvent.type === EventType.Meta && rrEvent.data?.href) {
            // Also handle rrweb meta events as navigation
            const metaData = rrEvent.data as { href: string };
            const step: NavigationStep = {
              type: "navigation",
              timestamp: rrEvent.timestamp,
              tabId: rrEvent.tabId,
              url: metaData.href,
            };
            steps.push(step);
          }
          break;
        }

        // Add cases for other StoredEvent types to Step types if needed
        // e.g., CUSTOM_SELECT_EVENT -> SelectStep
        // e.g., CUSTOM_TAB_CREATED -> TabCreatedStep
        // RRWEB_EVENT type 4 (Meta) or 3 (FullSnapshot) could potentially map to NavigationStep if needed.

        default:
          // Ignore other event types for now
          // console.log("Ignoring event type:", event.messageType);
          break;
      }
    }

    return steps;
  }

  // --- Message Handlers & Dispatcher ---

    const customEventTypes = [
      "CUSTOM_CLICK_EVENT",
      "CUSTOM_INPUT_EVENT",
      "CUSTOM_SELECT_EVENT",
      "CUSTOM_KEY_EVENT",
    ];

  const handleContentEvent = (type: string, message: any, sender: chrome.runtime.MessageSender) => {
    if (!isRecordingEnabled) return false;
      if (!sender.tab?.id) {
        console.warn("Received event without tab ID:", message);
      return false;
      }
      const tabId = sender.tab.id;

      const storeEvent = (eventPayload: any, screenshotDataUrl?: string) => {
      if (!sessionLogs[tabId]) sessionLogs[tabId] = [];
      if (!tabInfo[tabId]) tabInfo[tabId] = {};
      if (sender.tab?.url && !tabInfo[tabId].url) tabInfo[tabId].url = sender.tab.url;
      if (sender.tab?.title && !tabInfo[tabId].title) tabInfo[tabId].title = sender.tab.title;

      const eventWithMeta = { ...eventPayload, tabId, messageType: type, screenshot: screenshotDataUrl };
        sessionLogs[tabId].push(eventWithMeta);
      broadcastWorkflowDataUpdate();
      };

    const isCustom = customEventTypes.includes(type);
    if (isCustom && sender.tab?.windowId) {
        chrome.tabs.captureVisibleTab(
          sender.tab.windowId,
          { format: "jpeg", quality: 75 },
          (dataUrl) => {
            if (chrome.runtime.lastError) {
            console.error("Screenshot failed:", chrome.runtime.lastError.message);
            storeEvent(message.payload);
            } else {
            storeEvent(message.payload, dataUrl);
            }
          }
        );
      return false;
    }
    if (type === "RRWEB_EVENT") {
        storeEvent(message.payload);
      return false;
    }
    if (isCustom) {
      console.warn("Storing custom event without screenshot due to missing windowId or other issue.");
        storeEvent(message.payload);
      return false;
    }
    return false;
  };

  const handleGetRecordingData = async (_message: any, _sender: any, sendResponse: (res: any) => void) => {
        const workflowData = await broadcastWorkflowDataUpdate();
    const statusString = isRecordingEnabled ? "recording" : workflowData.steps.length > 0 ? "stopped" : "idle";
        sendResponse({ workflow: workflowData, recordingStatus: statusString });
  };

  const handleStartRecording = (_message: any, _sender: any, sendResponse: (res: any) => void) => {
      console.log("Received START_RECORDING request.");
    Object.keys(sessionLogs).forEach((key) => delete sessionLogs[parseInt(key)]);
      Object.keys(tabInfo).forEach((key) => delete tabInfo[parseInt(key)]);
      console.log("Cleared previous recording data.");
      if (!isRecordingEnabled) {
        isRecordingEnabled = true;
        console.log("Recording status set to: true");
      broadcastRecordingStatus();
      const eventToSend: HttpRecordingStartedEvent = { type: "RECORDING_STARTED", timestamp: Date.now(), payload: { message: "Recording has started" } };
        sendEventToServer(eventToSend);
      }
    sendResponse({ status: "started" });
  };

  const handleStopRecording = (_message: any, _sender: any, sendResponse: (res: any) => void) => {
      console.log("Received STOP_RECORDING request.");
      if (isRecordingEnabled) {
        isRecordingEnabled = false;
        console.log("Recording status set to: false");
      broadcastRecordingStatus();
      const eventToSend: HttpRecordingStoppedEvent = { type: "RECORDING_STOPPED", timestamp: Date.now(), payload: { message: "Recording has stopped" } };
        sendEventToServer(eventToSend);
      }
    sendResponse({ status: "stopped" });
  };

  const handleStartCookieSync = async (message: any, _sender: any, sendResponse: (res: any) => void) => {
    try {
      const { requestId, sites = [], others = [] } = message.payload || {};
      console.log("[CookieSync] START received:", { requestId, sites, others });
      sendResponse({ ok: true });
      const allTargets: string[] = [...sites, ...others.map((d: string) => `other:${d}`)];

      const persistStatus = async (
        siteId: string,
        status: 'ready' | 'processing' | 'success' | 'failed',
        message?: string
      ) => {
        const key = 'cookieSyncStatusMap';
        cookieStatusMap[siteId] = { status, lastUpdated: Date.now(), message };
        await chrome.storage.local.set({ [key]: cookieStatusMap });
      };

      const runForTarget = async (siteId: string) => {
        const progressStart: CookieSyncProgressMessage = { type: 'COOKIE_SYNC_PROGRESS', payload: { requestId, site: { siteId, status: 'processing', lastUpdated: Date.now() } } };
        chrome.runtime.sendMessage(progressStart).catch(() => {});
        await persistStatus(siteId, 'processing');
        // Permission pre-check to avoid silent failures
        try {
          if (siteId.startsWith('other:')) {
            const domain = siteId.split(':', 2)[1];
            const origins = buildHostPermissionPatternsForDomain(domain);
            const perm = await checkOrigins(origins);
            if (perm.missing?.length) {
              const msg = 'Permission not granted';
              const deniedMsg: CookieSyncProgressMessage = { type: 'COOKIE_SYNC_PROGRESS', payload: { requestId, site: { siteId, status: 'failed', lastUpdated: Date.now(), message: msg } } };
              chrome.runtime.sendMessage(deniedMsg).catch(() => {});
              await persistStatus(siteId, 'failed', msg);
              return { siteId, ok: false };
            }
          } else {
            const isCookieSiteId = (v: any): v is import('../lib/cookie-sites').CookieSiteId => (Object.keys(COOKIE_SITES) as string[]).includes(String(v));
            if (isCookieSiteId(siteId)) {
              const origins = getSiteHostPermissions(siteId);
              const perm = await checkOrigins(origins);
              if (perm.missing?.length) {
                const msg = 'Permission not granted';
                const deniedMsg: CookieSyncProgressMessage = { type: 'COOKIE_SYNC_PROGRESS', payload: { requestId, site: { siteId, status: 'failed', lastUpdated: Date.now(), message: msg } } };
                chrome.runtime.sendMessage(deniedMsg).catch(() => {});
                await persistStatus(siteId, 'failed', msg);
                return { siteId, ok: false };
              }
            }
          }
        } catch {}
        let cookies: chrome.cookies.Cookie[] = [];
        try {
          if (siteId.startsWith('other:')) {
            const domain = siteId.split(':', 2)[1];
            const list1 = await chrome.cookies.getAll({ domain });
            const list2 = await chrome.cookies.getAll({ domain: `.${domain}` });
            cookies = [...(list1 || []), ...(list2 || [])];
          } else {
            const isCookieSiteId = (v: any): v is import('../lib/cookie-sites').CookieSiteId => (Object.keys(COOKIE_SITES) as string[]).includes(String(v));
            if (isCookieSiteId(siteId)) {
              const domains = COOKIE_SITES[siteId].cookieDomains;
              for (const d of domains) {
                const list = await chrome.cookies.getAll({ domain: d });
                if (list?.length) cookies.push(...list);
              }
            }
          }
        } catch (e) {
          console.warn('[CookieSync] collection failed for', siteId, e);
        }
        let ok = true; const missing: string[] = []; let reason: string | undefined;
        const isCookieSiteId = (v: any): v is import('../lib/cookie-sites').CookieSiteId => (Object.keys(COOKIE_SITES) as string[]).includes(String(v));
        if (isCookieSiteId(siteId)) {
          const req = COOKIE_SITES[siteId].requiredCookies || [];
          const cookiesByName = cookies.reduce<Record<string, chrome.cookies.Cookie[]>>((acc, c) => {
            (acc[c.name] ||= []).push(c);
            return acc;
          }, {});
          for (const r of req) if (!cookiesByName[r]?.length) missing.push(r);

          if (missing.length === 0) {
            // Site-specific validation hardening
            if (siteId === 'facebook') {
              const xsList = cookiesByName['xs'] || [];
              const xsGood = xsList.some((c) => c.httpOnly === true && c.secure === true);
              if (!xsGood) { ok = false; reason = 'xs must be httpOnly & secure'; }
              const cUserList = cookiesByName['c_user'] || [];
              const cUserGood = cUserList.some((c) => (c.value ?? '').length > 0);
              if (!cUserGood) { ok = false; reason = 'c_user missing or empty'; }
            } else if (siteId === 'linkedin') {
              const liAtList = cookiesByName['li_at'] || [];
              const liAtGood = liAtList.some((c) => c.httpOnly === true);
              if (!liAtGood) { ok = false; reason = 'li_at must be httpOnly'; }
            } else if (siteId === 'instagram') {
              const sidList = cookiesByName['sessionid'] || [];
              const sidGood = sidList.some((c) => c.httpOnly === true);
              if (!sidGood) { ok = false; reason = 'sessionid must be httpOnly'; }
            } else if (siteId === 'x') {
              const atList = cookiesByName['auth_token'] || [];
              const atGood = atList.some((c) => c.httpOnly === true);
              if (!atGood) { ok = false; reason = 'auth_token must be httpOnly'; }
            }
          } else {
            ok = false;
          }
        }
        const msgText = ok ? undefined : (missing.length ? `Missing: ${missing.join(', ')}` : (reason || 'Validation failed'));
        const progressEnd: CookieSyncProgressMessage = { type: 'COOKIE_SYNC_PROGRESS', payload: { requestId, site: { siteId, status: ok ? 'success' : 'failed', lastUpdated: Date.now(), message: msgText } } };
        chrome.runtime.sendMessage(progressEnd).catch(() => {});
        await persistStatus(siteId, ok ? 'success' : 'failed', msgText);
        return { siteId, ok };
      };

      const results = await Promise.all(allTargets.map(runForTarget));
      const done: CookieSyncDoneMessage = { type: 'COOKIE_SYNC_DONE', payload: { requestId, results: results.map((r) => ({ siteId: r.siteId, status: r.ok ? 'success' : 'failed', lastUpdated: Date.now() })) } };
      chrome.runtime.sendMessage(done).catch(() => {});
    } catch (err) {
      console.error('[CookieSync] START handler failed:', err);
      try {
        chrome.runtime.sendMessage({ type: 'COOKIE_SYNC_ERROR', payload: { requestId: message?.payload?.requestId, error: String(err) } }).catch(() => {});
      } catch {}
    }
  };

  const handleGetSiteCookies = (message: any, _sender: any, sendResponse: (res: any) => void) => {
    (async () => {
      try {
        const { siteId, domain, storeId } = message.payload || {};
        const siteKey = siteId ?? (domain ? `other:${domain}` : 'unknown');
        let queryDomains: string[] = [];
        const isCookieSiteId = (v: any): v is CookieSiteId => (Object.keys(COOKIE_SITES) as string[]).includes(String(v));
        if (isCookieSiteId(siteId)) queryDomains = COOKIE_SITES[siteId].cookieDomains; else if (domain) { const d = domain.trim().toLowerCase(); queryDomains = [d, `.${d}`]; }
        const allCookies: chrome.cookies.Cookie[] = [];
        for (const d of queryDomains) { const list = await chrome.cookies.getAll({ domain: d, storeId }); if (list && list.length) allCookies.push(...list); }
        console.log(`[CookieFetch] ${siteKey} -> ${allCookies.length} cookies`, allCookies);
        sendResponse({ ok: true, siteKey, cookies: allCookies });
      } catch (e) {
        console.error('[CookieFetch] failed:', e);
        sendResponse({ ok: false, siteKey: message.payload?.siteId ?? message.payload?.domain, error: String(e) });
      }
    })();
    return true; // async
  };

  const handleDownloadCookiesJson = (message: any, _sender: any, sendResponse: (res: any) => void) => {
    (async () => {
      try {
        const { sites = [], others = [], storeId } = message.payload || {};
        const targets: Array<{ key: string; domains: string[] }> = [];
        const isCookieSiteId = (v: any): v is import('../lib/cookie-sites').CookieSiteId => (Object.keys(COOKIE_SITES) as string[]).includes(String(v));
        for (const s of sites) { if (isCookieSiteId(s)) targets.push({ key: s, domains: COOKIE_SITES[s].cookieDomains }); }
        for (const dRaw of others) { const d = String(dRaw).trim().toLowerCase(); if (!d) continue; targets.push({ key: `other:${d}`, domains: [d, `.${d}`] }); }
        const collected: chrome.cookies.Cookie[] = [];
        for (const t of targets) { for (const dom of t.domains) { const list = await chrome.cookies.getAll({ domain: dom, storeId }); if (list?.length) collected.push(...list); } }
        const sameSiteMap: Record<string, 'None' | 'Lax' | 'Strict'> = { no_restriction: 'None', lax: 'Lax', strict: 'Strict' } as const;
        const keyOf = (c: chrome.cookies.Cookie) => `${c.domain}|${c.path}|${c.name}`;
        const dedup = new Map<string, chrome.cookies.Cookie>();
        for (const c of collected) { const k = keyOf(c); const prev = dedup.get(k); if (!prev || (c.expirationDate ?? 0) > (prev.expirationDate ?? 0)) dedup.set(k, c); }
        const cookiesOut = Array.from(dedup.values()).map((c) => ({ name: c.name, value: c.value, domain: c.domain, path: c.path, expires: Math.trunc(c.expirationDate ?? 0), httpOnly: !!c.httpOnly, secure: !!c.secure, sameSite: sameSiteMap[String(c.sameSite) as keyof typeof sameSiteMap] ?? 'Lax' }));

        // Validate presence of required cookies before writing the file; if any selected site is missing its required cookies,
        // embed a warning in filename to make debugging easier (does not block download).
        try {
          const siteReqs: Record<string, string[]> = {
            x: ['auth_token'],
            linkedin: ['li_at'],
            instagram: ['sessionid'],
            facebook: ['c_user', 'xs'],
          };
          const namesSet = new Set(cookiesOut.map((c) => c.name));
          const missingPerSite: string[] = [];
          for (const [site, reqs] of Object.entries(siteReqs)) {
            const miss = reqs.filter((r) => !namesSet.has(r));
            if (miss.length) missingPerSite.push(`${site}:${miss.join('+')}`);
          }
          if (missingPerSite.length) {
            console.warn('[DownloadCookies] Missing required before download:', missingPerSite.join(', '));
          }
        } catch {}
        const payload = { cookies: cookiesOut, origins: [] as any[] };
        const json = JSON.stringify(payload, null, 2);
        const url = 'data:application/json;charset=utf-8,' + encodeURIComponent(json);
        const filename = `storage_state_${new Date().toISOString().replace(/[:.]/g, '-')}.json`;
        await chrome.downloads.download({ url, filename, saveAs: true });
        sendResponse({ ok: true, count: cookiesOut.length });
      } catch (e) {
        console.error('[DownloadCookies] failed:', e);
        sendResponse({ ok: false, error: String(e) });
      }
    })();
    return true; // async
  };

  const handleRequestRecordingStatus = (_message: any, sender: chrome.runtime.MessageSender, sendResponse: (res: any) => void) => {
    if (!sender.tab?.id) return false;
    console.log(`Sending initial status (${isRecordingEnabled}) to tab ${sender.tab.id}`);
    setTimeout(() => { sendResponse({ isRecordingEnabled }); }, 50);
    return true; // async response
  };

  const messageHandlers: Record<string, (message: any, sender: chrome.runtime.MessageSender, sendResponse: (res: any) => void) => boolean | void | Promise<void>> = {
    // Content events
    RRWEB_EVENT: (m, s) => handleContentEvent('RRWEB_EVENT', m, s),
    CUSTOM_CLICK_EVENT: (m, s) => handleContentEvent('CUSTOM_CLICK_EVENT', m, s),
    CUSTOM_INPUT_EVENT: (m, s) => handleContentEvent('CUSTOM_INPUT_EVENT', m, s),
    CUSTOM_SELECT_EVENT: (m, s) => handleContentEvent('CUSTOM_SELECT_EVENT', m, s),
    CUSTOM_KEY_EVENT: (m, s) => handleContentEvent('CUSTOM_KEY_EVENT', m, s),

    // Control
    GET_RECORDING_DATA: handleGetRecordingData,
    START_RECORDING: handleStartRecording,
    STOP_RECORDING: handleStopRecording,

    // Cookie sync & cookies
    START_COOKIE_SYNC: handleStartCookieSync,
    GET_SITE_COOKIES: handleGetSiteCookies,
    DOWNLOAD_COOKIES_JSON: handleDownloadCookiesJson,

    // Status
    REQUEST_RECORDING_STATUS: handleRequestRecordingStatus,
  };

  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    const handler = messageHandlers[message?.type];
    if (!handler) return false;
    try {
      const result = handler(message, sender, sendResponse);
      if (result === true) return true; // keep port open for async
      if (result && typeof (result as any).then === 'function') {
        (result as Promise<void>).catch((e) => console.error('Async handler failed:', e));
        return true; // assume async handler will call sendResponse later
      }
      return false;
    } catch (e) {
      console.error('Handler threw:', e);
      return false;
    }
  });

  // Initialize cookie status map from storage on service worker start
  (async () => {
    try {
      const key = 'cookieSyncStatusMap';
      const res = await chrome.storage.local.get([key]);
      cookieStatusMap = (res?.[key] ?? {}) as Record<string, { status: string; lastUpdated: number; message?: string }>;
    } catch {}
  })();

  // Optional: Save data periodically or on browser close (less reliable)
  // chrome.storage.local.set({ sessionLogs, tabInfo });

  console.log(
    "Background script loaded. Initial recording status:",
    isRecordingEnabled,
    "(EventType:",
    EventType,
    ", IncrementalSource:",
    IncrementalSource,
    ")" // Log imported constants
  );

  // Automatically open the side panel on install/update during development
  // Note: chrome.sidePanel.open() typically requires a user gesture,
  // but onInstalled sometimes works for development reloads.
  if (import.meta.env.DEV) {
    chrome.runtime.onInstalled.addListener(async (details) => {
      // Only run on development install/update
      if (details.reason === "install" || details.reason === "update") {
        console.log(
          `[DEV] Extension ${details.reason}ed. Attempting to open side panel...`
        );
        try {
          // We need to specify the window ID to open the global side panel.
          // Using getLastFocused is generally safer than getCurrent() here.
          const window = await chrome.windows.getLastFocused();
          if (window?.id) {
            await chrome.sidePanel.open({ windowId: window.id });
            console.log(
              `[DEV] Side panel open call successful for window ${window.id}.`
            );
          } else {
            console.warn(
              "[DEV] Could not get window ID to open side panel (no focused window?)."
            );
          }
        } catch (error) {
          console.error("[DEV] Error opening side panel:", error);
          console.warn(
            "[DEV] Note: Automatic side panel opening might fail without a direct user gesture or if no window is focused."
          );
        }
      }
    });
  }

  // Also allow opening via the action icon click (works in dev and prod)
  chrome.sidePanel
    .setPanelBehavior({ openPanelOnActionClick: true })
    .catch((error) => console.error("Failed to set panel behavior:", error));

  
  // --- NEW: Upload JSON to backend when we receive the STOP_RECORDING event ---
  chrome.runtime.onMessage.addListener(async (msg) => {
    // the side-panel sends this when the user clicks "Download JSON"
    if (msg.type !== 'STOP_RECORDING') return;
 
    try {
      /* 1. we already have the latest trace in memory – broadcastWorkflowDataUpdate() assembles it */
      const workflow = await broadcastWorkflowDataUpdate();
 
      // 🔄 NEW: Get session token (need to import ensureAuth if not already)
      // Note: This might need to be refactored since background scripts have different context
      // For now, commenting out automatic upload from background to avoid auth issues
      console.log('🔄 [Background] Automatic upload disabled - user should use sidepanel upload');
      
      /* COMMENTED OUT - Use sidepanel upload instead
      const res = await fetch(`${import.meta.env.VITE_API_URL}/workflows/upload/session`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          recording: workflow,
          goal: "Automated workflow",
          name: workflow.name ?? "Untitled workflow",
          session_token: sessionToken, // Need to get this from auth context
        }),
      });
 
      if (!res.ok) throw new Error(`Backend returned ${res.status}`);
 
      const result = await res.json();
      const job_id = result.job_id;
 
      // 2. open processing page
      chrome.tabs.create({
        url: `${import.meta.env.VITE_APP_ORIGIN}/wf/processing/${job_id}`,
      });
      */
    } catch (err) {
      console.error('[workflow-use] background process failed:', err);
      chrome.notifications.create({
        type: 'basic',
        iconUrl: chrome.runtime.getURL('icon/48.png'),
        title: 'Background process failed',
        message: String(err),
      });
    }
  });

  // --- Register content script for all pages ---
  // We need to do this to be able to listen to events from all tabs.
});
