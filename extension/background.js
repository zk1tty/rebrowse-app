// background.js
let NATIVE_PORT = null;
let portConnectInProgress = false;
const HOST_NAME = 'com.rebrowse.host';
let isNativeHostReady = false;
// Simple FIFO queue to buffer outbound messages when the native host is not ready.
// Each entry is a plain JS object that will be passed as-is to NATIVE_PORT.postMessage when flushed.
// FIX: The outbound queue in background.js had been disabled, if native post isn't ready yet.
const MESSAGE_QUEUE_MAX = 500;
let messageQueue = [];

function setupNativePortListeners(port) {
  port.onMessage.addListener(msg => {
    if (port !== NATIVE_PORT && NATIVE_PORT !== null) { 
        console.log("[Rebrowse BG] Received message from an old/stale port. Ignoring type:", msg.type);
        return;
    }

    if (msg.type === 'inject') {
      if (msg.tabId && msg.payload) {
        chrome.tabs.sendMessage(msg.tabId, msg.payload).catch(e => console.warn("[Rebrowse BG] ⚠️ Error sending inject message to tab:", e.message));
      }
    } else if (msg.type === 'status' && msg.message === 'Native host ready and listening for CDP.') {
      console.log('[Rebrowse BG] ✓ Native host signaled ready. Current NATIVE_PORT matched. Sending ack.');
      isNativeHostReady = true; 
      portConnectInProgress = false;
      try {
          if (NATIVE_PORT === port) { 
            NATIVE_PORT.postMessage({ type: "client_ready_ack", message: "Extension acknowledged host readiness." });
            console.log("[Rebrowse BG] ► Sending initial PING to host after ACK.");
            NATIVE_PORT.postMessage({ type: "extension_ping", data: "keep_alive" });
            processMessageQueue();
          } else {
            console.warn("[Rebrowse BG] ⚠️ Port changed before client_ready_ack/ping could be sent (in host ready handler).");
            isNativeHostReady = false; 
          }
      } catch (e) {
          console.error("[Rebrowse BG] ❌ Error sending client_ready_ack or ping:", e.message);
          isNativeHostReady = false; 
          if (NATIVE_PORT === port) { try { port.disconnect(); } catch (ex){} NATIVE_PORT = null; portConnectInProgress = false; setTimeout(ensureNativeConnection, 500); }
      }
    } else if (msg.type === 'ack') {
      console.log(`[Rebrowse BG] ✓ Received ACK from Host for ${msg.received_event_type}: ${msg.details}`);
    }
  });

  port.onDisconnect.addListener(() => {
    console.error(`[Rebrowse BG] 🔌 Native port disconnected.`);
    if (chrome.runtime.lastError) {
      console.error('[Rebrowse BG] Disconnect reason:', chrome.runtime.lastError.message);
    } else {
      console.warn('[Rebrowse BG] ⚠️ Native port disconnected without a specific chrome.runtime.lastError.');
    }

    if (NATIVE_PORT === port || NATIVE_PORT === null) {
      NATIVE_PORT = null; 
      isNativeHostReady = false; 
      portConnectInProgress = false;
      console.log('[Rebrowse BG] ► Current native port nulled by onDisconnect. Attempting to reconnect in 1 second...');
      setTimeout(ensureNativeConnection, 1000);
    }
  });
}

function ensureNativeConnection() {
  if (NATIVE_PORT && isNativeHostReady) { 
    return true;
  }
  if (portConnectInProgress) {
    console.log("[Rebrowse BG] ► Port connection attempt already in progress. Not starting new one.");
    return false; 
  }

  console.log(`[Rebrowse BG] ► Attempting to connect to native host '${HOST_NAME}'...`);
  isNativeHostReady = false; 
  portConnectInProgress = true;
  try {
    const newPort = chrome.runtime.connectNative(HOST_NAME); 
    NATIVE_PORT = newPort; 
    console.log("[Rebrowse BG] ✓ Native port object created. Setting up listeners.");
    setupNativePortListeners(newPort); 
    return true; 
  } catch (e) {
    console.error("[Rebrowse BG] ❌ CRITICAL ERROR during chrome.runtime.connectNative:", e.message);
    if (NATIVE_PORT) { 
        try { NATIVE_PORT.disconnect(); } catch(ex){ console.warn("[Rebrowse BG] ⚠️ Error disconnecting potentially bad port during connectNative failure:", ex.message); }
    }
    NATIVE_PORT = null;
    isNativeHostReady = false;
    portConnectInProgress = false;
    console.log('[Rebrowse BG] ► Scheduling retry connection in 2 seconds due to critical connection error...');
    setTimeout(ensureNativeConnection, 2000); 
    return false;
  }
}

