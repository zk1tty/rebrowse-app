import asyncio, json, logging, time
from pathlib import Path
from typing import List, Dict, Any, Optional, Literal
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import Page as SyncPage, TimeoutError as SyncPlaywrightTimeoutError, Locator as SyncLocator, ElementHandle as SyncElementHandle

logger = logging.getLogger(__name__)

# --------------------------------------------------
# Exceptions
# --------------------------------------------------

class Drift(Exception):
    """Raised when replay diverges from expected state."""
    def __init__(self, msg: str, event: Dict[str, Any] | None = None):
        super().__init__(msg)
        self.event = event

# --------------------------------------------------
# Trace loader helper
# --------------------------------------------------

def load_trace(path: str | Path) -> List[Dict[str, Any]]:
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]

# --------------------------------------------------
# Replayer
# --------------------------------------------------

class TraceReplayerSync:
    BTN_MAP: Dict[str, Literal["left", "middle", "right"]] = {"left": "left", "middle": "middle", "right": "right"}
    MOD_MAP = {"alt": "Alt", "ctrl": "Control", "shift": "Shift", "meta": "Meta"}

    def __init__(self, page: SyncPage, trace: List[Dict[str, Any]], controller: Any,
                 user_provided_files: Optional[List[str]] = None,
                 ui_q: Optional[asyncio.Queue] = None,
                 main_loop: Optional[asyncio.AbstractEventLoop] = None):
        logger.debug(f"[REPLAYER_SYNC __init__] Initializing. Page: {type(page)}, Trace_events: {len(trace) if trace else 0}, Controller: {type(controller)}")
        self.page = page
        self.trace = trace
        self.controller = controller
        self.user_provided_files = user_provided_files or [] # Store user-provided file paths
        self._clicked_with_selector = False
        self._clicked_dispatch = False
        self.ui_q = ui_q
        self.main_loop = main_loop

    # ------------- main loop -------------

    def play(self, speed: float = 2.0):
        i = 0
        logger.debug(f"[REPLAYER play] Starting play loop. Trace length: {len(self.trace)}")
        while i < len(self.trace):
            ev = self.trace[i]
            logger.debug(f"[REPLAYER play] Processing event {i+1}/{len(self.trace)}: Type: {ev.get('type')}, URL: {ev.get('url')}")
            
            # Avoid processing 'v' key press before clipboard_paste event
            # Check if the current event is 'v' key input and the next is 'clipboard_paste'
            if ev.get("type") == "keyboard_input" and ev.get("key") == "v" and not ev.get("modifiers"):
                if (i + 1) < len(self.trace):
                    next_ev = self.trace[i+1]
                    if next_ev.get("type") == "clipboard_paste":
                        logger.info(f"[REPLAYER play] Skipping 'v' key press before clipboard_paste. Event {i+1}")
                        i += 1  # Skip the 'v' key press event
                        ev = next_ev # Process the clipboard_paste event in this iteration
                        logger.debug(f"[REPLAYER play] Now processing event {i+1}/{len(self.trace)}: Type: {ev.get('type')}, URL: {ev.get('url')}")
            
            # New concise and iconic log format
            log_type = ev["type"]
            current_event_url = ev.get("url", "N/A") # URL from the event itself

            log_message_elements = []

            if log_type == "mouse_click":
                log_message_elements.append("🖱️ MouseClick")
                button_text = ev.get("text")
                selector = ev.get("selector")
                
                if button_text:
                    log_message_elements.append(f"button_text:\"{button_text}\"")
                elif selector: 
                    log_message_elements.append(f"selector:\"{selector}\"")
                else: 
                    log_message_elements.append(f"xy:({ev.get('x', 'N/A')},{ev.get('y', 'N/A')})")
                
                button_type = ev.get("button", "left")
                if button_type != "left": # Only show if not default left click
                    log_message_elements.append(f"button:\"{button_type}\"")
                log_message_elements.append(f"url='{current_event_url}'")
            
            elif log_type == "keyboard_input":
                log_message_elements.append("⌨️ KeyInput")
                key_val = ev.get("key")
                log_message_elements.append(f"key:'{key_val}'")
                modifiers = ev.get("modifiers")
                if modifiers: 
                    log_message_elements.append(f"mods:{modifiers}")
                log_message_elements.append(f"url='{current_event_url}'")

            elif log_type == "navigation":
                log_message_elements.append("🌐 Navigation")
                to_url = ev.get("to")
                log_message_elements.append(f"to='{to_url}'")

            else: # Generic fallback for other event types like scroll, viewport_change etc.
                log_message_elements.append(f"{log_type.replace('_', ' ').title()}")
                s = ev.get("selector")
                if s: log_message_elements.append(f"selector:\"{s}\"")
                if 'x' in ev and 'y' in ev:
                     log_message_elements.append(f"coords:({ev.get('x')},{ev.get('y')})")
                log_message_elements.append(f"url='{current_event_url}'")

            # Send iconic log message to UI queue
            log_msg_str = ", ".join(log_message_elements)
            if self.ui_q and self.main_loop:
                self.main_loop.call_soon_threadsafe(self.ui_q.put_nowait, log_msg_str)
            else: # Fallback to standard logger if queue/loop not provided (e.g. during testing)
                logger.info(log_msg_str)
            
            # Delay logic
            logger.debug(f"[REPLAYER play] Event {i+1}: Applying delay of {ev.get('t', 0)}ms, speed adjusted: {ev.get('t', 0)/speed}ms")
            event_delay_ms = ev.get("t", 0)
            if event_delay_ms > 10: # Log only if delay is > 10ms (to avoid spamming for 0ms delays)
                 logger.debug(f"Pausing for {event_delay_ms/1000.0:.3f}s (speed adjusted: {event_delay_ms/1000.0/speed:.3f}s)")
            time.sleep(event_delay_ms / 1000.0 / speed)

            if ev["type"] == "keyboard_input":
                consumed = self._batch_type(i)
                i += consumed
                logger.debug(f"[REPLAYER play] Event {i+1-consumed} (keyboard_input batch): Consumed {consumed} events. New index: {i}")
                continue

            self._apply(ev)
            logger.debug(f"[REPLAYER play] Event {i+1}: _apply(ev) completed.")
            self._verify(ev)
            logger.debug(f"[REPLAYER play] Event {i+1}: _verify(ev) completed.")
            i += 1
        logger.debug(f"[REPLAYER play] Play loop finished.")

    # ------------- batching -------------

    def _batch_type(self, idx: int) -> int:
        ev_start_batch = self.trace[idx]
        sel, mods = ev_start_batch.get("selector"), ev_start_batch.get("modifiers", [])
        text_to_type = ""
        
        current_idx_in_trace = idx
        
        first_key = ev_start_batch.get("key", "")
        is_first_key_batchable = len(first_key) == 1 and not mods

        if is_first_key_batchable:
            text_to_type = first_key
            current_idx_in_trace = idx + 1
            while current_idx_in_trace < len(self.trace):
                nxt = self.trace[current_idx_in_trace]
                if nxt["type"] != "keyboard_input" or nxt.get("t",1) != 0: break 
                if nxt.get("selector") != sel: break
                if nxt.get("modifiers"): break
                
                next_key_char = nxt.get("key", "")
                if len(next_key_char) == 1:
                    text_to_type += next_key_char
                    current_idx_in_trace += 1
                else:
                    break
            current_idx_in_trace -= 1

        num_events_processed = 0
        if len(text_to_type) > 1:
            self._apply_type(sel, text_to_type, [], ev_start_batch)
            self._verify(ev_start_batch)
            num_events_processed = current_idx_in_trace - idx + 1
        else:
            self._apply(ev_start_batch) 
            self._verify(ev_start_batch)
            num_events_processed = 1
            
        return num_events_processed

    def _apply_type(self, sel: Optional[str], text: str, mods: List[str], original_event_for_log: Dict[str, Any]):
        log_sel_for_type = sel or "N/A"
        logger.debug(f"APPLYING BATCH TYPE: '{text}' -> {log_sel_for_type}")

        if sel:
            try:
                element_to_fill = self.page.locator(sel).first
                element_to_fill.wait_for(state='visible', timeout=5000)
                element_to_fill.focus(timeout=1000)
                time.sleep(0.2) # Short delay after focus before filling
                element_to_fill.fill(text)
            except Exception as e_fill:
                logger.error(f"Error during locator.fill('{text}') for selector '{sel}': {e_fill.__class__.__name__} - {str(e_fill)}. Falling back to keyboard.type.")
                # Fallback to original keyboard.type if fill fails for some reason
                mapped_mods = [self.MOD_MAP[m] for m in mods if m in self.MOD_MAP]
                for m_down in mapped_mods: self.page.keyboard.down(m_down)
                try:
                    self.page.keyboard.type(text)
                except Exception as e_type:
                    logger.error(f"Error during fallback page.keyboard.type('{text}'): {e_type.__class__.__name__} - {str(e_type)}")
                for m_up in reversed(mapped_mods): self.page.keyboard.up(m_up)
        else:
            # If no selector, fallback to general keyboard typing (less common for batched text)
            logger.warning(f"Attempting to batch type '{text}' without a selector. Using page.keyboard.type().")
            mapped_mods = [self.MOD_MAP[m] for m in mods if m in self.MOD_MAP]
            for m_down in mapped_mods: self.page.keyboard.down(m_down)
            try:
                self.page.keyboard.type(text)
            except Exception as e_type:
                logger.error(f"Error during page.keyboard.type('{text}') without selector: {e_type.__class__.__name__} - {str(e_type)}")
            for m_up in reversed(mapped_mods): self.page.keyboard.up(m_up)

        logger.debug(f"✅ done BATCH TYPE: '{text}' -> {log_sel_for_type}")

    # ------------- apply -------------

    def _apply(self, ev: Dict[str, Any]):
        typ = ev["type"]
        sel_event = ev.get("selector")
        logger.debug(f"[REPLAYER _apply] Applying action: {typ}, selector: {sel_event}, keys: {ev.get('key')}, to: {ev.get('to')}")
        logger.debug(f"APPLYING ACTION: {typ} for sel={sel_event or 'N/A'}, key={ev.get('key','N/A')}")

        if typ == "navigation":
            target = ev["to"]
            if not self._url_eq(self.page.url, target):
                logger.debug(f"[REPLAYER _apply NAV] Attempting self.page.goto('{target}')")
                try:
                    # Restore original navigation target and timeout
                    self.page.goto(target, wait_until="domcontentloaded", timeout=15000)
                    logger.debug(f"[REPLAYER _apply NAV] self.page.goto to '{target}' SUCCEEDED.")
                except SyncPlaywrightTimeoutError as pte_goto:
                    logger.error(f"[REPLAYER _apply NAV] PlaywrightTimeoutError during goto '{target}': {pte_goto}", exc_info=True)
                except Exception as e_goto_general:
                    logger.error(f"[REPLAYER _apply NAV] Exception during goto '{target}': {e_goto_general}", exc_info=True)
            else:
                logger.debug(f"[REPLAYER _apply NAV] Page URL {self.page.url} already matches target {target}. Skipping goto.")

            logger.debug(f"[REPLAYER _apply NAV] Attempting page.bring_to_front() for {target}")
            self.page.bring_to_front()
            logger.debug(f"[REPLAYER _apply NAV] page.bring_to_front() completed for {target}")
            # Enhanced wait after navigation
            try:
                logger.debug(f"Waiting for 'load' state after navigating to {target}")
                logger.debug(f"[REPLAYER _apply NAV] Attempting page.wait_for_load_state('load') for {target}")
                self.page.wait_for_load_state('load', timeout=10000) # Wait for basic load
                logger.debug(f"[REPLAYER _apply NAV] page.wait_for_load_state('load') completed for {target}")
                logger.debug(f"'load' state confirmed for {target}. Now waiting for networkidle.")
                logger.debug(f"[REPLAYER _apply NAV] Attempting page.wait_for_load_state('networkidle') for {target}")
                self.page.wait_for_load_state('networkidle', timeout=3000) # Shorter networkidle (e.g., 3 seconds)
                logger.debug(f"[REPLAYER _apply NAV] page.wait_for_load_state('networkidle') completed for {target}")
                logger.debug(f"[REPLAYER _apply NAV] Attempting time.sleep(0.3) for {target}")
                time.sleep(0.3) # Small buffer
                logger.debug(f"[REPLAYER _apply NAV] time.sleep(0.3) completed for {target}")
                logger.debug(f"Network idle (or timeout) confirmed for {target}")
            except Exception as e_wait:
                logger.warning(f"Timeout or error during page load/networkidle wait on {target}: {e_wait.__class__.__name__} - {str(e_wait)}")

            logger.info(f"✅🌐 Navigated: {target}")
            logger.debug(f"[REPLAYER _apply] Action {typ} applied.")
            return

        if typ == "mouse_click":
            btn = ev.get("button", "left")
            recorded_text = ev.get("text", "").lower() if ev.get("text") else ""
            self._clicked_with_selector = False
            self._clicked_dispatch = False
            
            if sel_event:
                loc = self._resolve_click_locator(sel_event)
                if loc:
                    try:
                        logger.debug(f"Attempting to click resolved locator for original selector: {sel_event}")
                        
                        # Default explicit wait timeout
                        wait_timeout = 5000
                        
                        # Expanded keyword list
                        critical_keywords = [
                            "download", "save", "submit", "next", "continue", "confirm", "upload", "add", "create",
                            "process", "generate", "apply", "send", "post", "tweet", "run", "execute",
                            "search", "go", "login", "signup", "pay", "checkout", "agree", "accept", "allow"
                        ]
                        
                        sel_event_lower = sel_event.lower() if sel_event else ""
                        is_critical_action = False

                        if any(keyword in recorded_text for keyword in critical_keywords):
                            is_critical_action = True
                        elif sel_event_lower and any(keyword in sel_event_lower for keyword in critical_keywords):
                            is_critical_action = True
                        
                        # Specific checks for known critical element identifiers
                        if sel_event_lower and (
                            'data-testid="send-button"' in sel_event_lower or
                            'data-testid*="submit"' in sel_event_lower or
                            'data-testid*="send"' in sel_event_lower or
                            'id*="submit-button"' in sel_event_lower or
                            'data-testid*="tweetbutton"' in sel_event_lower or
                            'id*="composer-submit-button"' in sel_event_lower # for chatgpt (example)
                        ):
                            is_critical_action = True

                        if is_critical_action:
                            # Use original recorded text for logging if available, else empty string
                            log_text = ev.get('text', '')
                            logger.info(f"Critical action suspected (text: '{log_text}', selector: '{sel_event}'). Extending wait.")
                            wait_timeout = 15000 # 15 seconds
                        
                        logger.debug(f"Waiting for selector '{sel_event}' to be visible and enabled with timeout {wait_timeout}ms.")
                        loc.wait_for(state='visible', timeout=wait_timeout)
                        loc.scroll_into_view_if_needed(timeout=wait_timeout)
                        logger.debug(f"Element '{sel_event}' is visible and enabled. Attempting standard click.")
                        
                        print(f"[REPLAYER _apply CLICK] >>> Attempting loc.click() for '{sel_event}' with timeout {wait_timeout}ms", flush=True)
                        try:
                            loc.click(button=self.BTN_MAP.get(btn, "left"), timeout=wait_timeout, delay=100)
                            self._clicked_with_selector = True
                            logger.debug(f"[REPLAYER _apply CLICK] loc.click() for '{sel_event}' SUCCEEDED.")
                            logger.info(f"Standard Playwright click successful for resolved locator from selector: {sel_event}")
                            time.sleep(0.25) # Keep small delay after successful click
                            return # Successfully clicked
                        except SyncPlaywrightTimeoutError as pte_click:
                            logger.warning(f"[REPLAYER _apply CLICK] PlaywrightTimeoutError during standard loc.click() for '{sel_event}': {pte_click}")
                        except Exception as e_click:
                            logger.warning(f"[REPLAYER _apply CLICK] Exception during standard loc.click() for '{sel_event}': {e_click}", exc_info=True)

                        # Fallback 2: Try click with force=True
                        if not self._clicked_with_selector:
                            logger.debug(f"[REPLAYER _apply CLICK] Fallback 2: Attempting loc.click(force=True) for '{sel_event}'")
                            try:
                                loc.click(button=self.BTN_MAP.get(btn, "left"), timeout=wait_timeout, delay=100, force=True)
                                self._clicked_with_selector = True
                                logger.info(f"Forced Playwright click successful for '{sel_event}'")
                                time.sleep(0.25)
                                return
                            except SyncPlaywrightTimeoutError as pte_force_click:
                                logger.warning(f"[REPLAYER _apply CLICK] PlaywrightTimeoutError during loc.click(force=True) for '{sel_event}': {pte_force_click}")
                            except Exception as e_force_click:
                                logger.warning(f"[REPLAYER _apply CLICK] Exception during loc.click(force=True) for '{sel_event}': {e_force_click}", exc_info=True)

                    except SyncPlaywrightTimeoutError as e_timeout:
                        logger.warning(f"Timeout ({wait_timeout}ms) waiting for element '{sel_event}' (visible/enabled) or during click: {e_timeout.__class__.__name__}")
                        # Fall through to other fallbacks if timeout
                    except Exception as e_click_attempt1:
                        logger.warning(f"Standard Playwright click (attempt 1) for resolved locator from '{sel_event}' failed: {e_click_attempt1.__class__.__name__} ({str(e_click_attempt1)})")
                        
                    # Fallback to dispatchEvent if standard click failed (and not returned)
                    if not self._clicked_with_selector:
                        try:
                            logger.info(f"Fallback 3 (Final): Attempting to dispatch click event for resolved locator from '{sel_event}'")
                            logger.debug(f"[REPLAYER _apply CLICK] Fallback 3: Attempting dispatchEvent for '{sel_event}'")
                            if loc.count() > 0:
                                element_handle = loc.element_handle(timeout=1000)
                                if element_handle:
                                    element_handle.dispatch_event('click')
                                    self._clicked_dispatch = True
                                    self._clicked_with_selector = True
                                    logger.info(f"DispatchEvent (via element_handle) click successful for '{sel_event}'")
                                    time.sleep(0.25)
                                    return
                                else:
                                    loc.dispatch_event('click')
                                    self._clicked_dispatch = True
                                    self._clicked_with_selector = True
                                    logger.info(f"DispatchEvent (via locator) click successful for '{sel_event}'")
                                    time.sleep(0.25)
                                    return
                            else:
                                logger.error(f"Cannot dispatch click for '{sel_event}', resolved locator is empty.")
                        except Exception as e_dispatch:
                            logger.warning(f"DispatchEvent click failed for '{sel_event}': {e_dispatch.__class__.__name__} ({str(e_dispatch)}). Falling back to XY if available.")
            
            # Fallback to XY click if selector-based attempts failed or no selector
            if not self._clicked_with_selector:
                log_x, log_y = ev.get("x"), ev.get("y")
                if log_x is not None and log_y is not None:
                    logger.info(f"Fallback: Performing coordinate-based click at ({log_x},{log_y})")
                    self.page.mouse.click(log_x, log_y, button=self.BTN_MAP.get(btn, "left"))
                    time.sleep(0.25)
                else:
                    if sel_event:
                         logger.error(f"All click attempts failed for selector '{sel_event}' and no XY coordinates available.")
            return
        
        if typ == "keyboard_input":
            key_to_press = ev["key"]
            modifiers_for_press = ev.get("modifiers", []) # REVERTED to 'modifiers'
            sel_for_press = ev.get("selector")
            logger.debug(f"APPLYING SINGLE KEY PRESS: '{key_to_press}' (mods: {modifiers_for_press}) -> {sel_for_press or 'no specific target'}")

            if sel_for_press:
                try:
                    target_loc_key_press = self.page.locator(sel_for_press).first
                    if target_loc_key_press.count() > 0:
                         target_loc_key_press.focus(timeout=800)
                    else:
                        logger.warning(f"Target element for key press not found: {sel_for_press}")
                except Exception as e_focus_single_key:
                    logger.debug(f"Focus failed for selector '{sel_for_press}' during single key press: {e_focus_single_key.__class__.__name__}")

            mapped_mods_press = [self.MOD_MAP[m] for m in modifiers_for_press if m in self.MOD_MAP]
            for m_down_key in mapped_mods_press: self.page.keyboard.down(m_down_key)
            
            try:
                self.page.keyboard.press(key_to_press)
            except Exception as e_press:
                 logger.error(f"Error during page.keyboard.press('{key_to_press}'): {e_press.__class__.__name__} - {str(e_press)}")

            for m_up_key in reversed(mapped_mods_press): self.page.keyboard.up(m_up_key)
            logger.debug(f"✅ done SINGLE KEY PRESS: '{key_to_press}' -> {sel_for_press or 'no specific target'}")
            return

        # --- NEW EVENT HANDLERS ---
        elif typ == "clipboard_copy":
            logger.debug(f"[REPLAYER _apply] Executing clipboard_copy controller action.")
            self.controller.execute("Copy text to clipboard", text=ev["text"])
            logger.info(f"📋 Executed Copy: text='{(ev['text'][:30] + '...') if len(ev['text']) > 30 else ev['text']}'")
            return
        elif typ == "clipboard_paste":
            logger.debug(f"[REPLAYER _apply] Executing clipboard_paste controller action for selector: {ev['selector']}.")
            self.controller.execute("Paste text from clipboard", selector=ev["selector"])
            logger.info(f"📋 Executed Paste into selector='{ev['selector']}'")
            return
        elif typ == "file_upload":
            logger.debug(f"[REPLAYER _apply] Processing file_upload for selector: {ev['selector']}, file_name: {ev.get('file_name')}")
            file_path_to_upload = None
            trace_file_name = ev.get("file_name")

            if trace_file_name and self.user_provided_files:
                for user_file_path_str in self.user_provided_files:
                    user_file_path = Path(user_file_path_str)
                    if user_file_path.name == trace_file_name:
                        if user_file_path.exists():
                            file_path_to_upload = str(user_file_path)
                            logger.info(f"Using user-provided file for '{trace_file_name}': {file_path_to_upload}")
                            break
                        else:
                            logger.warning(f"User-provided file '{user_file_path_str}' for '{trace_file_name}' does not exist.")
            
            if not file_path_to_upload:
                trace_event_file_path = ev.get("file_path") # This is the one from original recording (often empty)
                if trace_event_file_path: 
                    path_obj = Path(trace_event_file_path).expanduser()
                    if path_obj.exists():
                        file_path_to_upload = str(path_obj)
                        logger.info(f"Using file_path from trace for '{trace_file_name or 'unknown'}': {file_path_to_upload}")
                    else:
                        logger.warning(f"file_path '{trace_event_file_path}' from trace for '{trace_file_name or 'unknown'}' does not exist.")

            if not file_path_to_upload and trace_file_name:
                fallback_path = Path(f"~/Downloads/{trace_file_name}").expanduser()
                if fallback_path.exists():
                    file_path_to_upload = str(fallback_path)
                    logger.info(f"Using fallback file for '{trace_file_name}': {file_path_to_upload}")
                else:
                    logger.warning(f"Fallback file '{fallback_path}' for '{trace_file_name}' does not exist.")
            
            if file_path_to_upload:
                logger.debug(f"[REPLAYER _apply] Executing file_upload controller action with path: {file_path_to_upload}")
                self.controller.execute("Upload local file", 
                                              selector=ev["selector"], 
                                              file_path=file_path_to_upload)
                logger.info(f"📤 Executed Upload: file='{trace_file_name or Path(file_path_to_upload).name}' (path: '{file_path_to_upload}') to selector='{ev['selector']}'")
            else:
                logger.error(f"Could not determine a valid file path for upload event: {ev}. Skipping upload.")
            return
        elif typ == "file_download":
            # Pass all necessary info from the event to the controller
            logger.debug(f"[REPLAYER _apply] Executing file_download controller action for: {ev.get('suggested_filename')}")
            self.controller.execute(
                "Download remote file", 
                url=ev.get("download_url"),         # Original download URL (for info/logging)
                suggested_filename=ev.get("suggested_filename"),
                recorded_local_path=ev.get("recorded_local_path") # Path to file saved during recording
                # dest_dir will be handled by CustomController.execute with its default if not present here
            )
            logger.info(f"💾 Replay: Executed 'Download remote file' action for: {ev.get('suggested_filename')}")
            return
        # --- END NEW EVENT HANDLERS ---

        logger.debug(f"✅ done {typ} (no specific apply action in this path or already handled by controller.execute)")
        logger.debug(f"[REPLAYER _apply] Action {typ} applied (end of _apply general path).")

    def _resolve_click_locator(self, sel: str) -> Optional[SyncLocator]:
        if not sel: return None

        # Initial locator based on the selector from the trace
        initial_loc: SyncLocator = self.page.locator(sel).first

        # Check if the initial locator itself is a button or has role="button"
        # Use a try-catch for evaluate as the element might not exist or be stale
        try:
            if initial_loc and initial_loc.count() > 0: # Ensure element exists before evaluation
                # Check if the element itself is a button or has role="button"
                is_button_or_has_role = initial_loc.evaluate(
                    "el => el.tagName === 'BUTTON' || el.getAttribute('role') === 'button'"
                )
                if is_button_or_has_role:
                    logger.debug(f"_resolve_click_locator: Initial selector '{sel}' is already a button or has role='button'. Using it.")
                    return initial_loc
            else:
                logger.debug(f"_resolve_click_locator: Initial selector '{sel}' did not yield any elements. Will try to find ancestor.")
                # If initial_loc.count() is 0, initial_loc might not be suitable for ancestor search directly, 
                # but Playwright handles this by searching from the page if the locator is empty.
                # However, it's cleaner to ensure we have a starting point if we intend to find an ancestor *of something*.
                # For now, we will proceed, and if initial_loc is empty, the ancestor search becomes a page-wide search for a button.

        except Exception as e_eval_initial:
            logger.debug(f"_resolve_click_locator: Error evaluating initial selector '{sel}': {e_eval_initial}. Will try to find ancestor.")

        # If not, or if initial check failed, try to find an ancestor that is a button or has role="button"
        # This also covers cases where `sel` might point to an inner element of a button (e.g., a span).
        # The XPath searches for an ancestor OR self that is a button or has the role.
        # Using a more specific XPath to find the closest ancestor or self that is a button:
        # xpath=ancestor-or-self::button | ancestor-or-self::*[@role='button']
        # Playwright's loc.locator("xpath=...") will find the first such element from the perspective of `loc`.
        # If initial_loc was empty, this effectively searches from page root.
        
        # Let's try a slightly different approach for finding the button: use Playwright's :nth-match with a broader internal selector.
        # This attempts to find the *actual element* matching 'sel', then looks upwards or at itself for a button.
        # This is more robust if 'sel' is very specific to an inner element.

        # Re-fetch the initial locator to ensure we are working from the element pointed to by `sel`
        # This is important if `sel` is like 'div > span' - we want the span, then find its button parent.
        # If initial_loc.count() was 0 above, this will still be an empty locator.
        element_loc = self.page.locator(sel).first 

        if element_loc.count() > 0:
            # Try to find a button by looking at the element itself or its ancestors
            # This combines checking self and then ascending.
            # The XPath 'ancestor-or-self::button | ancestor-or-self::*[@role="button"]' correctly finds the button.
            # We then take the .first of these, as Playwright will return them in document order (ancestors first).
            # To get the *closest* (most specific) button, we might need to be careful.
            # However, Playwright's .locator on an existing locator usually chains correctly.

            # Let's try to find the *specific* element by `sel` and then chain to find its button ancestor or self.
            # This is more reliable than a broad page search if `sel` is specific.
            potential_button_loc = element_loc.locator("xpath=ancestor-or-self::button | ancestor-or-self::*[@role='button']").first
            if potential_button_loc.count() > 0:
                logger.debug(f"_resolve_click_locator: Found button/role=button for '{sel}' via ancestor-or-self. Using it.")
                return potential_button_loc
            else:
                logger.debug(f"_resolve_click_locator: No button ancestor found for specific element of '{sel}'. Falling back to initial locator if it exists.")
                return element_loc if element_loc and element_loc.count() > 0 else None
        else:
            # If the original selector `sel` finds nothing, try a page-wide search for a button that might contain the text from `sel` if `sel` was text-based
            # This part is tricky and heuristic. For now, if `sel` finds nothing, we return None.
            logger.debug(f"_resolve_click_locator: Initial selector '{sel}' found no elements. Cannot resolve to a button.")
            return None

    # ------------- verify -------------

    def _verify_tweet_posted(self):
        try:
            self.page.wait_for_selector('[role=alert]:text("sent")', timeout=3000)
            logger.info("Tweet post verification successful: 'sent' toast found.")
        except Exception as e_toast:
            logger.error(f"Tweet post verification failed: 'sent' toast not found within timeout. Error: {e_toast.__class__.__name__}")

    def _verify(self, ev: Dict[str, Any]):
        typ = ev["type"]
        sel_from_event_verify = ev.get("selector")

        if typ == "navigation":
            if not TraceReplayerSync._url_eq(self.page.url, ev["to"]):
                current_event_expected_url = ev["url"]
                nav_target_url = ev["to"]
                actual_page_url = self.page.url

                if TraceReplayerSync._url_eq(actual_page_url, nav_target_url):
                    logger.debug(f"Navigation URL verified: Expected target {nav_target_url}, Got {actual_page_url}")
                    return

                logger.warning(f"Potential Navigation URL drift: Expected target {nav_target_url}, but current URL is {actual_page_url}. Original event recorded at {current_event_expected_url}")
                
                current_event_index = -1
                try:
                    current_event_index = self.trace.index(ev)
                except ValueError:
                    logger.error("Critical: Could not find current navigation event in trace for drift recovery. Raising drift based on target mismatch.")
                    raise Drift(f"URL drift for navigation: expected target {nav_target_url}, got {actual_page_url}", ev)

                if 0 <= current_event_index < len(self.trace) - 1:
                    next_event = self.trace[current_event_index + 1]
                    logger.debug(f"Drift check for navigation: Next event is type '{next_event.get('type')}', URL '{next_event.get('url')}', To '{next_event.get('to')}'")
                    
                    if next_event.get("type") == "navigation":
                        next_event_nav_target_url = next_event.get("to")
                        next_event_recorded_at_url = next_event.get("url")

                        if next_event_nav_target_url and TraceReplayerSync._url_eq(actual_page_url, next_event_nav_target_url):
                            logger.info(f"Drift recovery for navigation: Actual URL {actual_page_url} matches TARGET of NEXT navigation. Allowing.")
                            return
                        if next_event_recorded_at_url and TraceReplayerSync._url_eq(actual_page_url, next_event_recorded_at_url):
                            logger.info(f"Drift recovery for navigation: Actual URL {actual_page_url} matches RECORDED URL of NEXT navigation. Allowing.")
                            return
                
                logger.error(f"URL drift CONFIRMED for navigation: expected target {nav_target_url}, got {actual_page_url}")
                raise Drift(f"URL drift for navigation: expected target {nav_target_url}, got {actual_page_url}", ev)
            return
        
        if typ == "mouse_click" and self._clicked_with_selector and sel_from_event_verify:
            if "tweetButton" in sel_from_event_verify:
                self._verify_tweet_posted()
                return

            if getattr(self, "_clicked_dispatch", False):
                logger.info(f"Verification for selector '{sel_from_event_verify}': Skipped standard DOM check as dispatchEvent was used (element might be detached/changed).")
                return
            
            recorded_text = ev.get("text")
            if recorded_text is not None:
                try:
                    verify_loc = self._resolve_click_locator(sel_from_event_verify) 
                    if verify_loc and verify_loc.count() > 0:
                        current_text = (verify_loc.inner_text(timeout=1000)).strip()
                        if current_text == recorded_text:
                            logger.info(f"Inner text matched for {sel_from_event_verify}: '{recorded_text}'")
                        else:
                            logger.warning(f"Text drift for {sel_from_event_verify}: expected '{recorded_text}', got '{current_text}'")
                    else:
                        logger.warning(f"Cannot verify text for {sel_from_event_verify}, element not found by re-resolving after click.")
                except Exception as e_text_verify:
                    logger.warning(f"Error during text verification for {sel_from_event_verify}: {str(e_text_verify)}")
            return
        
        if typ == "keyboard_input":
            try:
                active_element_focused = self.page.evaluate("document.activeElement !== null && document.activeElement !== document.body")
                if not active_element_focused:
                    logger.debug("No specific element has focus after typing for event: %s", ev.get("selector"))
            except Exception as e:
                logger.debug("Error checking active element after typing: %s", e)
            return

        # Selector verification (if applicable)
        # This part remains unchanged from your existing logic if you have it.
        # For example, if a click was supposed to happen on a selector:
        if ev["type"] == "mouse_click" and ev.get("selector") and not self._clicked_with_selector:
            # This implies the fallback XY click was used, which can be a form of drift.
            # You might want to log this or handle it as a minor drift.
            logger.debug(f"Verification: Click for selector '{ev['selector']}' used XY fallback.")

        # URL drift check
        current_event_expected_url = ev["url"]
        actual_page_url = self.page.url

        if not TraceReplayerSync._url_eq(actual_page_url, current_event_expected_url):
            logger.warning(f"Potential URL drift: expected {current_event_expected_url} (from event record), got {actual_page_url} (actual browser URL).")

            current_event_index = -1
            try:
                # Find the index of the current event 'ev' in self.trace
                # This is okay for moderately sized traces. Consider passing index if performance becomes an issue.
                current_event_index = self.trace.index(ev)
            except ValueError:
                logger.error("Critical: Could not find current event in trace for drift recovery. This shouldn't happen. Raising original drift.")
                raise Drift(f"URL drift (and event indexing error): expected {current_event_expected_url}, got {actual_page_url}", ev)

            if 0 <= current_event_index < len(self.trace) - 1:
                next_event = self.trace[current_event_index + 1]
                logger.debug(f"Drift check: Next event is type '{next_event.get('type')}', URL '{next_event.get('url')}', To '{next_event.get('to')}'")
                
                if next_event.get("type") == "navigation":
                    next_event_target_url = next_event.get("to")
                    next_event_recorded_at_url = next_event.get("url")

                    # Condition 1: The browser is AT the target URL of the NEXT navigation event.
                    # This means the current navigation (ev) effectively led to where next_event will go.
                    if next_event_target_url and TraceReplayerSync._url_eq(actual_page_url, next_event_target_url):
                        logger.info(f"Drift recovery: Actual URL {actual_page_url} matches TARGET ('to') of the NEXT navigation event. Allowing.")
                        return

                    # Condition 2: The browser is AT the URL where the NEXT navigation event was RECORDED.
                    # This means the current navigation (ev) might have been part of a quick redirect chain,
                    # and the page has landed on the 'url' from which the next_event was initiated.
                    # This is relevant if next_event_target_url is different from next_event_recorded_at_url
                    if next_event_recorded_at_url and TraceReplayerSync._url_eq(actual_page_url, next_event_recorded_at_url):
                        logger.info(f"Drift recovery: Actual URL {actual_page_url} matches RECORDED URL ('url') of the NEXT navigation event. Allowing.")
                        return
            
            # If no recovery condition met, raise the original drift error
            logger.error(f"URL drift CONFIRMED after checks: expected {current_event_expected_url} (from event record), got {actual_page_url} (actual browser URL).")
            raise Drift(f"URL drift: expected {current_event_expected_url}, got {actual_page_url}", ev)
        else:
            logger.debug(f"URL verified: Expected {current_event_expected_url}, Got {actual_page_url}")

    # ---------- util ----------
    @staticmethod
    def _url_eq(a, b): 
        if not a or not b: return False
        pa, pb = urlparse(a), urlparse(b)
        if pa.netloc.replace('www.','') != pb.netloc.replace('www.',''): return False
        if pa.path.rstrip('/') != pb.path.rstrip('/'): return False
        KEEP = {'q','tbm','hl'} 
        qa = {k:v for k,v in parse_qs(pa.query).items() if k in KEEP}
        qb = {k:v for k,v in parse_qs(pb.query).items() if k in KEEP}
        return qa == qb

