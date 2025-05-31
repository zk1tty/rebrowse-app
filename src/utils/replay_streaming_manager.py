# src/utils/replay_streaming_manager.py
import logging
import queue
import threading
import time      
import asyncio
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Any, Union, Callable
import os
import gradio as gr
from playwright.sync_api import sync_playwright, TimeoutError as SyncPlaywrightTimeoutError, Page as SyncPage, BrowserContext as SyncBrowserContext

# --- Project-specific imports needed by replay logic ---
from src.browser.custom_browser import CustomBrowser
from src.browser.custom_context import CustomBrowserContext
from src.controller.custom_controller import CustomControllerSync
from src.utils.replayer import TraceReplayerSync, load_trace, Drift
from src.browser.custom_context_config import CustomBrowserContextConfig as AppCustomBrowserContextConfig
from browser_use.browser.browser import BrowserConfig
from browser_use.browser.context import BrowserContextWindowSize

# --- Logging Setup for this Module (and for UI queue) ---
log_q: queue.Queue[str] = queue.Queue()
UI_HANDLER_NAME_FOR_MANAGER = "ReplayStreamManagerQueueHandler"
logging.getLogger('src.utils.replay_streaming_manager').setLevel(logging.DEBUG)

class ReplayManagerQueueHandler(logging.Handler): # Renamed for clarity within this module
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = UI_HANDLER_NAME_FOR_MANAGER

    def emit(self, record: logging.LogRecord):
        log_q.put(self.format(record))

# This setup assumes this module is imported once.
# If webui.py also has its own root logger setup, ensure they don't conflict badly.
# Typically, only the main application entry point should call basicConfig.

# Get the specific logger for replay-related messages that should go to the UI queue
# This means only logs from 'src.utils.replayer' (and potentially this manager) go to UI.
_replay_event_logger = logging.getLogger('src.utils.replayer') 

# Configure and add the handler
_manager_ui_queue_handler = ReplayManagerQueueHandler()
_manager_ui_queue_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', datefmt='%H:%M:%S'))
_manager_ui_queue_handler.setLevel(logging.INFO)

# Cleanup and add to the target logger
already_has_our_handler = False
for handler in list(_replay_event_logger.handlers):
    if hasattr(handler, 'name') and handler.name == UI_HANDLER_NAME_FOR_MANAGER:
        already_has_our_handler = True
        logging.debug(f"Handler '{UI_HANDLER_NAME_FOR_MANAGER}' already on '{_replay_event_logger.name}'")
        break
    elif isinstance(handler, ReplayManagerQueueHandler): # Fallback if name didn't match but type did
        logging.debug(f"Removing old ReplayManagerQueueHandler from '{_replay_event_logger.name}'")
        _replay_event_logger.removeHandler(handler)

if not already_has_our_handler:
    logging.debug(f"Adding ReplayManagerQueueHandler to '{_replay_event_logger.name}'")
    _replay_event_logger.addHandler(_manager_ui_queue_handler)

# Ensure the target logger processes INFO messages
if _replay_event_logger.getEffectiveLevel() > logging.INFO:
    _replay_event_logger.setLevel(logging.INFO)
# _replay_event_logger.propagate = False # Optional: if these logs shouldn't also go to console via root

logger = logging.getLogger(__name__) # Logger for this manager module
# logger.info("ReplayStreamingManager: Logging initialized. UI logs from 'src.utils.replayer' will use log_q.") 
# The above log can be confusing as log_q is now an internal detail before going to asyncio.Queue

def harvest_logs_for_ui() -> str:
    logger.debug("harvest_logs_for_ui: Checking queue...") # Changed to logger.debug
    lines = []
    queue_had_items = not log_q.empty() # Check before loop
    while not log_q.empty():
        try: 
            item = log_q.get_nowait()
            print(f"[MANAGER DEBUG] HARVESTED FROM QUEUE: {item}", flush=True) # Explicit print
            lines.append(item)
        except queue.Empty: 
            break
    if lines: 
        logger.debug(f"harvest_logs_for_ui: Returning {len(lines)} lines.")
    elif queue_had_items: # Log if queue had items but somehow lines is empty (shouldn't happen)
        logger.debug("harvest_logs_for_ui: Queue had items but no lines collected (unexpected).")
    # else: # Log if queue was empty (can be verbose)
        # logger.debug("harvest_logs_for_ui: Queue was empty.")
    return "\n".join(lines)

