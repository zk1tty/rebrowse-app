// content.js

// 1. Inject js_template.js as a <script> tag so it runs in the page's context.
//    This allows it to attach its own event listeners directly to the page's document.
(function() {
  const s = document.createElement('script');
  s.src = chrome.runtime.getURL('js_template.js');
  (document.head || document.documentElement).appendChild(s);
  s.onload = function() {
    // console.log('[Rebrowse content.js] js_template.js loaded and executed.');
    // s.remove(); // Removing the script tag after execution is good practice.
  };
  s.onerror = function() {
    console.error('[Rebrowse content.js] Failed to load js_template.js – falling back to in-content listeners.');
    // If the page blocked script injection (e.g. due to a strict CSP), we still want to
    // capture the most important UI events. We therefore attach a pared-down listener
    // set directly from the content-script isolated world.  Because this world cannot
    // patch page-scope APIs such as navigator.clipboard, we only forward keyboard and
    // mouse interactions here.  The event payload is kept intentionally similar to the
    // format produced by the main js_template.js script so the backend can treat both
    // uniformly.

    if (window.__rebrowse_fallback_attached) {
      return; // Guard against double-attachment.
    }
    window.__rebrowse_fallback_attached = true;

    function buildPayload(type, e) {
      const payload = {
        type,
        originalEventType: e.type,
        ts: Date.now(),
        url: document.location.href,
        selector: (() => {
          // A very small selector helper (id preferred, else tagName).
          try {
            if (e.target && e.target.id) return '#' + e.target.id;
            return e.target ? e.target.tagName.toLowerCase() : '';
          } catch (_) { return ''; }
        })(),
        x: e.clientX ?? null,
        y: e.clientY ?? null,
        button: e.button ?? null,
        key: e.key ?? null,
        code: e.code ?? null,
        modifiers: { alt: e.altKey, ctrl: e.ctrlKey, shift: e.shiftKey, meta: e.metaKey },
        text: null
      };
      return payload;
    }

    const forward = (payload) => {
      chrome.runtime.sendMessage({ type: 'rebrowse_ui_event', data: payload }, () => {
        if (chrome.runtime.lastError) {
          console.warn('[Rebrowse content.js] Fallback sendMessage error:', chrome.runtime.lastError.message);
        }
      });
    };

    document.addEventListener('keydown', (e) => {
      if (e.repeat) return;
      forward(buildPayload('keydown', e));
    }, true);

    document.addEventListener('mousedown', (e) => {
      forward(buildPayload('mousedown', e));
    }, true);

    console.log('[Rebrowse content.js] Fallback in-content listeners attached.');
  };
  // It's often better to remove the script tag after it has loaded and run,
  // but ensure its listeners are established globally or persist as needed.
  // For IIFE, removal after load is fine.
  // If js_template.js might take time to set up async listeners, 
  // ensure removal doesn't break it. Given its structure, it should be okay.
  // setTimeout(() => s.remove(), 100); // Delayed removal just in case
})();

// 2. Listen for messages posted from the in-page js_template.js via window.postMessage
window.addEventListener('message', function(event) {
  // We only accept messages from the window itself (same frame)
  if (event.source !== window) {
    return;
  }

  if (event.data && event.data.__REBROWSE_UI_EVENT__ && event.data.payload) {
    // console.log('[Rebrowse content.js] Received UI event from page via postMessage:', event.data.payload); // Commented out for housekeeping
    // Forward this payload to background.js
    chrome.runtime.sendMessage({ type: 'rebrowse_ui_event', data: event.data.payload }, function(response) {
      if (chrome.runtime.lastError) {
        console.error("[Rebrowse content.js] Error sending message to background (async check):", chrome.runtime.lastError.message, chrome.runtime.lastError);
      } else {
        // console.log("[Rebrowse content.js] Message successfully sent to background, response:", response); 
      }
    });
  }
});

// console.log('[Rebrowse content.js] Content script loaded and listener for postMessage is active.'); 