// DIAGNOSTIC: Simplified postMessageToNativeHost without queueing
function postMessageToNativeHost(messageObject) {
  if (!NATIVE_PORT || !isNativeHostReady) {
    // Host is not currently ready. Buffer the message for later.
    if (messageQueue.length < MESSAGE_QUEUE_MAX) {
      messageQueue.push(messageObject);
      console.warn(`[Rebrowse BG] ⚠️ postMessage: Host not ready – queued message of type ${messageObject.type}. Queue length now ${messageQueue.length}.`);
    } else {
      console.error(`[Rebrowse BG] ❌ postMessage: MESSAGE_QUEUE_MAX (${MESSAGE_QUEUE_MAX}) reached, dropping message of type ${messageObject.type}.`);
    }

    // Kick off (or retry) connection attempts so the queue will eventually flush.
    ensureNativeConnection();
    return;
  }

  console.log(`[Rebrowse BG] ►► postMessage: Port valid & host ready. Attempting send for type: ${messageObject.type}`);
  try {
    NATIVE_PORT.postMessage(messageObject);
    console.log(`[Rebrowse BG] ✓✓ postMessage: Successfully posted message to Host: ${messageObject.type}`);
  } catch (e) {
    console.error(`[Rebrowse BG] ❌ postMessage: IMMEDIATE ERROR posting message ${messageObject.type}:`, e.message);
    if (chrome.runtime.lastError) {
        console.error(`[Rebrowse BG] ❌ chrome.runtime.lastError after post:`, chrome.runtime.lastError.message);
    }
    isNativeHostReady = false; 
    if (NATIVE_PORT) {
        try { NATIVE_PORT.disconnect(); } catch (ex) { /* ignore */ }
    }
    NATIVE_PORT = null;
    portConnectInProgress = false;
    console.log('[Rebrowse BG] ► Error during post. Triggering ensureNativeConnection immediately.');
    ensureNativeConnection();
    // The send failed; push the message back onto the head of the queue for a retry.
    messageQueue.unshift(messageObject);
  }
}

function processMessageQueue() {
  if (!NATIVE_PORT || !isNativeHostReady) {
    return; // Nothing to do, will retry when connection established.
  }

  while (messageQueue.length > 0) {
    const msg = messageQueue.shift();
    try {
      NATIVE_PORT.postMessage(msg);
      console.log(`[Rebrowse BG] ✓✓ Flushed queued message to Host: ${msg.type}. Remaining queue length: ${messageQueue.length}`);
    } catch (e) {
      console.error(`[Rebrowse BG] ❌ Error flushing queued message of type ${msg.type}:`, e.message);
      // Put the message back and break – we'll retry later.
      messageQueue.unshift(msg);
      if (NATIVE_PORT) {
        try { NATIVE_PORT.disconnect(); } catch (_) {}
      }
      NATIVE_PORT = null;
      isNativeHostReady = false;
      ensureNativeConnection();
      break;
    }
  }
}

console.log("[Rebrowse BG] Script evaluated. Initializing native connection...");
ensureNativeConnection(); 

chrome.runtime.onInstalled.addListener(() => {
  console.log('[Rebrowse BG] ✨ Extension installed/updated - background.js ready');
  ensureNativeConnection(); 
});

chrome.tabs.onActivated.addListener(({ tabId }) => {
  console.log(`[Rebrowse BG] ► Tab activated: ${tabId}. Triggering attach logic.`);
  attemptToAttachDebugger(tabId);
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url) {
    console.log(`[Rebrowse BG] ► Tab updated: ${tabId}, status: 'complete', url: ${tab.url}. Triggering attach logic.`);
    attemptToAttachDebugger(tabId);
  }
});