# --- Global Browser/Context Variables (MOVED HERE TEMPORARILY - will be passed as args later) ---
# These represent state that needs to be managed and passed from webui.py
# _mgr_global_browser: Optional[CustomBrowser] = None
# _mgr_global_browser_context: Optional[CustomBrowserContext] = None
# --- End Global Browser/Context Variables ---

# --- Global Helper Functions for Replay Logic (MOVED HERE) ---
def context_is_closed_mgr(ctx) -> bool: # Renamed to avoid conflict if webui still has one
    if not ctx: return True
    try: _ = ctx.pages; return False
    except Exception: return True

# MODIFIED: get_page_for_replay_mgr now takes browser/context as arguments
async def get_page_for_replay_mgr(ui_browser: Optional[CustomBrowser], ui_context: Optional[CustomBrowserContext]) -> Optional[Any]:
    logger.info("ReplayManager: get_page_for_replay_mgr called.")
    print(f"[MANAGER get_page_for_replay_mgr] ENTRY. ui_browser: {type(ui_browser)}, ui_context: {type(ui_context)}", flush=True)

    if not ui_browser:
        logger.error("ReplayManager: Provided ui_browser is None.")
        print("[MANAGER get_page_for_replay_mgr] ui_browser is None. Returning None.", flush=True)
        return None
    if not hasattr(ui_browser, 'resolved_playwright_browser') or not ui_browser.resolved_playwright_browser:
        logger.error("ReplayManager: Provided ui_browser.resolved_playwright_browser is missing.")
        print("[MANAGER get_page_for_replay_mgr] ui_browser.resolved_playwright_browser is missing. Returning None.", flush=True)
        return None
    if not ui_browser.resolved_playwright_browser.is_connected():
        logger.error("ReplayManager: Provided ui_browser is not connected.")
        print("[MANAGER get_page_for_replay_mgr] ui_browser is not connected. Returning None.", flush=True)
        return None 
    current_browser = ui_browser
    logger.debug("ReplayManager: ui_browser seems valid and connected.")
    if current_browser and hasattr(current_browser, 'resolved_playwright_browser') and current_browser.resolved_playwright_browser:
        print(f"[MANAGER get_page_for_replay_mgr] current_browser type: {type(current_browser)}, connected: {current_browser.resolved_playwright_browser.is_connected()}", flush=True)
    else:
        print(f"[MANAGER get_page_for_replay_mgr] current_browser or resolved_playwright_browser is None/invalid.", flush=True)

    current_context = ui_context
    if not current_context or not hasattr(current_context, 'playwright_context') or not current_context.playwright_context or context_is_closed_mgr(current_context.playwright_context):
        logger.info(f"ReplayManager: Provided ui_context (type: {type(ui_context)}) is invalid/closed. Attempting new context.")
        print(f"[MANAGER get_page_for_replay_mgr] ui_context invalid/closed (type: {type(ui_context)}, playwright_context exists: {hasattr(current_context, 'playwright_context') if current_context else False}). Creating new context.", flush=True)
        try:
            ctx_config = AppCustomBrowserContextConfig(enable_input_tracking=False, browser_window_size=BrowserContextWindowSize(width=1280, height=1100))
            logger.debug(f"ReplayManager: Calling current_browser.new_context() with config: {ctx_config}")
            print(f"[MANAGER get_page_for_replay_mgr] Calling current_browser.new_context()", flush=True)
            current_context = await current_browser.new_context(config=ctx_config)
            print(f"[MANAGER get_page_for_replay_mgr] new_context() returned. New current_context type: {type(current_context)}", flush=True)
            logger.debug(f"ReplayManager: current_browser.new_context() returned: {type(current_context)}")
            if not (current_context and hasattr(current_context, 'playwright_context') and current_context.playwright_context):
                logger.error("ReplayManager: Newly created context is invalid or has no Playwright link.")
                print("[MANAGER get_page_for_replay_mgr] Newly created context is invalid. Raising exception.", flush=True)
                raise Exception("Newly created context is invalid or has no Playwright link.")
            logger.info("ReplayManager: New context created successfully.")
            print(f"[MANAGER get_page_for_replay_mgr] New context created successfully. Context pages: {len(current_context.pages) if current_context.pages else 'None'}", flush=True)
        except Exception as e_ctx:
            logger.error(f"ReplayManager: Failed to create new context on ui_browser: {e_ctx}", exc_info=True)
            print(f"[MANAGER get_page_for_replay_mgr] EXCEPTION during new context creation: {e_ctx}. Returning None.", flush=True)
            return None
    else:
        logger.debug("ReplayManager: Using provided ui_context as it seems valid.")
        print(f"[MANAGER get_page_for_replay_mgr] Using provided ui_context. Type: {type(ui_context)}, Pages: {len(current_context.pages) if current_context.pages else 'None'}", flush=True)
    
    logger.debug(f"ReplayManager: current_context type before page ops: {type(current_context)}")
    print(f"[MANAGER get_page_for_replay_mgr] Before page ops, current_context: {type(current_context)}, pages: {len(current_context.pages) if current_context.pages else 'None'}", flush=True)
    active_pages = current_context.pages
    logger.debug(f"ReplayManager: current_context.pages returned: {type(active_pages)}, Count: {len(active_pages) if active_pages is not None else 'N/A'}")
    print(f"[MANAGER get_page_for_replay_mgr] current_context.pages. Type: {type(active_pages)}, Count: {len(active_pages) if active_pages is not None else 'N/A'}", flush=True)

    if not active_pages:
        logger.info("ReplayManager: Context has no pages. Calling current_context.new_page().")
        print(f"[MANAGER get_page_for_replay_mgr] No active pages. Calling current_context.new_page(). Context: {type(current_context)}", flush=True)
        try: 
            await current_context.new_page()
            print(f"[MANAGER get_page_for_replay_mgr] current_context.new_page() called.", flush=True)
            active_pages = current_context.pages # Refresh
            logger.debug(f"ReplayManager: After new_page(), active_pages count: {len(active_pages) if active_pages is not None else 'N/A'}")
            print(f"[MANAGER get_page_for_replay_mgr] Refreshed active_pages. Count: {len(active_pages) if active_pages is not None else 'N/A'}", flush=True)
            if not active_pages: 
                logger.error("ReplayManager: Still no pages after new_page() call.")
                print("[MANAGER get_page_for_replay_mgr] Still no pages after new_page() call. Raising exception.", flush=True)
                raise Exception("Failed to create page in context.")
        except Exception as e_page: 
            logger.error(f"ReplayManager: PAGE CREATION FAILED: {e_page}", exc_info=True);
            print(f"[MANAGER get_page_for_replay_mgr] EXCEPTION during new page creation: {e_page}. Returning None.", flush=True)
            return None
    else:
        logger.debug("ReplayManager: Context already had pages.")
        print(f"[MANAGER get_page_for_replay_mgr] Context already had pages. Count: {len(active_pages)}", flush=True)
    
    active_page = active_pages[0]
    logger.debug(f"ReplayManager: active_page selected: {active_page.url if active_page else 'None'}")
    print(f"[MANAGER get_page_for_replay_mgr] Selected active_page: {type(active_page)}, URL: {active_page.url if active_page else 'None'}", flush=True)

    if active_page.url == "about:blank" or not active_page.url.startswith("http"):
        logger.info(f"ReplayManager: Page '{active_page.url}' is blank/non-HTTP. Navigating to Google.")
        print(f"[MANAGER get_page_for_replay_mgr] Attempting navigation to Google from {active_page.url}", flush=True)
        try: 
            print(f"[MANAGER get_page_for_replay_mgr] >>> TRYING: active_page.goto('https://www.google.com')", flush=True)
            # TEST: Using a simpler URL, shorter timeout, and different wait_until
            test_url_init_nav = "http://example.com"
            test_timeout_init_nav = 7000
            test_wait_until_init_nav = "load" # Try 'load' or 'commit'
            print(f"[MANAGER get_page_for_replay_mgr] >>> TEST PARAMS: url={test_url_init_nav}, timeout={test_timeout_init_nav}, wait_until={test_wait_until_init_nav}", flush=True)
            await active_page.goto(test_url_init_nav, wait_until=test_wait_until_init_nav, timeout=test_timeout_init_nav)
            logger.debug(f"ReplayManager: Navigation to Google complete. New URL: {active_page.url}")
            print(f"[MANAGER get_page_for_replay_mgr] Initial Navigation to {test_url_init_nav} SUCCEEDED. New URL: {active_page.url}", flush=True)
        except SyncPlaywrightTimeoutError as pte_nav_init:
            logger.error(f"[MANAGER get_page_for_replay_mgr] PlaywrightTimeoutError during initial navigation to {test_url_init_nav}: {pte_nav_init}", exc_info=True)
            print(f"[MANAGER get_page_for_replay_mgr] PlaywrightTimeoutError during initial navigation to {test_url_init_nav}: {pte_nav_init}", flush=True)
            return None # Critical failure, cannot proceed
        except Exception as e_nav_init: 
            logger.error(f"[MANAGER get_page_for_replay_mgr] Exception during initial navigation to {test_url_init_nav}: {e_nav_init}", exc_info=True)
            print(f"[MANAGER get_page_for_replay_mgr] Exception during initial navigation to {test_url_init_nav}: {e_nav_init}", flush=True)
            return None # Critical failure, cannot proceed
    logger.info(f"ReplayManager: Successfully obtained/prepared page '{active_page.url}'.")
    print(f"[MANAGER get_page_for_replay_mgr] Returning page: {active_page.url if active_page else 'None'}", flush=True)
    return active_page

