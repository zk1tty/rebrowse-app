// background.js
const LOG_LEVEL = {
  DEBUG: 0,
  INFO: 1,
  WARN: 2,
  ERROR: 3
};
// Set the current log level for the extension.
// For example, to see DEBUG, INFO, WARN, ERROR messages, set to LOG_LEVEL.DEBUG.
// To see only INFO, WARN, ERROR, set to LOG_LEVEL.INFO, and so on.
const CURRENT_LOG_LEVEL = LOG_LEVEL.DEBUG; // Default to showing all logs for now

function log(level, ...args) {
  if (level < CURRENT_LOG_LEVEL) {
    return;
  }
  // Preserve the existing prefix style
  const prefix = '[Rebrowse BG]';
  switch (level) {
    case LOG_LEVEL.DEBUG:
      console.debug(prefix, ...args);
      break;
    case LOG_LEVEL.INFO:
      // console.info often styles the same as console.log, but is semantically correct.
      console.info(prefix, ...args);
      break;
    case LOG_LEVEL.WARN:
      console.warn(prefix, ...args);
      break;
    case LOG_LEVEL.ERROR:
      console.error(prefix, ...args);
      break;
    default:
      // Fallback for unknown levels, though ideally this shouldn't be hit.
      console.log(prefix, `[UnknownLevel:${level}]`, ...args);
  }
}

let NATIVE_PORT = null;
let portConnectInProgress = false;
const HOST_NAME = 'com.rebrowse.host';
let isNativeHostReady = false;
// Simple FIFO queue to buffer outbound messages when the native host is not ready.
// Each entry is a plain JS object that will be passed as-is to NATIVE_PORT.postMessage when flushed.
// FIX: The outbound queue in background.js had been disabled, if native post isn't ready yet.
const MESSAGE_QUEUE_MAX = 500;
let messageQueue = [];

// NEW: Variable to hold the last known recording status
let currentRecordingStatus = { status: 'idle', message: 'Awaiting host status.' };

function setupNativePortListeners(port) {
  port.onMessage.addListener(msg => {
    if (port !== NATIVE_PORT && NATIVE_PORT !== null) { 
        log(LOG_LEVEL.WARN, "Received message from an old/stale port. Ignoring type:", msg.type);
        return;
    }

    if (msg.type === 'inject') {
      if (msg.tabId && msg.payload) {
        chrome.tabs.sendMessage(msg.tabId, msg.payload).catch(e => log(LOG_LEVEL.WARN, "⚠️ Error sending inject message to tab:", e.message));
      }
    } else if (msg.type === 'status' && msg.message === 'Native host ready and listening for CDP.') {
      log(LOG_LEVEL.INFO, '✓ Native host signaled ready. Current NATIVE_PORT matched. Sending ack.');
      isNativeHostReady = true; 
      portConnectInProgress = false;
      try {
          if (NATIVE_PORT === port) { 
            NATIVE_PORT.postMessage({ type: "client_ready_ack", message: "Extension acknowledged host readiness." });
            log(LOG_LEVEL.INFO, "► Sending initial PING to host after ACK.");
            NATIVE_PORT.postMessage({ type: "extension_ping", data: "keep_alive" });
            processMessageQueue();
          } else {
            log(LOG_LEVEL.WARN, "⚠️ Port changed before client_ready_ack/ping could be sent (in host ready handler).");
            isNativeHostReady = false; 
          }
      } catch (e) {
          log(LOG_LEVEL.ERROR, "❌ Error sending client_ready_ack or ping:", e.message);
          isNativeHostReady = false; 
          if (NATIVE_PORT === port) { try { port.disconnect(); } catch (ex){} NATIVE_PORT = null; portConnectInProgress = false; setTimeout(ensureNativeConnection, 500); }
      }
    } else if (msg.type === 'ack') {
      // Specific request to move cdp_event and ui_event ACKs to DEBUG
      if (msg.received_event_type === 'cdp_event' || msg.received_event_type === 'ui_event') {
        log(LOG_LEVEL.DEBUG, `✓ ACK: Host ➜ ${msg.received_event_type}: ${msg.details}`);
      } else {
        log(LOG_LEVEL.INFO, `✓ ACK: Host ➜ ${msg.received_event_type}: ${msg.details}`);
      }
    } else if (msg.type === 'recording_status_update') {
      log(LOG_LEVEL.INFO, `[Rebrowse BG] Received recording_status_update from host:`, msg.payload);
      // Store the latest status
      currentRecordingStatus = msg.payload;
      // Forward this to the popup
      chrome.runtime.sendMessage({ type: 'recording_status', data: msg.payload }).catch(e => {
        log(LOG_LEVEL.WARN, "[Rebrowse BG] Error sending recording_status to popup (popup might be closed):", e.message);
      });
    }
  });

  port.onDisconnect.addListener(() => {
    log(LOG_LEVEL.ERROR, `🔌 Native port disconnected.`);
    if (chrome.runtime.lastError) {
      log(LOG_LEVEL.ERROR, 'Disconnect reason:', chrome.runtime.lastError.message);
    } else {
      log(LOG_LEVEL.WARN, '⚠️ Native port disconnected without a specific chrome.runtime.lastError.');
    }

    if (NATIVE_PORT === port || NATIVE_PORT === null) {
      NATIVE_PORT = null; 
      isNativeHostReady = false; 
      portConnectInProgress = false;
      // Also reset recording status on disconnect, as we don't know the state anymore.
      currentRecordingStatus = { status: 'error', message: 'Host disconnected.' };
      log(LOG_LEVEL.INFO, '► Current native port nulled by onDisconnect. Attempting to reconnect in 1 second...');
      setTimeout(ensureNativeConnection, 1000);
    }
  });
}

