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
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

# --- Project-specific imports needed by replay logic ---
from src.browser.custom_browser import CustomBrowser
from src.browser.custom_context import CustomBrowserContext
from src.controller.custom_controller import CustomController
from src.utils.replayer import TraceReplayer, load_trace, Drift
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
        except PlaywrightTimeoutError as pte_nav_init:
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

# MODIFIED: actual_replay_trace_wrapper_mgr now takes browser/context
# run at stream_replay
async def actual_replay_trace_wrapper_mgr(
    selected_trace_path: str, 
    local_replay_speed: float, 
    override_files_list: Optional[List[Union[tempfile._TemporaryFileWrapper, str]]],
    ui_browser: CustomBrowser, 
    ui_context: CustomBrowserContext,
    ui_async_q: asyncio.Queue  # New parameter for streaming
): #: # No longer returns str
    print(f"[MANAGER ACTUAL_REPLAY_WRAPPER] Entered for {selected_trace_path}", flush=True)
    print(f"[MANAGER ARGS CHECK] selected_trace_path: {selected_trace_path}, type: {type(selected_trace_path)}", flush=True)
    print(f"[MANAGER ARGS CHECK] local_replay_speed: {local_replay_speed}, type: {type(local_replay_speed)}", flush=True)
    print(f"[MANAGER ARGS CHECK] override_files_list: {override_files_list}, type: {type(override_files_list)}", flush=True)
    print(f"[MANAGER ARGS CHECK] ui_browser: {ui_browser}, type: {type(ui_browser)}", flush=True)
    print(f"[MANAGER ARGS CHECK] ui_context: {ui_context}, type: {type(ui_context)}", flush=True)
    print(f"[MANAGER ARGS CHECK] ui_async_q: {ui_async_q}, type: {type(ui_async_q)}", flush=True)

    await ui_async_q.put(f"--- Replay starting for '{Path(selected_trace_path).name}' (manager) ---")
    print(f"[MANAGER ACTUAL_REPLAY_WRAPPER] Put '--- Replay starting...' on ui_async_q", flush=True)

    print(f"[MANAGER ACTUAL_REPLAY_WRAPPER] About to call get_page_for_replay_mgr.", flush=True)
    page_for_replay = await get_page_for_replay_mgr(ui_browser, ui_context)
    print(f"[MANAGER ACTUAL_REPLAY_WRAPPER] get_page_for_replay_mgr returned. page_for_replay is: {page_for_replay}", flush=True)
    
    if not page_for_replay: 
        logger.error("actual_replay_trace_wrapper_mgr: get_page_for_replay_mgr returned no page.")
        await ui_async_q.put("Error: Browser page not available (manager)")
        print(f"[MANAGER ACTUAL_REPLAY_WRAPPER] Put 'Error: Browser page not available' on ui_async_q", flush=True)
        return
    
    logger.debug(f"actual_replay_trace_wrapper_mgr: Page for replay is: {page_for_replay.url}")
    controller_browser_context = ui_context # Controller uses the passed context
    
    try:
        logger.debug(f"actual_replay_trace_wrapper_mgr: Creating CustomController with context type: {type(controller_browser_context)}")
        controller = CustomController(browser_context=controller_browser_context)
        logger.debug("actual_replay_trace_wrapper_mgr: CustomController created.")

        await ui_async_q.put(f"Loading trace: {selected_trace_path}")
        print(f"[MANAGER ACTUAL_REPLAY_WRAPPER] Put 'Loading trace...' on ui_async_q", flush=True)
        trace_events = load_trace(selected_trace_path)
        if not trace_events: 
            logger.error(f"actual_replay_trace_wrapper_mgr: Trace file {selected_trace_path} is empty or failed to load.")
            await ui_async_q.put(f"Error: Trace file {selected_trace_path} empty or failed to load.")
            print(f"[MANAGER ACTUAL_REPLAY_WRAPPER] Put 'Error: Trace file empty' on ui_async_q", flush=True)
            return
        logger.debug(f"actual_replay_trace_wrapper_mgr: Loaded {len(trace_events)} events.")
        await ui_async_q.put(f"Loaded {len(trace_events)} events from trace.")
        print(f"[MANAGER ACTUAL_REPLAY_WRAPPER] Put 'Loaded {len(trace_events)} events' on ui_async_q", flush=True)

        processed_override_files = []
        if override_files_list:
            msg = f"Processing {len(override_files_list)} override files."
            logger.debug(f"actual_replay_trace_wrapper_mgr: {msg}")
            await ui_async_q.put(msg)
            for i, f_item in enumerate(override_files_list):
                if isinstance(f_item, str):
                    processed_override_files.append(f_item)
                elif hasattr(f_item, 'name') and isinstance(f_item.name, str):
                    processed_override_files.append(f_item.name)
                else:
                    logger.warning(f"actual_replay_trace_wrapper_mgr: Skipping unexpected item type {type(f_item)} in override_files_list at index {i}.")
        else:
            logger.debug("actual_replay_trace_wrapper_mgr: No override files provided.")
            await ui_async_q.put("No override files provided.")
            print(f"[MANAGER ACTUAL_REPLAY_WRAPPER] Put 'No override files' or count on ui_async_q", flush=True)
        
        await ui_async_q.put(f"Instantiating Replayer. Page URL: {page_for_replay.url if page_for_replay else 'None'}, Overrides: {len(processed_override_files)}")
        print(f"[MANAGER ACTUAL_REPLAY_WRAPPER] Put 'Instantiating Replayer...' on ui_async_q", flush=True)
        print(f"[MANAGER TRACE_REPLAYER_INIT_ARGS] page_for_replay: {page_for_replay} (URL: {page_for_replay.url if page_for_replay else 'N/A'})", flush=True)
        print(f"[MANAGER TRACE_REPLAYER_INIT_ARGS] trace_events (first 3 if any): {trace_events[:3] if trace_events else 'None'}, Count: {len(trace_events) if trace_events else 0}", flush=True)
        print(f"[MANAGER TRACE_REPLAYER_INIT_ARGS] controller: {controller}, type: {type(controller)}", flush=True)
        print(f"[MANAGER TRACE_REPLAYER_INIT_ARGS] user_provided_files: {processed_override_files}", flush=True)

        replayer = TraceReplayer(
            page_for_replay, 
            trace_events, 
            controller,
            user_provided_files=processed_override_files
        )
        await ui_async_q.put("TraceReplayer instantiated. Starting playback...")
        print(f"[MANAGER ACTUAL_REPLAY_WRAPPER] Put 'TraceReplayer instantiated...' on ui_async_q", flush=True)
        
        # Initial harvest before play, in case of pre-play logs from replayer setup
        initial_harvest = harvest_logs_for_ui()
        if initial_harvest:
            for line in initial_harvest.splitlines():
                await ui_async_q.put(line)
                print(f"[MANAGER ACTUAL_REPLAY_WRAPPER] Put harvested pre-play log line on ui_async_q: {line}", flush=True)

        await replayer.play(speed=local_replay_speed) # This is where src.utils.replayer logs should begin appearing in the log_q
        print(f"[MANAGER ACTUAL_REPLAY_WRAPPER] replayer.play() completed", flush=True)

        # After play is done, harvest any remaining logs
        final_harvest = harvest_logs_for_ui()
        if final_harvest:
            for line in final_harvest.splitlines():
                await ui_async_q.put(line)
                print(f"[MANAGER ACTUAL_REPLAY_WRAPPER] Put harvested post-play log line on ui_async_q: {line}", flush=True)

        status_message_final = f"Input trace '{Path(selected_trace_path).name}' replayed successfully."
        logger.info(f"actual_replay_trace_wrapper_mgr: replayer.play() completed. {status_message_final}")
        await ui_async_q.put(status_message_final)
        print(f"[MANAGER ACTUAL_REPLAY_WRAPPER] Put final success message on ui_async_q", flush=True)

    except Drift as d: 
        status_message_final = f"Drift error: {d}"
        logger.error(f"actual_replay_trace_wrapper_mgr: {status_message_final}", exc_info=True)
        await ui_async_q.put(status_message_final)
        print(f"[MANAGER ACTUAL_REPLAY_WRAPPER] Put Drift error on ui_async_q", flush=True)
    except Exception as e: 
        status_message_final = f"General error during replay: {e}"
        logger.error(f"actual_replay_trace_wrapper_mgr: {status_message_final}", exc_info=True)
        await ui_async_q.put(status_message_final)
        print(f"[MANAGER ACTUAL_REPLAY_WRAPPER] Put General error on ui_async_q", flush=True)
    
    await ui_async_q.put(f"--- Replay Finished (actual_replay_trace_wrapper_mgr) for '{Path(selected_trace_path).name}' ---")
    print(f"[MANAGER ACTUAL_REPLAY_WRAPPER] Put '--- Replay Finished ---' on ui_async_q. Exiting.", flush=True)

