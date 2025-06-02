import json
import time
import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass, asdict, field
from pathlib import Path
import inspect
import collections # For deque for recent_copies

logger = logging.getLogger(__name__)

logger.debug(f"Loading recorder.py module. Timestamp: {time.time()}")

# =====================
# Dataclass definitions
# =====================

@dataclass
class InputEvent:
    timestamp: float
    url: str
    event_type: str

@dataclass
class MouseClickEvent(InputEvent):
    x: int
    y: int
    button: str
    selector: str
    text: str | None = None
    modifiers: List[str] = field(default_factory=list)

@dataclass
class KeyboardEvent(InputEvent):
    key: str
    code: str
    selector: str
    modifiers: List[str] = field(default_factory=list)

@dataclass
class NavigationEvent(InputEvent):
    from_url: Optional[str] = None
    to_url: str = ""

@dataclass
class ClipboardCopyEvent(InputEvent):
    text: str

@dataclass
class ClipboardPasteEvent(InputEvent):
    selector: str

@dataclass
class FileUploadEvent(InputEvent):
    selector: str
    file_path: str          # absolute or ~/relative
    file_name: str          # convenience, basename of file_path

@dataclass
class FileDownloadEvent(InputEvent):
    download_url: str
    suggested_filename: str
    recorded_local_path: Optional[str] = None

# =========================================================
# Main tracker class
# =========================================================