function ensureNativeConnection() {
  if (NATIVE_PORT && isNativeHostReady) { 
    return true;
  }
  if (portConnectInProgress) {
    log(LOG_LEVEL.DEBUG, "► Port connection attempt already in progress. Not starting new one.");
    return false; 
  }

  log(LOG_LEVEL.INFO, `► Attempting to connect to native host '${HOST_NAME}'...`);
  isNativeHostReady = false; 
  portConnectInProgress = true;
  try {
    const newPort = chrome.runtime.connectNative(HOST_NAME); 
    NATIVE_PORT = newPort; 
    log(LOG_LEVEL.INFO, "✓ Native port object created. Setting up listeners.");
    setupNativePortListeners(newPort); 
    return true; 
  } catch (e) {
    log(LOG_LEVEL.ERROR, "❌ CRITICAL ERROR during chrome.runtime.connectNative:", e.message);
    if (NATIVE_PORT) { 
        try { NATIVE_PORT.disconnect(); } catch(ex){ log(LOG_LEVEL.WARN, "⚠️ Error disconnecting potentially bad port during connectNative failure:", ex.message); }
    }
    NATIVE_PORT = null;
    isNativeHostReady = false;
    portConnectInProgress = false;
    log(LOG_LEVEL.INFO, '► Scheduling retry connection in 2 seconds due to critical connection error...');
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
      log(LOG_LEVEL.WARN, `⚠️ postMessage: Host not ready – queued message of type ${messageObject.type}. Queue length now ${messageQueue.length}.`);
    } else {
      log(LOG_LEVEL.ERROR, `❌ postMessage: MESSAGE_QUEUE_MAX (${MESSAGE_QUEUE_MAX}) reached, dropping message of type ${messageObject.type}.`);
    }

    // Kick off (or retry) connection attempts so the queue will eventually flush.
    ensureNativeConnection();
    return;
  }

  log(LOG_LEVEL.DEBUG, `►► postMessage: Port valid & host ready. Attempting send for type: ${messageObject.type}`);
  try {
    NATIVE_PORT.postMessage(messageObject);
    log(LOG_LEVEL.DEBUG, `✓✓ postMessage: Successfully posted message to Host: ${messageObject.type}`);
  } catch (e) {
    log(LOG_LEVEL.ERROR, `❌ postMessage: IMMEDIATE ERROR posting message ${messageObject.type}:`, e.message);
    if (chrome.runtime.lastError) {
        log(LOG_LEVEL.ERROR, `❌ chrome.runtime.lastError after post:`, chrome.runtime.lastError.message);
    }
    isNativeHostReady = false; 
    if (NATIVE_PORT) {
        try { NATIVE_PORT.disconnect(); } catch (ex) { /* ignore */ }
    }
    NATIVE_PORT = null;
    portConnectInProgress = false;
    log(LOG_LEVEL.INFO, '► Error during post. Triggering ensureNativeConnection immediately.');
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
      log(LOG_LEVEL.INFO, `✓✓ Flushed queued message to Host: ${msg.type}. Remaining queue length: ${messageQueue.length}`);
    } catch (e) {
      log(LOG_LEVEL.ERROR, `❌ Error flushing queued message of type ${msg.type}:`, e.message);
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

log(LOG_LEVEL.INFO, "Script evaluated. Initializing native connection...");
ensureNativeConnection(); 

chrome.runtime.onInstalled.addListener(() => {
  log(LOG_LEVEL.INFO, '✨ Extension installed/updated - background.js ready');
  ensureNativeConnection(); 
});

chrome.tabs.onActivated.addListener(({ tabId }) => {
  log(LOG_LEVEL.INFO, `► Tab activated: ${tabId}. Triggering attach logic.`);
  attemptToAttachDebugger(tabId);
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url) {
    log(LOG_LEVEL.INFO, `► Tab updated: ${tabId}, status: 'complete', url: ${tab.url}. Triggering attach logic.`);
    attemptToAttachDebugger(tabId);
  }
});