# --- Global variables for replay thread parameters (specific to this manager now) ---
_mgr_replay_params_lock = threading.Lock() # Renamed to avoid conflict if webui.py still has old ones
_mgr_replay_current_params: Optional[Dict[str, Any]] = None

# Synchronous version of the core replay execution logic, to be run in a thread
def _execute_replay_sync_in_thread(
    trace_path: str, 
    speed: float, 
    override_files: Optional[List[Any]], 
    p_ui_async_q: asyncio.Queue, # Still an asyncio.Queue for now
    main_event_loop: asyncio.AbstractEventLoop, # Loop of the main thread for call_soon_threadsafe
    cdp_url: str  # Changed from cdp_ws_endpoint to cdp_url (e.g. http://localhost:9222)
):
    logger.debug(f"[SYNC_THREAD _execute_replay_sync] Entered. Trace: {trace_path}. CDP URL: {cdp_url}")
    main_event_loop.call_soon_threadsafe(p_ui_async_q.put_nowait, "🧵 Execution started (CDP).")

    try:
        # These variables will hold the Playwright objects created within the sync context
        # They are distinct from any async Playwright objects on the main thread.
        sync_browser = None
        sync_context_instance = None # Renamed to avoid conflict with 'context' module
        sync_page_for_replay = None

        with sync_playwright() as p:
            main_event_loop.call_soon_threadsafe(p_ui_async_q.put_nowait, f"🧵 Sync Playwright started. Connecting to CDP URL: {cdp_url}")
            logger.debug(f"[SYNC_THREAD _execute_replay_sync] Sync Playwright started. Connecting to CDP URL: {cdp_url}")
            
            sync_browser = p.chromium.connect_over_cdp(cdp_url)
            main_event_loop.call_soon_threadsafe(p_ui_async_q.put_nowait, "🧵 Browser launched/connected via CDP.")
            logger.debug(f"[SYNC_THREAD _execute_replay_sync] Browser launched/connected via CDP: {type(sync_browser)}")

            # Use the existing persistent context from the CDP-connected browser
            if sync_browser.contexts:
                sync_context_instance = sync_browser.contexts[0] # Assuming the first is the persistent default
                logger.debug(f"[SYNC_THREAD _execute_replay_sync] Using existing persistent context (0). Original pages: {len(sync_context_instance.pages)}")
                main_event_loop.call_soon_threadsafe(p_ui_async_q.put_nowait, "🧵 Using existing persistent context.")
            else:
                err_msg_ctx = "🧵 ERROR: No contexts found in CDP-connected browser. Cannot use persistent profile."
                logger.error(err_msg_ctx)
                main_event_loop.call_soon_threadsafe(p_ui_async_q.put_nowait, err_msg_ctx)
                if sync_browser.is_connected(): sync_browser.close()
                return

            # Call the synchronous page helper
            sync_page_for_replay = get_page_for_replay_mgr_sync(sync_context_instance, p_ui_async_q, main_event_loop)

            if not sync_page_for_replay:
                err_msg_helper = "🧵 get_page_for_replay_mgr_sync failed to return a page."
                logger.error(err_msg_helper)
                main_event_loop.call_soon_threadsafe(p_ui_async_q.put_nowait, err_msg_helper)
                if sync_browser.is_connected(): sync_browser.close() # Clean up browser before returning
                return # Stop if page prep fails
            
            logger.debug(f"[SYNC_THREAD _execute_replay_sync] Page for replay ready. URL: {sync_page_for_replay.url}")
            main_event_loop.call_soon_threadsafe(p_ui_async_q.put_nowait, f"🧵 Page for replay ready: {sync_page_for_replay.url}")

            # --- Placeholder for calling the actual (refactored) TraceReplayerSync ---
            main_event_loop.call_soon_threadsafe(p_ui_async_q.put_nowait, "🧵 Loading trace events...")
            trace_events = load_trace(trace_path)
            logger.debug(f"[SYNC_THREAD _execute_replay_sync] Loaded {len(trace_events)} trace events.")
            main_event_loop.call_soon_threadsafe(p_ui_async_q.put_nowait, f"🧵 Loaded {len(trace_events)} trace events.")

            logger.debug(f"[SYNC_THREAD _execute_replay_sync] Initializing controller (CustomControllerSync).")
            controller_for_sync_replay = CustomControllerSync(page=sync_page_for_replay) # Pass the sync Page
            main_event_loop.call_soon_threadsafe(p_ui_async_q.put_nowait, "🧵 Controller initialized (CustomControllerSync).")

            logger.debug(f"[SYNC_THREAD _execute_replay_sync] Initializing TraceReplayerSync.")
            replayer_sync = TraceReplayerSync(
                sync_page_for_replay, 
                trace_events, 
                controller_for_sync_replay, 
                override_files, 
                p_ui_async_q, 
                main_event_loop
            )
            main_event_loop.call_soon_threadsafe(p_ui_async_q.put_nowait, "🧵 TraceReplayerSync initialized. Starting play().")
            logger.debug(f"[SYNC_THREAD _execute_replay_sync] Starting replayer_sync.play(speed={speed})")

            replayer_sync.play(speed) # This is now a synchronous call

            logger.debug(f"[SYNC_THREAD _execute_replay_sync] replayer_sync.play() finished.")
            main_event_loop.call_soon_threadsafe(p_ui_async_q.put_nowait, "🧵 Replay allegedly finished.")
            # --------------------------------------------------------------------------

            logger.debug("[SYNC_THREAD _execute_replay_sync] Closing browser...")
            # As per architecture: only close the page/target created for this replay.
            # The browser (CDP connection) is managed by the 'with sync_playwright()' context manager.
            if sync_page_for_replay and not sync_page_for_replay.is_closed():
                logger.debug(f"[SYNC_THREAD _execute_replay_sync] Closing replay page: {sync_page_for_replay.url}")
                sync_page_for_replay.close()
                main_event_loop.call_soon_threadsafe(p_ui_async_q.put_nowait, "🧵 Replay page closed.")
            # Do not close sync_browser here; it refers to the persistent CDP connection which should stay open.
            # sync_browser.close() would disconnect this thread from the shared browser.
            main_event_loop.call_soon_threadsafe(p_ui_async_q.put_nowait, "🧵 CDP Connection for thread will be closed by context manager.")

    except SyncPlaywrightTimeoutError as pte_sync:
        err_msg = f"🧵 PlaywrightTimeoutError: {pte_sync}"
        logger.error(err_msg, exc_info=True)
        main_event_loop.call_soon_threadsafe(p_ui_async_q.put_nowait, err_msg)
    except Exception as e_sync:
        err_msg = f"🧵 EXCEPTION: {e_sync}"
        logger.error(err_msg, exc_info=True)
        main_event_loop.call_soon_threadsafe(p_ui_async_q.put_nowait, err_msg)
    finally:
        final_msg = "🧵 Execution finished."
        logger.debug(final_msg)
        main_event_loop.call_soon_threadsafe(p_ui_async_q.put_nowait, final_msg)

           
