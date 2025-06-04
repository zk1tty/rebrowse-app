// Placeholder for JS_TEMPLATE
(function () { // Main IIFE
  console.log('[UIT SCRIPT] Attempting to run on URL:', location.href, 'Is top window:', window.top === window, 'Timestamp:', Date.now());

  if (window.top !== window) {
    console.log('[UIT SCRIPT] EXIT (not top window) on URL:', location.href);
    return;
  }

  if (window.top.__uit_global_listeners_attached) {
    console.log('[UIT SCRIPT] GUARDED (globally, listeners already attached by a previous script instance in this tab) on URL:', location.href);
    return; 
  }

  console.log('[UIT SCRIPT] PASSED GLOBAL GUARD: Marking tab as having listeners and proceeding to setup for URL:', location.href);
  window.top.__uit_global_listeners_attached = true;

  // const binding = '__uit_relay'; // Binding name, not directly used by postMessage but kept for context if needed

  function send(type, eventData) {
      if (eventData.repeat && type === 'keydown') return;

      function smartSelector(el) {
        if (!document || !document.documentElement) { console.warn('[UIT SCRIPT] smartSelector: documentElement not available'); return ''; }
        if (!el || el.nodeType !== 1) return '';
        if (el.id) return '#' + CSS.escape(el.id);
        const attrs = ['data-testid','aria-label','role','name','placeholder'];
        for (const a of attrs) {
            const v = el.getAttribute(a);
            if (v) { const sel_val = el.localName + '[' + a + '="' + CSS.escape(v) + '"]'; try { if (document.querySelectorAll(sel_val).length === 1) return sel_val; } catch (err) {} }
        }
        let path = '', depth = 0, node = eventData.target || el; 
        while (node && node.nodeType === 1 && node !== document.documentElement && depth < 10) {
            let seg = node.localName;
            if (node.parentElement) { const children = node.parentElement.children; const sib = Array.from(children || []).filter(s => s.localName === seg); if (sib.length > 1) { const idx = sib.indexOf(node); if (idx !== -1) { seg += ':nth-of-type(' + (idx + 1) + ')'; } } }
            path = path ? seg + '>' + path : seg;
            try { if (document.querySelectorAll(path).length === 1) return path; } catch (err) {} 
            if (!node.parentElement) break; node = node.parentElement; depth++;
        }
        return path || (node && node.localName ? node.localName : '');
      }
      
      let selectorForPayload;
      if (type === 'clipboard_copy' && eventData && typeof eventData.text !== 'undefined' && typeof eventData.target === 'undefined') {
          selectorForPayload = smartSelector(document.activeElement) || 'document.body'; 
      } else if (eventData && eventData.target) {
          selectorForPayload = smartSelector(eventData.target);
      } else { 
          selectorForPayload = smartSelector(document.activeElement);
      }

      const payload = { 
        type: type, 
        originalEventType: eventData?.type, 
        ts: Date.now(),
        url: document.location.href,
        selector: selectorForPayload,
        x: eventData?.clientX ?? null,
        y: eventData?.clientY ?? null,
        button: eventData?.button ?? null,
        key: eventData?.key ?? null,
        code: eventData?.code ?? null,
        modifiers: {alt:eventData?.altKey || false ,ctrl:eventData?.ctrlKey || false ,shift:eventData?.shiftKey || false ,meta:eventData?.metaKey || false},
        text: (eventData && typeof eventData.text !== 'undefined') ? eventData.text : 
              (type === 'mousedown' && eventData?.target?.innerText) ? (eventData.target.innerText || '').trim().slice(0,50) :
              ((eventData?.target?.value || '').trim().slice(0,50) || null),
        file_path: eventData?.file_path ?? null, 
        file_name: eventData?.file_name ?? null
      };
                                  
      // console.log('[UIT SCRIPT DEBUG] Posting message to window:', payload.type, payload); // Commented out for housekeeping
      window.postMessage({ __REBROWSE_UI_EVENT__: true, payload: payload }, '*');
      // console.log('[UIT SCRIPT] Posted message to window:', payload.type);
  } 

  // ---- Clipboard-API interception (navigator.clipboard.writeText) ----
  (function () { 
    if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
      const _origWriteText = navigator.clipboard.writeText.bind(navigator.clipboard);
      navigator.clipboard.writeText = async function (textArgument) { 
        // console.log('[UIT SCRIPT] Intercepted navigator.clipboard.writeText, text:', textArgument ? String(textArgument).slice(0,30) : '<empty>');
        try { await _origWriteText(textArgument); }
        finally { send("clipboard_copy", { "text": textArgument }); } 
      };
      console.log('[UIT SCRIPT] Patched navigator.clipboard.writeText');
    } else {
      // console.log('[UIT SCRIPT] navigator.clipboard.writeText not found or not a function, skipping patch.');
    }
  })(); 

  // ---- execCommand("copy") interception ----
  (function () { 
    if (typeof document.execCommand === 'function') {
      const _origExec = document.execCommand.bind(document);
      document.execCommand = function (cmd, showUI, val) {
        const ok = _origExec(cmd, showUI, val);
        if (cmd === "copy" && ok) {
          // console.log('[UIT SCRIPT] Intercepted document.execCommand("copy")');
          if (navigator.clipboard && typeof navigator.clipboard.readText === 'function') {
            navigator.clipboard.readText().then(
              (clipboardText) => { /*console.log('[UIT SCRIPT] execCommand copy, readText success, text:', clipboardText ? String(clipboardText).slice(0,30): '<empty>');*/ send("clipboard_copy", { "text": clipboardText }); }, 
              ()     => { /*console.log('[UIT SCRIPT] execCommand copy, readText failed, sending empty');*/ send("clipboard_copy", { "text": "" }); } 
            );
          } else {
            // console.log('[UIT SCRIPT] execCommand copy, navigator.clipboard.readText not available, sending empty for copy.');
            send("clipboard_copy", { "text": "" }); 
          }
        }
        return ok;
      };
      console.log('[UIT SCRIPT] Patched document.execCommand');
    } else {
      // console.log('[UIT SCRIPT] document.execCommand not found or not a function, skipping patch.');
    }
  })(); 

  function actualListenerSetup() { 
    console.log('[UIT SCRIPT] actualListenerSetup: Called for document of URL:', document.location.href);
    document.addEventListener('mousedown', e => send('mousedown', e), true);
    document.addEventListener('keydown',   e => send('keydown',   e), true);
    
    document.addEventListener('copy',  e => { 
        // console.log('[UIT SCRIPT] Native "copy" event triggered.');
        const selectedText = window.getSelection().toString();
        send('clipboard_copy', { target: e.target, "text": selectedText }); 
    }, true);
    document.addEventListener('paste', e => send('paste', e), true); 

    const delegatedFileChangeListener = (e) => { 
        const tgt = e.target;
        if (!tgt || tgt.nodeType !== 1) return;
        if (tgt.tagName === 'INPUT' && tgt.type === 'file') {
            const file = tgt.files && tgt.files.length > 0 ? tgt.files[0] : null;
            send('file_upload', { target: tgt, file_path: 'N/A_in_extension_context', file_name: file?.name ?? '' }); 
        }
    };

    document.addEventListener('change', delegatedFileChangeListener, true);
    document.addEventListener('drop', (e) => { 
        if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            const file = e.dataTransfer.files[0];
            send('file_upload', { target: e.target, file_path: 'N/A_in_extension_context', file_name: file?.name ?? '' });
        }
    }, true);
    console.log('[UIT SCRIPT] actualListenerSetup: Event listeners ATTACHED to document of URL:', document.location.href);
  } 

  function initializeListeners() {
    // console.log('[UIT SCRIPT] initializeListeners: Checking document state for URL:', document.location.href);
    if (document.readyState === 'loading') {
      // console.log('[UIT SCRIPT] Document still loading, deferring actualListenerSetup for URL:', document.location.href);
      document.addEventListener('DOMContentLoaded', actualListenerSetup);
    } else {
      // console.log('[UIT SCRIPT] Document already loaded (or interactive), calling actualListenerSetup for URL:', document.location.href);
      actualListenerSetup();
    }
  }
  
  initializeListeners();

})(); // End of Main IIFE