async function attemptToAttachDebugger(tabId) {
  let tabInfo;
  try {
    tabInfo = await chrome.tabs.get(tabId);
  } catch (e) {
    log(LOG_LEVEL.WARN, `⚠️ Failed to get tab info for tabId ${tabId}:`, e.message);
    return; 
  }

  if (!tabInfo || !tabInfo.url) {
    log(LOG_LEVEL.DEBUG, `⏭️ Skipping debugger attach for tabId ${tabId}: No URL info or tab closed.`);
    return;
  }

  if (tabInfo.url.startsWith('chrome://') || tabInfo.url.startsWith('devtools://') || tabInfo.url.startsWith('chrome-extension://')) {
    log(LOG_LEVEL.INFO, `⏭️ Skipping debugger attach for protected URL: ${tabInfo.url} on tab ${tabId}`);
    return;
  }

  try {
    const attachedTargets = await chrome.debugger.getTargets();
    const isAttached = attachedTargets.some(target => target.tabId === tabId && target.attached);

    if (isAttached) {
      log(LOG_LEVEL.DEBUG, `✓ Debugger already attached to tab ${tabId} (${tabInfo.url}).`);
      return;
    }

    log(LOG_LEVEL.INFO, `► Attaching debugger to tab ${tabId} (${tabInfo.url}).`);
    await chrome.debugger.attach({ tabId }, '1.3');
    log(LOG_LEVEL.INFO, `✓ Successfully attached CDP to tab ${tabId} (${tabInfo.url})`);

    try {
      await chrome.debugger.sendCommand({ tabId }, "Page.enable");
      log(LOG_LEVEL.DEBUG, `✓ Page domain enabled for tab ${tabId}`);
      await chrome.debugger.sendCommand({ tabId }, "Network.enable");
      log(LOG_LEVEL.DEBUG, `✓ Network domain enabled for tab ${tabId}`);
      await chrome.debugger.sendCommand({ tabId }, "Runtime.enable");
      log(LOG_LEVEL.DEBUG, `✓ Runtime domain enabled for tab ${tabId}`);
    } catch (e) {
      log(LOG_LEVEL.ERROR, `❌ Error enabling CDP domains for tab ${tabId}:`, e.message);
    }

  } catch (e) {
    log(LOG_LEVEL.ERROR, `❌ Debugger attach failed for tab ${tabId} (${tabInfo.url}):`, e.message);
  }
}

const cdpEventListener = (debuggeeId, method, params) => {
  const tabId = debuggeeId.tabId;
  if (tabId) {
    postMessageToNativeHost({ type: 'cdp', method, params, tabId });
  } else {
    log(LOG_LEVEL.WARN, "⚠️ CDP Event received without tabId in debuggeeId:", debuggeeId, method);
  }
};

try {
  if (chrome.debugger.onEvent.hasListener(cdpEventListener)) {
    chrome.debugger.onEvent.removeListener(cdpEventListener);
  }
} catch (e) { /* Best effort */ }
chrome.debugger.onEvent.addListener(cdpEventListener);
log(LOG_LEVEL.INFO, "Global CDP event listener set up.");

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.source === 'popup' && message.action === 'start_recording') {
    log(LOG_LEVEL.INFO, '[Rebrowse BG] Received start_recording command from popup.');
    postMessageToNativeHost({ type: 'recording_command', command: 'START' });
    // Optional: send an immediate acknowledgement back to popup if needed, 
    // but actual status will come from host.py later.
    sendResponse({ status: 'start_recording_command_sent_to_host' });
    return true; // Indicates you wish to send a response asynchronously (or synchronously)
  } else if (message.source === 'popup' && message.action === 'stop_recording') {
    log(LOG_LEVEL.INFO, '[Rebrowse BG] Received stop_recording command from popup.');
    postMessageToNativeHost({ type: 'recording_command', command: 'STOP' });
    sendResponse({ status: 'stop_recording_command_sent_to_host' });
    return true;
  } else if (message.source === 'popup' && message.action === 'get_recording_status') {
    log(LOG_LEVEL.INFO, `[Rebrowse BG] Popup requested recording status. Sending current status:`, currentRecordingStatus);
    sendResponse({ type: 'recording_status', data: currentRecordingStatus });
    // To prevent the "message port closed" error, it's safest to always
    // return true from a listener that sends a response.
    return true;
  }
  // Keep existing UI event handling
  else if (message.type === 'rebrowse_ui_event' && message.data) {
    const uiEvent = message.data;
    let eventDetails = `type: ${uiEvent.type}`;
    if (uiEvent.type === 'keydown' && typeof uiEvent.key !== 'undefined') {
      eventDetails += `, key: '${uiEvent.key}'`;
    } else if (uiEvent.type === 'mousedown' && typeof uiEvent.selector !== 'undefined') {
      eventDetails += `, selector: '${uiEvent.selector}', button: ${uiEvent.button}`;
    }
    log(LOG_LEVEL.INFO, `►► UI Event (Tab: ${sender.tab ? sender.tab.id : 'N/A'}): ${eventDetails}`);
    postMessageToNativeHost({ type: 'ui_event_to_host', payload: uiEvent });
    sendResponse({status: `UI event '${uiEvent.type}' received by background.js and attempt to forward was made`});
    return false; // No async response needed beyond this for UI events handled here.
  }
  // If the message is not handled by the new popup commands or existing UI event handling,
  // return false or nothing to indicate no response will be sent.
  // log(LOG_LEVEL.DEBUG, "[Rebrowse BG] onMessage: No handler for this message type", message);
  return false; 
});