# --- Threading helpers (now part of this manager) ---
def _run_replay_logic_in_thread_mgr(done_event: threading.Event):
    global _mgr_replay_current_params, logger
    logger.debug("[MANAGER THREAD _run_replay_logic_in_thread_mgr] Entered")
    # Remove local params copy if not used for browser/context config for sync playwright
    current_params_snapshot = {}
    with _mgr_replay_params_lock:
        if _mgr_replay_current_params: current_params_snapshot = _mgr_replay_current_params.copy()

    if not current_params_snapshot: 
        # This part should ideally send error back via queue if possible, but queue isn't available yet.
        logger.error("ReplayManager Thread: No parameters dictionary found."); done_event.set(); return

    trace_path = current_params_snapshot.get("trace_path")
    speed = current_params_snapshot.get("speed")
    override_files = current_params_snapshot.get("override_files")
    # ui_browser_from_params and ui_context_from_params are no longer used by the sync version directly
    ui_async_q_from_params = current_params_snapshot.get("ui_async_q") # Get the asyncio.Queue
    main_event_loop_from_params = current_params_snapshot.get("main_event_loop")
    cdp_url_from_params = current_params_snapshot.get("cdp_url")

    if not trace_path: logger.error("ReplayManager Thread: 'trace_path' not found."); done_event.set(); return
    if speed is None: logger.error("ReplayManager Thread: 'speed' not found."); done_event.set(); return
    if not ui_async_q_from_params: logger.error("ReplayManager Thread: 'ui_async_q' not found."); done_event.set(); return
    if not main_event_loop_from_params: logger.error("ReplayManager Thread: 'main_event_loop' not found."); done_event.set(); return
    if not cdp_url_from_params: logger.error("ReplayManager Thread: 'cdp_url' not found."); done_event.set(); return # Critical

    # No more asyncio event loop creation here
    try:
        # Directly call the new synchronous function
        _execute_replay_sync_in_thread(
            str(trace_path), 
            float(speed), 
            override_files, 
            ui_async_q_from_params,
            main_event_loop_from_params,
            cdp_url_from_params
        )
        logger.debug(f"[MANAGER THREAD _run_replay_logic_in_thread_mgr] _execute_replay_sync_in_thread completed for {trace_path}")

    except Exception as e:
        # This top-level exception in the thread function itself
        err_msg = f"ReplayManager Thread: UNHANDLED EXCEPTION in _run_replay_logic_in_thread_mgr for {trace_path}: {e}"
        logger.error(err_msg, exc_info=True)
        # Try to put error message on the queue if possible
        if ui_async_q_from_params and main_event_loop_from_params:
            try: 
                main_event_loop_from_params.call_soon_threadsafe(ui_async_q_from_params.put_nowait, f"THREAD FATAL ERROR: {err_msg}")
            except Exception as q_err: 
                logger.error(f"ReplayManager Thread: Failed to put FATAL error on ui_async_q: {q_err}")
    finally: 
        logger.debug("[MANAGER THREAD _run_replay_logic_in_thread_mgr] Setting done_event.")
        if done_event: done_event.set()