async function attemptToAttachDebugger(tabId) {
  let tabInfo;
  try {
    tabInfo = await chrome.tabs.get(tabId);
  } catch (e) {
    console.warn(`[Rebrowse BG] ⚠️ Failed to get tab info for tabId ${tabId}:`, e.message);
    return; 
  }

  if (!tabInfo || !tabInfo.url) {
    console.log(`[Rebrowse BG] ⏭️ Skipping debugger attach for tabId ${tabId}: No URL info or tab closed.`);
    return;
  }

  if (tabInfo.url.startsWith('chrome://') || tabInfo.url.startsWith('devtools://') || tabInfo.url.startsWith('chrome-extension://')) {
    console.log(`[Rebrowse BG] ⏭️ Skipping debugger attach for protected URL: ${tabInfo.url} on tab ${tabId}`);
    return;
  }

  try {
    const attachedTargets = await chrome.debugger.getTargets();
    const isAttached = attachedTargets.some(target => target.tabId === tabId && target.attached);

    if (isAttached) {
      console.log(`[Rebrowse BG] ✓ Debugger already attached to tab ${tabId} (${tabInfo.url}).`);
      return;
    }

    console.log(`[Rebrowse BG] ► Attaching debugger to tab ${tabId} (${tabInfo.url}).`);
    await chrome.debugger.attach({ tabId }, '1.3');
    console.log(`[Rebrowse BG] ✓ Successfully attached CDP to tab ${tabId} (${tabInfo.url})`);

    try {
      await chrome.debugger.sendCommand({ tabId }, "Page.enable");
      console.log(`[Rebrowse BG] ✓ Page domain enabled for tab ${tabId}`);
      await chrome.debugger.sendCommand({ tabId }, "Network.enable");
      console.log(`[Rebrowse BG] ✓ Network domain enabled for tab ${tabId}`);
      await chrome.debugger.sendCommand({ tabId }, "Runtime.enable");
      console.log(`[Rebrowse BG] ✓ Runtime domain enabled for tab ${tabId}`);
    } catch (e) {
      console.error(`[Rebrowse BG] ❌ Error enabling CDP domains for tab ${tabId}:`, e.message);
    }

  } catch (e) {
    console.error(`[Rebrowse BG] ❌ Debugger attach failed for tab ${tabId} (${tabInfo.url}):`, e.message);
  }
}

const cdpEventListener = (debuggeeId, method, params) => {
  const tabId = debuggeeId.tabId;
  if (tabId) {
    postMessageToNativeHost({ type: 'cdp', method, params, tabId });
  } else {
    console.warn("[Rebrowse BG] ⚠️ CDP Event received without tabId in debuggeeId:", debuggeeId, method);
  }
};

try {
  if (chrome.debugger.onEvent.hasListener(cdpEventListener)) {
    chrome.debugger.onEvent.removeListener(cdpEventListener);
  }
} catch (e) { /* Best effort */ }
chrome.debugger.onEvent.addListener(cdpEventListener);
console.log("[Rebrowse BG] Global CDP event listener set up.");

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'rebrowse_ui_event' && message.data) {
    const uiEvent = message.data;
    let eventDetails = `type: ${uiEvent.type}`;
    if (uiEvent.type === 'keydown' && typeof uiEvent.key !== 'undefined') {
      eventDetails += `, key: '${uiEvent.key}'`;
    } else if (uiEvent.type === 'mousedown' && typeof uiEvent.selector !== 'undefined') {
      eventDetails += `, selector: '${uiEvent.selector}', button: ${uiEvent.button}`;
    }
    console.log(`[Rebrowse BG] ► Processing UI Event (Tab: ${sender.tab ? sender.tab.id : 'N/A'}): ${eventDetails}`);
    postMessageToNativeHost({ type: 'ui_event_to_host', payload: uiEvent });
    sendResponse({status: `UI event '${uiEvent.type}' received by background.js and attempt to forward was made`});
    return false; 
  }
  return false; 
});