# --------------------------------------------------
# CLI demo (optional)
# --------------------------------------------------

async def _cli_demo(url: str, trace_path: str):
    from playwright.async_api import async_playwright
    # from src.controller.custom_controller import CustomController # Async controller
    print("[CLI_DEMO] WARNING: _cli_demo is not yet updated for TraceReplayerSync and CustomControllerSync. Skipping full replay test.", flush=True)
    # Temporarily disable the replayer part of the CLI demo until CustomControllerSync is ready

    logger.info(f"CLI Demo: Replaying trace '{trace_path}' starting at URL '{url}'")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False) # Usually headless=False for observing replay
        # Create a new context for each replay for isolation
        context = await browser.new_context() 
        page = await context.new_page()
        
        # Navigate to the initial URL mentioned in the trace or a default start URL
        # The replayer itself handles navigation events from the trace.
        # So, `url` here is the very first URL to open before replaying starts.
        logger.info(f"CLI Demo: Initial navigation to {url}")
        try:
            await page.goto(url, wait_until="networkidle", timeout=15000)
        except Exception as e_goto:
            logger.warning(f"CLI Demo: Initial goto to {url} failed or timed out: {e_goto}. Attempting to continue replay.")

        # Instantiate your custom controller
        # controller = CustomController()

        # Load trace and instantiate replayer with the controller
        try:
            trace_events = load_trace(trace_path)
            if not trace_events:
                logger.error(f"CLI Demo: No events found in trace file: {trace_path}")
                await browser.close()
                return
            logger.info(f"CLI Demo: Loaded {len(trace_events)} events from {trace_path}")
        except Exception as e_load:
            logger.error(f"CLI Demo: Failed to load trace file {trace_path}: {e_load}")
            await browser.close()
            return
            
        # rep = TraceReplayerSync(page, trace_events, controller, user_provided_files=None) # Pass the controller

        # try:
        #     rep.play(speed=1) # Adjust speed as needed (1.0 is real-time, higher is faster)
        #     logger.info("✅ CLI Demo: Replay completed")
        # except Drift as d:
        #     logger.error(f"⚠️ CLI Demo: Drift detected during replay: {d}")
        #     if d.event:
        #         logger.error(f"Drift occurred at event: {json.dumps(d.event, indent=2)}")
        # except Exception as e_play:
        #     logger.error(f"💥 CLI Demo: An error occurred during replay: {e_play}", exc_info=True)
        # finally:
        #     logger.info("CLI Demo: Closing browser...")
        #     # Keep browser open for a few seconds to inspect final state, then close
        #     # await asyncio.sleep(5) # Optional: delay before closing
        #     await browser.close()
        # For now, just close the browser after setup
        print("[CLI_DEMO] Intentionally skipping replay part in CLI demo for now.", flush=True)
        await browser.close()

if __name__ == "__main__":
    import sys, asyncio as _a
    # Ensure correct arguments are provided
    if len(sys.argv) < 3:
        print("Usage: python src/utils/replayer.py <start_url> <path_to_trace_file.jsonl>")
        sys.exit(1)
    
    # Configure logging for the CLI demo if run directly
    logging.basicConfig(level=logging.INFO, 
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    _a.run(_cli_demo(sys.argv[1], sys.argv[2]))