# --- Global variables for replay thread parameters (specific to this manager now) ---
_mgr_replay_params_lock = threading.Lock() # Renamed to avoid conflict if webui.py still has old ones
_mgr_replay_current_params: Optional[Dict[str, Any]] = None

# --- Threading helpers (now part of this manager) ---
def _run_replay_logic_in_thread_mgr(done_event: threading.Event):
    print("[MANAGER DEBUG] THREAD: _run_replay_logic_in_thread_mgr ENTERED", flush=True)
    global _mgr_replay_current_params, logger
    params = None
    with _mgr_replay_params_lock:
        if _mgr_replay_current_params: params = _mgr_replay_current_params.copy()
    if not params: 
        logger.error("ReplayManager Thread: No parameters dictionary found."); 
        if done_event: done_event.set(); 
        return
    trace_path = params.get("trace_path")
    speed = params.get("speed")
    override_files = params.get("override_files")
    ui_browser_from_params = params.get("ui_browser")
    ui_context_from_params = params.get("ui_context")
    ui_async_q_from_params = params.get("ui_async_q") # Get the asyncio.Queue

    if not trace_path: logger.error("ReplayManager Thread: 'trace_path' not found."); done_event.set(); return
    if speed is None: logger.error("ReplayManager Thread: 'speed' not found."); done_event.set(); return
    if not ui_browser_from_params: logger.error("ReplayManager Thread: 'ui_browser' not found."); done_event.set(); return
    if not ui_context_from_params: logger.error("ReplayManager Thread: 'ui_context' not found."); done_event.set(); return
    if not ui_async_q_from_params: logger.error("ReplayManager Thread: 'ui_async_q' not found."); done_event.set(); return

    logger.info(f"ReplayManager Thread: Validated params. Starting replay for trace: {trace_path}")

    async def minimal_playwright_test_in_thread(context: CustomBrowserContext, p_ui_async_q: asyncio.Queue):
        print("[THREAD_TEST] Entered minimal_playwright_test_in_thread", flush=True)
        await p_ui_async_q.put("[THREAD_TEST] Minimal test started.")
        a_page = None
        page_url_test = "[THREAD_TEST] Page URL could not be retrieved."
        try:
            if not context.pages:
                print("[THREAD_TEST] No pages in context, creating one.", flush=True)
                await context.new_page()
                if not context.pages:
                    await p_ui_async_q.put("[THREAD_TEST] FAILED to create page.")
                    print("[THREAD_TEST] FAILED to create page, returning.", flush=True)
                    return
            a_page = context.pages[0]
            print(f"[THREAD_TEST] Got page: {a_page.url if a_page else 'None'}", flush=True)
            page_url_test = f"[THREAD_TEST] Page URL before any action: {a_page.url if a_page else 'None'}"
            print(page_url_test, flush=True)
            await p_ui_async_q.put(page_url_test)

            # Commenting out the goto call for this test
            # target_url = "http://example.com"
            # print(f"[THREAD_TEST] Attempting page.goto('{target_url}')", flush=True)
            # await a_page.goto(target_url, timeout=7000, wait_until="load")
            # print(f"[THREAD_TEST] page.goto('{target_url}') SUCCEEDED. New URL: {a_page.url}", flush=True)
            # await p_ui_async_q.put(f"[THREAD_TEST] Navigation to {target_url} SUCCEEDED. New URL: {a_page.url}")
            await p_ui_async_q.put("[THREAD_TEST] Skipped goto for this test.")

        except PlaywrightTimeoutError as pte:
            print(f"[THREAD_TEST] PlaywrightTimeoutError: {pte}", flush=True)
            await p_ui_async_q.put(f"[THREAD_TEST] PlaywrightTimeoutError: {pte}")
        except Exception as e:
            print(f"[THREAD_TEST] EXCEPTION: {e}", flush=True)
            await p_ui_async_q.put(f"[THREAD_TEST] EXCEPTION: {e}")
        finally:
            print("[THREAD_TEST] Minimal test finished.", flush=True)
            await p_ui_async_q.put("[THREAD_TEST] Minimal test finished execution.")

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Call the minimal test instead of the full replay wrapper
        loop.run_until_complete(actual_replay_trace_wrapper_mgr(
            str(trace_path), 
            float(speed), 
            override_files, 
            ui_browser_from_params, 
            ui_context_from_params,
            ui_async_q_from_params # Pass the queue
        ))
        logger.info(f"ReplayManager Thread: actual_replay_trace_wrapper_mgr completed for trace: {trace_path}.") # Original log
        print(f"[MANAGER THREAD _run_replay_logic_in_thread_mgr] actual_replay_trace_wrapper_mgr completed for {trace_path}", flush=True)

    except Exception as e:
        err_msg = f"ReplayManager Thread: Error during replay logic for {trace_path}: {e}" # Modified error message slightly
        logger.error(err_msg, exc_info=True)
        print(f"[MANAGER THREAD _run_replay_logic_in_thread_mgr] EXCEPTION: {err_msg}", flush=True)
        # Try to put error message on the queue if possible
        try: asyncio.run_coroutine_threadsafe(ui_async_q_from_params.put(f"THREAD ERROR: {err_msg}"), loop).result(timeout=1)
        except Exception as q_err: logger.error(f"ReplayManager Thread: Failed to put error on ui_async_q: {q_err}")
    finally:
        print("[MANAGER THREAD _run_replay_logic_in_thread_mgr] Setting done_event.", flush=True)
        if done_event: done_event.set()