class Recorder:
    """Tracks mouse, keyboard, and navigation events via Playwright + CDP."""

    logger.debug(f"Recorder class is being defined. Timestamp: {time.time()}")
    BINDING = "__uit_relay"

    # Max size for the recent copies deque to prevent unbounded growth
    _MAX_RECENT_COPIES = 20 

    _JS_TEMPLATE = """ 
(function () {{ // Main IIFE - escaped for .format()
  console.log('[UIT SCRIPT] Attempting to run on URL:', location.href, 'Is top window:', window.top === window, 'Timestamp:', Date.now());

  if (window.top !== window) {{
    console.log('[UIT SCRIPT] EXIT (not top window) on URL:', location.href);
    return;
  }}

  if (window.top.__uit_global_listeners_attached) {{
    console.log('[UIT SCRIPT] GUARDED (globally, listeners already attached by a previous script instance in this tab) on URL:', location.href);
    return; 
  }}

  console.log('[UIT SCRIPT] PASSED GLOBAL GUARD: Marking tab as having listeners and proceeding to setup for URL:', location.href);
  window.top.__uit_global_listeners_attached = true;

  const binding = '{binding}'; // Python .format() placeholder

  function send(type, eventData) {{ // JS function, braces escaped for .format()
      if (eventData.repeat && type === 'keydown') return;

      function smartSelector(el) {{ // JS function, braces escaped
        if (!document || !document.documentElement) {{ console.warn('[UIT SCRIPT] smartSelector: documentElement not available'); return ''; }}
        if (!el || el.nodeType !== 1) return '';
        if (el.id) return '#' + CSS.escape(el.id);
        const attrs = ['data-testid','aria-label','role','name','placeholder'];
        for (const a of attrs) {{
            const v = el.getAttribute(a);
            if (v) {{ const sel_val = el.localName + '[' + a + '="' + CSS.escape(v) + '"]'; try {{ if (document.querySelectorAll(sel_val).length === 1) return sel_val; }} catch (err) {{}} }}
        }}
        let path = '', depth = 0, node = eventData.target || el; 
        while (node && node.nodeType === 1 && node !== document.documentElement && depth < 10) {{
            let seg = node.localName;
            if (node.parentElement) {{ const children = node.parentElement.children; const sib = Array.from(children || []).filter(s => s.localName === seg); if (sib.length > 1) {{ const idx = sib.indexOf(node); if (idx !== -1) {{ seg += ':nth-of-type(' + (idx + 1) + ')'; }} }} }}
            path = path ? seg + '>' + path : seg;
            try {{ if (document.querySelectorAll(path).length === 1) return path; }} catch (err) {{}} 
            if (!node.parentElement) break; node = node.parentElement; depth++;
        }}
        return path || (node && node.localName ? node.localName : '');
      }}
      
      let selectorForPayload;
      if (type === 'clipboard_copy' && eventData && typeof eventData.text !== 'undefined' && typeof eventData.target === 'undefined') {{
          selectorForPayload = smartSelector(document.activeElement) || 'document.body'; 
      }} else if (eventData && eventData.target) {{
          selectorForPayload = smartSelector(eventData.target);
      }} else {{ 
          selectorForPayload = smartSelector(document.activeElement);
      }}

      const payload = {{ 
        type: type,
        ts: Date.now(),
        url: document.location.href,
        selector: selectorForPayload,
        x: eventData?.clientX ?? null,
        y: eventData?.clientY ?? null,
        button: eventData?.button ?? null,
        key: eventData?.key ?? null,
        code: eventData?.code ?? null,
        modifiers: {{alt:eventData?.altKey || false ,ctrl:eventData?.ctrlKey || false ,shift:eventData?.shiftKey || false ,meta:eventData?.metaKey || false}},
        text: (eventData && typeof eventData.text !== 'undefined') ? eventData.text : 
              (type === 'mousedown' && eventData?.target?.innerText) ? (eventData.target.innerText || '').trim().slice(0,50) :
              ((eventData?.target?.value || '').trim().slice(0,50) || null),
        file_path: eventData?.file_path ?? null, 
        file_name: eventData?.file_name ?? null
      }};
                                  
      if (typeof window[binding] === 'function') {{ window[binding](payload); }}
      else {{ console.warn('[UIT SCRIPT] send: Binding not ready for type:', type, 'on URL:', document.location.href); }}
  }} // End of send function

  // ---- Clipboard-API interception (navigator.clipboard.writeText) ----
  (function () {{ // IIFE braces escaped
    if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {{
      const _origWriteText = navigator.clipboard.writeText.bind(navigator.clipboard);
      navigator.clipboard.writeText = async function (textArgument) {{ 
        console.log('[UIT SCRIPT] Intercepted navigator.clipboard.writeText, text:', textArgument ? String(textArgument).slice(0,30) : '<empty>');
        try {{ await _origWriteText(textArgument); }}
        finally {{ send("clipboard_copy", {{ "text": textArgument }}); }} 
      }};
      console.log('[UIT SCRIPT] Patched navigator.clipboard.writeText');
    }} else {{
      console.log('[UIT SCRIPT] navigator.clipboard.writeText not found or not a function, skipping patch.');
    }}
  }})(); // End of IIFE

  // ---- execCommand("copy") interception ----
  (function () {{ // IIFE braces escaped
    if (typeof document.execCommand === 'function') {{
      const _origExec = document.execCommand.bind(document);
      document.execCommand = function (cmd, showUI, val) {{
        const ok = _origExec(cmd, showUI, val);
        if (cmd === "copy" && ok) {{
          console.log('[UIT SCRIPT] Intercepted document.execCommand("copy")');
          if (navigator.clipboard && typeof navigator.clipboard.readText === 'function') {{
            navigator.clipboard.readText().then(
              (clipboardText) => {{ console.log('[UIT SCRIPT] execCommand copy, readText success, text:', clipboardText ? String(clipboardText).slice(0,30): '<empty>'); send("clipboard_copy", {{ "text": clipboardText }}); }}, 
              ()     => {{ console.log('[UIT SCRIPT] execCommand copy, readText failed, sending empty'); send("clipboard_copy", {{ "text": "" }}); }} 
            );
          }} else {{
            console.log('[UIT SCRIPT] execCommand copy, navigator.clipboard.readText not available, sending empty for copy.');
            send("clipboard_copy", {{ "text": "" }}); 
          }}
        }}
        return ok;
      }};
      console.log('[UIT SCRIPT] Patched document.execCommand');
    }} else {{
      console.log('[UIT SCRIPT] document.execCommand not found or not a function, skipping patch.');
    }}
  }})(); // End of IIFE

  // Original event listeners
  function actualListenerSetup() {{ // JS function, braces escaped
    console.log('[UIT SCRIPT] actualListenerSetup: Called for document of URL:', document.location.href);
    document.addEventListener('mousedown', e => send('mousedown', e), true);
    document.addEventListener('keydown',   e => send('keydown',   e), true);
    document.addEventListener('copy',  e => {{ // JS arrow function body, braces escaped
        console.log('[UIT SCRIPT] Native "copy" event triggered.');
        const selectedText = window.getSelection().toString();
        send('clipboard_copy', {{ target: e.target, "text": selectedText }}); 
    }}, true);
    document.addEventListener('paste', e => send('paste', e), true); 

    const delegatedFileChangeListener = (e) => {{ // JS arrow function, braces escaped
        const tgt = e.target;
        if (!tgt || tgt.nodeType !== 1) return;
        if (tgt.tagName === 'INPUT' && tgt.type === 'file') {{
            const file = tgt.files && tgt.files.length > 0 ? tgt.files[0] : null;
            send('file_upload', {{ target: tgt, file_path: file?.path ?? '', file_name: file?.name ?? '' }}); 
        }}
    }};

    document.addEventListener('change', delegatedFileChangeListener, true);
    document.addEventListener('drop', (e) => {{ // JS arrow function, braces escaped
        if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {{
            const file = e.dataTransfer.files[0];
            send('file_upload', {{ target: e.target, file_path: file?.path ?? '', file_name: file?.name ?? '' }});
        }}
    }}, true);
    console.log('[UIT SCRIPT] actualListenerSetup: Event listeners ATTACHED to document of URL:', document.location.href);
  }} // End of actualListenerSetup

  function deferredSetupCaller() {{ // JS function, braces escaped
    console.log('[UIT SCRIPT] deferredSetupCaller: Checking binding and document state for URL:', document.location.href);
    if (typeof window[binding] === 'function') {{
      console.log('[UIT SCRIPT] Binding found immediately for document:', document.location.href);
      if (document.readyState === 'loading') {{
        console.log('[UIT SCRIPT] Document still loading, deferring actualListenerSetup for URL:', document.location.href);
        document.addEventListener('DOMContentLoaded', actualListenerSetup);
      }} else {{
        console.log('[UIT SCRIPT] Document already loaded (or interactive), calling actualListenerSetup for URL:', document.location.href);
        actualListenerSetup();
      }}
    }} else {{
      console.log('[UIT SCRIPT] Binding not immediately found for document:', document.location.href, '. Will check again in 10ms.');
      setTimeout(() => {{
        if (typeof window[binding] === 'function') {{
          console.log('[UIT SCRIPT] Binding found after 10ms delay for document:', document.location.href);
          if (document.readyState === 'loading') {{
            console.log('[UIT SCRIPT] Document still loading (after delay), deferring actualListenerSetup for URL:', document.location.href);
            document.addEventListener('DOMContentLoaded', actualListenerSetup);
          }} else {{
            console.log('[UIT SCRIPT] Document already loaded (or interactive, after delay), calling actualListenerSetup for URL:', document.location.href);
            actualListenerSetup();
          }}
        }} else {{
          console.error('[UIT SCRIPT] FATAL: Binding still not found after delay for document:', document.location.href, '. Listeners NOT attached.');
        }}
      }}, 10);
    }}
  }} // End of deferredSetupCaller
  
  deferredSetupCaller();

}})(); // End of Main IIFE
"""

    def __init__(self, *, context: Optional[Any] = None, page: Optional[Any] = None, cdp_client: Optional[Any] = None, event_log_queue: Optional[asyncio.Queue] = None):
        logger.debug(f"Recorder.__init__ called. Timestamp: {time.time()}")
        sig = inspect.signature(self.__class__.__init__)
        logger.debug(f"Recorder.__init__ signature: {sig}")
        logger.debug(f"Recorder.__init__ received event_log_queue type: {type(event_log_queue)}")
        
        if context is None and cdp_client is not None:
            context = cdp_client
        self.context = context
        self.page = page
        self.events: List[InputEvent] = []
        self.is_recording = False
        self.current_url: str = ""
        self._cleanup: List[Callable[[], None]] = []
        self.event_log_queue = event_log_queue
        
        # For de-duplicating copy events
        self._recent_copies: collections.deque[Tuple[str, float]] = collections.deque(maxlen=self._MAX_RECENT_COPIES)
        
        # Ensure _script_source is initialized after _JS_TEMPLATE is available
        self._script_source = "" # Will be properly set after JS update
        self._script_source = self._JS_TEMPLATE.format(binding=self.BINDING)

        logger.debug(f"RECORDER: Initialized with event_log_queue: {type(self.event_log_queue)}")
        logger.debug(f"RECORDER: _script_source length: {len(self._script_source)}") # Log length for verification

    async def start_tracking(self):
        if self.is_recording:
            return True 
        if not self.page:
            logger.error("Recorder: Page is not set, cannot start tracking.")
            return False
        if not self.context: 
            logger.error("Recorder: Context is not set, cannot start tracking.")
            return False
            
        try:
            await self._setup_page_listeners(self.page)
            self.is_recording = True
            self.current_url = self.page.url if self.page else ""
            logger.info("User-input tracking started (listeners configured by Recorder)") # Internal log
            
            # DEBUGGING queue in start_tracking
            logger.debug(f"[Recorder.start_tracking]: self.event_log_queue is {type(self.event_log_queue)}")
            if self.event_log_queue:
                logger.debug(f"[Recorder.start_tracking]: Attempting to put 'Recording started.' onto queue id: {id(self.event_log_queue)}")
                try:
                    self.event_log_queue.put_nowait("Recording started.")
                    logger.debug(f"[Recorder.start_tracking]: Successfully put 'Recording started.' onto queue.")
                except asyncio.QueueFull:
                    logger.warning("Recorder event log queue is full. Could not log 'Recording started.'")
                    logger.debug(f"[Recorder.start_tracking]: FAILED to put 'Recording started.' (QueueFull)")
            else:
                logger.debug(f"[Recorder.start_tracking]: self.event_log_queue is None or False. Skipping put.")
            return True
        except Exception as e: 
            logger.exception(f"Failed to start tracking in Recorder: {e}")
            await self.stop_tracking() 
            return False

    async def stop_tracking(self):
        if not self.is_recording:
            return
        for fn in self._cleanup:
            try:
                fn()
            except Exception as e_cleanup:
                logger.debug(f"Error during cleanup function: {e_cleanup}")
                pass
        self._cleanup.clear()
        self.is_recording = False
        logger.info("User-input tracking stopped") # Internal log

        # DEBUGGING queue in stop_tracking
        logger.debug(f"[Recorder.stop_tracking]: self.event_log_queue is {type(self.event_log_queue)}")
        if self.event_log_queue:
            logger.debug(f"[Recorder.stop_tracking]: Attempting to put 'Recording stopped.' onto queue id: {id(self.event_log_queue)}")
            try:
                self.event_log_queue.put_nowait("Recording stopped.")
                logger.debug(f"[Recorder.stop_tracking]: Successfully put 'Recording stopped.' onto queue.")
            except asyncio.QueueFull:
                logger.warning("Recorder event log queue is full. Could not log 'Recording stopped.'")
                logger.debug(f"[Recorder.stop_tracking]: FAILED to put 'Recording stopped.' (QueueFull)")
        else:
            logger.debug(f"[Recorder.stop_tracking]: self.event_log_queue is None or False. Skipping put.")

    # Renamed from _setup_page to reflect its new role
    async def _setup_page_listeners(self, page):
        """Set up page-specific listeners. Binding and init script are context-level."""
        if not page or page.is_closed():
            logger.warning(f"Attempted to set up listeners on a closed or invalid page: {page.url if page else 'N/A'}")
            return

        logger.debug(f"START: Setting up page-specific listeners for page: {page.url}")

        # 1. Playwright-level navigation listener (for NavigationEvent)
        # Use a wrapper to handle potential errors if page closes before lambda runs
        def playwright_nav_handler(frame):
            if not page.is_closed():
                self._on_playwright_nav(page, frame)
            else:
                logger.debug(f"Page closed, skipping _on_playwright_nav for url: {frame.url if frame else 'N/A'}")

        page.on("framenavigated", playwright_nav_handler)
        self._cleanup.append(lambda: page.remove_listener("framenavigated", playwright_nav_handler) if not page.is_closed() else None)

        # 2. Ensure script is evaluated on all existing frames of this page.
        #    add_init_script on context handles future frames/navigations.
        logger.debug(f"Evaluating main tracking script in all frames for page: {page.url}")
        eval_results = await self._eval_in_all_frames(page, self._script_source)
        logger.debug(f"Finished evaluating main tracking script in all frames for page: {page.url}. Results (per frame): {eval_results}")

        # 3. Listeners for dynamic frames within this specific page to re-evaluate script.
        #    (Optional, as context-level add_init_script should cover new frames, but kept for safety)
        async def safe_eval_on_frame(frame_to_eval):
            if not frame_to_eval.is_detached():
                await self._safe_eval(frame_to_eval, self._script_source)
            else:
                logger.debug("Frame detached, skipping _safe_eval.")
        
        # Store lambdas for removal
        frame_attached_lambda = lambda fr: asyncio.create_task(safe_eval_on_frame(fr))
        frame_navigated_lambda = lambda fr: asyncio.create_task(safe_eval_on_frame(fr))

        page.on("frameattached", frame_attached_lambda)
        page.on("framenavigated", frame_navigated_lambda) # For SPAs or dynamic content loading into frames
        self._cleanup.append(lambda: page.remove_listener("frameattached", frame_attached_lambda) if not page.is_closed() else None)
        self._cleanup.append(lambda: page.remove_listener("framenavigated", frame_navigated_lambda) if not page.is_closed() else None)

        # ---------- NEW ----------
        # Listener for file downloads
        async def _download_listener(download):
            try:
                page_url = page.url
                download_url = download.url
                suggested_filename = download.suggested_filename

                # Define a path to save recorded downloads
                # This should ideally be configurable or relative to a known temp/session directory
                recorded_downloads_dir = Path("./tmp/recorded_downloads") # Example path
                recorded_downloads_dir.mkdir(parents=True, exist_ok=True)
                
                # Ensure unique filename for saved download to prevent overwrites during a session
                timestamp = int(time.time() * 1000)
                unique_filename = f"{timestamp}_{suggested_filename}"
                local_save_path = recorded_downloads_dir / unique_filename

                await download.save_as(str(local_save_path))
                logger.info(f"💾 Download recorded and saved locally: '{suggested_filename}' to '{local_save_path}'")

                evt = FileDownloadEvent(timestamp=time.time(), 
                                        url=page_url, 
                                        event_type="file_download", 
                                        download_url=download_url, 
                                        suggested_filename=suggested_filename,
                                        recorded_local_path=str(local_save_path)) # Store local path
                self.events.append(evt)
                # Original log kept for consistency if needed, but new log above is more informative for recording phase
                # logger.info(f"💾 Download detected: '{suggested_filename}' from {download_url} on page {page_url}")

                user_log_msg_dl = None
                if self.event_log_queue: # Check before defining user_log_msg_dl for this scope
                    user_log_msg_dl = f"💾 File Downloaded: '{suggested_filename}' (saved to recorded_downloads)"
            except Exception as e:
                logger.error(f"Error in download listener during recording: {e}", exc_info=True)
                if self.event_log_queue:
                    user_log_msg_dl = f"⚠️ Error processing download: {e}"
        
            # DEBUGGING queue in _download_listener (after try-except)
            if user_log_msg_dl: # Only try to log if a message was generated
                logger.debug(f"[Recorder._download_listener]: self.event_log_queue is {type(self.event_log_queue)} for msg: '{user_log_msg_dl}'")
                if self.event_log_queue:
                    logger.debug(f"[Recorder._download_listener]: Attempting to put '{user_log_msg_dl}' onto queue id: {id(self.event_log_queue)}")
                    try:
                        self.event_log_queue.put_nowait(user_log_msg_dl)
                        logger.debug(f"[Recorder._download_listener]: Successfully put '{user_log_msg_dl}'.")
                    except asyncio.QueueFull:
                        logger.warning(f"Recorder event log queue full. Dropped: {user_log_msg_dl}")
                        logger.debug(f"[Recorder._download_listener]: FAILED to put '{user_log_msg_dl}' (QueueFull)")
                else:
                     logger.debug(f"[Recorder._download_listener]: self.event_log_queue is None or False. Skipping put for '{user_log_msg_dl}'.")

        page.on("download", _download_listener)
        self._cleanup.append(lambda: page.remove_listener("download", _download_listener) if not page.is_closed() else None)
        # End of NEW

        logger.debug(f"END: Page-specific listeners setup for page: {page.url}")

    # JS → Python bridge
    async def _on_dom_event(self, _src, p: Dict[str, Any]):
        if not self.is_recording:
            return
        try:
            ts = p.get("ts", time.time()*1000)/1000.0
            url = p.get("url", self.current_url)
            raw_modifiers = p.get("modifiers")
            mods = [k for k, v in raw_modifiers.items() if v] if isinstance(raw_modifiers, dict) else []
            typ = p.get("type")
            sel = str(p.get("selector", ""))

            user_log_msg: Optional[str] = None

            if typ == "clipboard_copy":
                text_content = p.get("text")
                if text_content is None: text_content = ""
                else: text_content = str(text_content)

                now = time.time()
                # Token for de-duplication: (text, coarse_timestamp_to_nearest_100ms)
                # Using round(now, 1) for 100ms window; round(now, 2) is 10ms as per user example.
                # Let's use a slightly larger window for robustness, e.g. 200-300ms by adjusting rounding or comparison logic.
                # For simplicity with set, exact text & rounded time is used. Consider a time window for matching if needed.
                token = (text_content, round(now, 1)) # 100ms window

                if token not in self._recent_copies:
                    self._recent_copies.append(token) # deque handles maxlen automatically
                    
                    evt = ClipboardCopyEvent(timestamp=ts, url=url, event_type="clipboard_copy", text=text_content)
                    self.events.append(evt)
                    log_display_text = f"'{text_content[:40] + '...' if len(text_content) > 40 else text_content}'" if text_content else "<empty>"
                    logger.info(f"📋 Copy {log_display_text}")
                    ui_display_text = f"\"{(text_content[:30] + '...') if len(text_content) > 30 else text_content}\"" if text_content else "<empty selection>"
                    user_log_msg = f"📋 Copied: {ui_display_text}"
                else:
                    logger.debug(f"[Recorder._on_dom_event]: Ignoring duplicate clipboard_copy event: {token}")
                    user_log_msg = None # Do not send duplicate to UI log queue
            elif typ == "clipboard_paste":
                evt = ClipboardPasteEvent(timestamp=ts, url=url, event_type="clipboard_paste", selector=sel)
                self.events.append(evt)
                logger.info(f"📋 Paste into {sel}")
                user_log_msg = f"📋 Pasted into element: '{sel}'"
            elif typ == "file_upload":
                file_path_from_payload = p.get("file_path") or ""
                file_name_from_payload = p.get("file_name") or ""
                if not file_name_from_payload and file_path_from_payload:
                    file_name_from_payload = Path(file_path_from_payload).name
                evt = FileUploadEvent(timestamp=ts, url=url, event_type="file_upload", selector=sel, file_path=file_path_from_payload, file_name=file_name_from_payload)
                self.events.append(evt)
                logger.info(f"📤 Upload '{file_name_from_payload}' (path: '{file_path_from_payload}') to {sel}")
                user_log_msg = f"📤 File Uploaded: '{file_name_from_payload}' to element: '{sel}'"
            elif typ == "mousedown":
                button_code = p.get("button") 
                button_name = {0:"left",1:"middle",2:"right"}.get(button_code, "unknown") if isinstance(button_code, int) else "unknown"
                txt = p.get("text")
                x_coord, y_coord = int(p.get("x",0)), int(p.get("y",0))
                evt = MouseClickEvent(timestamp=ts, url=url, event_type="mouse_click", x=x_coord, y=y_coord, button=button_name, selector=sel, text=txt, modifiers=mods)
                self.events.append(evt)
                logger.info(f"🖱️ MouseClick, url='{evt.url}', button='{evt.button}' on '{sel}'")
                user_log_msg = f"🖱️ {button_name.capitalize()} Click at ({x_coord},{y_coord}) on '{sel if sel else 'document'}'"
                if txt: 
                    formatted_text = (txt[:20]+'...') if len(txt) > 20 else txt
                    user_log_msg += f" (text: '{formatted_text}')"
            elif typ == "keydown":
                key_val = str(p.get("key"))
                evt = KeyboardEvent(timestamp=ts, url=url, event_type="keyboard_input", key=key_val, code=str(p.get("code")), selector=sel, modifiers=mods)
                self.events.append(evt)
                logger.info(f"⌨️ KeyInput, url='{evt.url}', key='{evt.key}' in '{sel}'")
                display_key = key_val
                if len(key_val) > 1 and key_val not in ["Backspace", "Enter", "Tab", "Escape", "Delete"]:
                    display_key = key_val
                elif key_val == " ":
                    display_key = "Space"
                user_log_msg = f"⌨️ Key Press: '{display_key}' in element: '{sel if sel else 'document'}'"
            
            # DEBUGGING queue in _on_dom_event
            if user_log_msg:
                logger.debug(f"[Recorder._on_dom_event]: self.event_log_queue is {type(self.event_log_queue)} for msg: '{user_log_msg}'")
                if self.event_log_queue:
                    logger.debug(f"[Recorder._on_dom_event]: Attempting to put '{user_log_msg}' onto queue id: {id(self.event_log_queue)}")
                    try:
                        self.event_log_queue.put_nowait(user_log_msg)
                        logger.debug(f"[Recorder._on_dom_event]: Successfully put '{user_log_msg}'.")
                    except asyncio.QueueFull:
                        logger.warning(f"Recorder event log queue full. Dropped: {user_log_msg}")
                        logger.debug(f"[Recorder._on_dom_event]: FAILED to put '{user_log_msg}' (QueueFull)")
                else:
                    logger.debug(f"[Recorder._on_dom_event]: self.event_log_queue is None or False. Skipping put for '{user_log_msg}'.")
        except Exception:
            logger.exception("Malformed DOM payload or error processing event: %s", p)
            # Potentially log to UI queue as well if an error occurs during event processing
            if self.event_log_queue:
                try: self.event_log_queue.put_nowait(f"⚠️ Error processing recorded DOM event: {p.get('type', 'unknown')}")
                except asyncio.QueueFull: logger.warning("Recorder event log queue full. Dropped DOM event processing error log.")

    # --------------------------------------------------
    # Navigation via Playwright
    # --------------------------------------------------

    def _on_playwright_nav(self, page, frame):
        if not self.is_recording: return
        if frame.parent_frame is None: 
            url = frame.url
            if url and url not in (self.current_url, "about:blank"):
                nav = NavigationEvent(timestamp=time.time(), url=url, event_type="navigation", from_url=self.current_url, to_url=url)
                self.events.append(nav)
                # self.current_url = url # Moved after logging
                logger.info("🧭 Navigation recorded (internal) from %s to %s", self.current_url, url)
                user_log_msg = f"🧭 Navigated to: {url}"
                logger.debug(f"[Recorder._on_playwright_nav]: self.event_log_queue is {type(self.event_log_queue)} for msg: '{user_log_msg}'")
                if self.event_log_queue:
                    logger.debug(f"[Recorder._on_playwright_nav]: Attempting to put '{user_log_msg}' onto queue id: {id(self.event_log_queue)}")
                    try: self.event_log_queue.put_nowait(user_log_msg); logger.debug(f"[Recorder._on_playwright_nav]: Successfully put '{user_log_msg}'.")
                    except asyncio.QueueFull: logger.warning(f"Recorder event log queue full. Dropped: {user_log_msg}"); logger.debug(f"[Recorder._on_playwright_nav]: FAILED to put '{user_log_msg}' (QueueFull)")
                else: logger.debug(f"[Recorder._on_playwright_nav]: self.event_log_queue is None or False. Skipping put for '{user_log_msg}'.")
                self.current_url = url # Update after logging 'from' URL

    # --------------------------------------------------
    # Frame‑eval helpers
    # --------------------------------------------------

    async def _eval_in_all_frames(self, page, script):
        results = []
        if not page or page.is_closed():
            logger.warning("eval_in_all_frames: Page is closed or None.")
            return [None]
        try:
            for frame in page.frames:
                if not frame.is_detached():
                    result = await self._safe_eval(frame, script)
                    results.append(result)
                else:
                    logger.debug(f"eval_in_all_frames: Frame {frame.url} is detached, skipping eval.")
                    results.append("detached_frame")
            return results
        except Exception as e:
            logger.error(f"Error during _eval_in_all_frames for page {page.url}: {e}", exc_info=True)
            return [f"error: {str(e)}"]

    async def _safe_eval(self, frame, script):
        try:
            result = await frame.evaluate(script)
            return result
        except Exception as e:
            logger.error(f"SAFE_EVAL: Error evaluating script in frame {frame.name} ({frame.url}): {str(e)}", exc_info=False)
            return f"eval_error: {str(e)}"

    # --------------------------------------------------
    # Export
    # --------------------------------------------------

    def export_events_to_json(self) -> str:
        return json.dumps({
            "version": "2.0",
            "timestamp": time.time(),
            "events": [asdict(e) for e in self.events],
        }, indent=2)

    def export_events_to_jsonl(self) -> str:
        lines = []
        last_ts = self.events[0].timestamp if self.events else 0
        for ev in self.events:
            dt = int((ev.timestamp - last_ts)*1000)
            last_ts = ev.timestamp
            # Create a dictionary from the event, ensuring 'timestamp' is not carried over.
            line_dict = asdict(ev)
            # TODO: which file is the reference? 
            # The problem statement implies 'event_type' should be 'type' in the output.
            # and 'to_url' should be 'to' for navigation events.
            # also, 'timestamp' is replaced by 't' (delta time).
            line_dict["type"] = line_dict.pop("event_type")
            if "timestamp" in line_dict: # should always be true based on InputEvent
                del line_dict["timestamp"]
            if line_dict["type"] == "navigation":
                if "to_url" in line_dict: # Ensure to_url exists
                    line_dict["to"] = line_dict.pop("to_url")
                if "from_url" in line_dict: # from_url is not in the example, remove
                    del line_dict["from_url"]
            # The example shows 'mods' instead of 'modifiers' for keyboard/mouse events.
            if "modifiers" in line_dict:
                line_dict["mods"] = line_dict.pop("modifiers")

            line_dict["t"] = dt
            lines.append(json.dumps(line_dict))
        return "\n".join(lines)