# MODIFIED: start_replay_async_thread_mgr now takes browser/context
def start_replay_sync_api_in_thread( # Renamed function for clarity
    trace_path: str, 
    speed: float, 
    override_files: Optional[List[Any]], 
    p_ui_async_q: asyncio.Queue, 
    p_main_event_loop: asyncio.AbstractEventLoop,
    cdp_url: str # Changed from cdp_ws_endpoint to cdp_url (e.g. http://localhost:9222)
) -> threading.Event:
    global _mgr_replay_current_params, logger
    logger.debug("[MANAGER ASYNC_STARTER] start_replay_sync_api_in_thread ENTERED")
    with _mgr_replay_params_lock:
        _mgr_replay_current_params = {
            "trace_path": trace_path, "speed": speed, "override_files": override_files,
            "ui_async_q": p_ui_async_q, # Store the asyncio.Queue
            "main_event_loop": p_main_event_loop, # Store the main event loop
            "cdp_url": cdp_url # Store the CDP URL
        }
        logger.debug(f"[MANAGER ASYNC_STARTER] _mgr_replay_current_params SET: { {k: type(v) for k,v in _mgr_replay_current_params.items()} }")
    done = threading.Event()
    logger.debug("[MANAGER ASYNC_STARTER] Creating Thread object...")
    thread = threading.Thread(target=_run_replay_logic_in_thread_mgr, args=(done,), daemon=True)
    logger.debug("[MANAGER ASYNC_STARTER] Starting Thread...")
    thread.start()
    logger.info(f"ReplayManager: Replay thread created/started for trace: {trace_path}")
    logger.debug("[MANAGER ASYNC_STARTER] Thread started. Returning done_event.")
    return done