# MODIFIED: start_replay_async_thread_mgr now takes browser/context
def start_replay_async_thread_mgr(trace_path: str, speed: float, override_files: Optional[List[Any]], ui_browser: CustomBrowser, ui_context: CustomBrowserContext, ui_async_q: asyncio.Queue) -> threading.Event:
    print("[MANAGER ASYNC_STARTER] start_replay_async_thread_mgr ENTERED", flush=True)
    global _mgr_replay_current_params, logger
    with _mgr_replay_params_lock:
        _mgr_replay_current_params = {
            "trace_path": trace_path, "speed": speed, "override_files": override_files,
            "ui_browser": ui_browser, "ui_context": ui_context,
            "ui_async_q": ui_async_q # Store the queue
        }
        print("[MANAGER ASYNC_STARTER] _mgr_replay_current_params SET", flush=True)
    done = threading.Event()
    print("[MANAGER ASYNC_STARTER] Creating Thread object...", flush=True)
    thread = threading.Thread(target=_run_replay_logic_in_thread_mgr, args=(done,), daemon=True)
    print("[MANAGER ASYNC_STARTER] Starting Thread...", flush=True)
    thread.start()
    logger.info(f"ReplayManager: Replay thread created/started for trace: {trace_path}")
    print("[MANAGER ASYNC_STARTER] Thread started. Returning done_event.", flush=True)
    return done

# Removed replay_log_streamer_snippet as it's superseded by the new UI streaming mechanism in webui.py