# UPDATED: now takes sync_context from the sync API in the thread
def get_page_for_replay_mgr_sync(
    sync_context: SyncBrowserContext, 
    p_ui_async_q: asyncio.Queue, 
    main_loop: asyncio.AbstractEventLoop,
    # Potentially pass AppCustomBrowserContextConfig or relevant parts if needed for new context logic
) -> Optional[SyncPage]:
    logger.debug(f"[SYNC_THREAD get_page_for_replay_mgr_sync] ENTRY. sync_context type: {type(sync_context)}")
    main_loop.call_soon_threadsafe(p_ui_async_q.put_nowait, "🪡  get_page_for_replay_mgr_sync started.")

    # Note: Logic for creating a new context if sync_context is invalid is removed for now,
    # as sync_context is expected to be freshly created by _execute_replay_sync_in_thread.
    # This function now primarily ensures a page exists in the given sync_context.

    if not sync_context:
        return None

    active_pages = sync_context.pages
    logger.debug(f"[SYNC_THREAD get_page_for_replay_mgr_sync] Existing pages in sync_context: {len(active_pages)}")

    if not active_pages:
        logger.debug("[SYNC_THREAD get_page_for_replay_mgr_sync] No active pages in sync_context. Creating new page.")
        try:
            page = sync_context.new_page()
            logger.debug(f"[SYNC_THREAD get_page_for_replay_mgr_sync] New page created. URL: {page.url}")
            main_loop.call_soon_threadsafe(p_ui_async_q.put_nowait, f"🪡  New page created: {page.url}")
            active_pages = [page] # sync_context.pages should update but let's be explicit
        except Exception as e_page_sync:
            err_msg = f"[SYNC_THREAD get_page_for_replay_mgr_sync] EXCEPTION during new page creation: {e_page_sync}"
            logger.error(err_msg, exc_info=True)
            logger.error(err_msg, exc_info=True)
            main_loop.call_soon_threadsafe(p_ui_async_q.put_nowait, f"🪡  ERROR creating page: {e_page_sync}")
            return None
    
    active_page = active_pages[0]
    logger.debug(f"[SYNC_THREAD get_page_for_replay_mgr_sync] Selected page. Current URL: {active_page.url}")
    main_loop.call_soon_threadsafe(p_ui_async_q.put_nowait, f"🪡  Selected page URL: {active_page.url}")

    # Page is prepared (either new 'about:blank' or an existing one).
    # No further navigation is done here; TraceReplayerSync will handle the first trace navigation.
    logger.debug(f"[SYNC_THREAD get_page_for_replay_mgr_sync] Page ready for TraceReplayer. Current URL: {active_page.url}")
    main_loop.call_soon_threadsafe(p_ui_async_q.put_nowait, f"🪡  Page for replay (initial state): {active_page.url}")
    
    logger.debug(f"[SYNC_THREAD get_page_for_replay_mgr_sync] Returning page. Final URL: {active_page.url}")
    main_loop.call_soon_threadsafe(p_ui_async_q.put_nowait, f"🪡  get_page_for_replay_mgr_sync finished. Page URL: {active_page.url}")
    return active_page