import pdb
import logging
import os
import gradio as gr
import queue 
import threading 
import time 
import asyncio 
import tempfile
from typing import Optional, List, Dict, Any, Union, Callable, Tuple, AsyncGenerator
from pathlib import Path
from gradio.themes import Default, Soft, Glass, Monochrome, Ocean, Origin, Base, Citrus
import pandas as pd
from playwright.async_api import BrowserContext as PlaywrightBrowserContextType, Browser as PlaywrightBrowser
from playwright.async_api import Browser # For isinstance check
# from playwright.async_api import async_playwright # Ensure this is removed if only for old recording logic

from dotenv import load_dotenv
load_dotenv()

# Import task templates
from task_templates import TASK_TEMPLATES

# --- Project-specific global imports needed by replay logic ---
from src.browser.custom_browser import CustomBrowser
from src.browser.custom_context import CustomBrowserContext
from src.browser.custom_context_config import CustomBrowserContextConfig as AppCustomBrowserContextConfig
from browser_use.browser.browser import BrowserConfig
from src.utils.trace_utils import get_upload_file_names_from_trace # ADDED
from src.utils import user_input_functions # ADDED for get_file_info
from browser_use.browser.context import BrowserContextWindowSize # ADDED IMPORT

# --- Global Logging Setup ---
from src.utils.replay_streaming_manager import start_replay_sync_api_in_thread, log_q as manager_log_q

# BasicConfig should still be called once in webui.py for general console logging
if not logging.getLogger().handlers and not logging.getLogger().hasHandlers():
    logging.basicConfig(
        level=logging.INFO, 
        format='%(asctime)s - %(name)s - %(levelname)s - [%(module)s.%(funcName)s:%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
else:
    if logging.getLogger().getEffectiveLevel() > logging.DEBUG:
        logging.getLogger().setLevel(logging.DEBUG)

# --- Specific logger levels for DEBUG ---
logging.getLogger('src.utils.replayer').setLevel(logging.DEBUG)
logging.getLogger('src.controller.custom_controller').setLevel(logging.DEBUG)

logger = logging.getLogger(__name__) # Logger for webui.py itself
logger.info("WebUI: Base logging configured. UI log: ReplayStreamingManager.")

# --- NEW Global Queue for Recorder Event Logs ---
RECORDER_EVENT_LOG_Q: asyncio.Queue[str] = asyncio.Queue()

# --- Global Constants ---
MANUAL_TRACES_DIR = "./tmp/input_tracking"

# --- Global Helper Functions (e.g. trace file listing) ---
def refresh_traces(): 
    logger.info("refresh_traces called")
    try:
        files_details_list = user_input_functions.list_input_trace_files(MANUAL_TRACES_DIR)
        df_rows = []
        for item_dict in files_details_list:
            if isinstance(item_dict, dict):
                df_rows.append([
                    item_dict.get("name", "N/A"),
                    item_dict.get("created", "N/A"),
                    item_dict.get("size", "N/A"),
                    item_dict.get("events", "N/A")
                ])
        if df_rows: 
            pandas_df = pd.DataFrame(df_rows, columns=["Name", "Created", "Size", "Events"])
            return pandas_df, files_details_list
        else:
            logger.info("No trace files found or processed by refresh_traces.")
            return pd.DataFrame(columns=["Name", "Created", "Size", "Events"]), []
    except Exception as e:
        logger.error(f"Error in refresh_traces: {e}", exc_info=True)
    return pd.DataFrame(columns=["Name", "Created", "Size", "Events"]), []

# --- Global Browser/Context Variables ---
_ui_global_browser: Optional[CustomBrowser] = None
_ui_global_browser_context: Optional[CustomBrowserContext] = None
# _global_agent: Optional[Any] = None # This can be reviewed/removed if not used elsewhere
# The old _global_input_tracking_active (if it existed here) is replaced by the new ones below.

# --- NEW Global variables for Recording Feature ---
_global_input_tracking_active: bool = False
_last_manual_trace_path: Optional[str] = None
# Note: The old, separate _global_browser and _global_browser_context for recording have been removed.

# --- NEW Global variable for the replay-specific context ---
# This variable needs to be set by your UI logic when a suitable context is active.
GLOBAL_REPLAY_BROWSER_CTX: Optional[CustomBrowserContext] = None

# --- Global Helper Function for Replay Logic: context_is_closed ---
def context_is_closed(ctx: Optional[PlaywrightBrowserContextType]) -> bool:
    """Checks if a Playwright BrowserContext is closed."""
    if not ctx: return True
    try: 
        # Accessing pages on a closed context raises an error.
        # Also check if pages list itself is None, which can happen if context was not properly initialized
        # or if the underlying Playwright context object is in an invalid state.
        if ctx.pages is None: # Explicitly check if pages attribute is None
            logger.warning("context_is_closed: context.pages is None, treating as unusable/closed.")
            return True
        _ = ctx.pages # Trigger potential error if closed
        return False
    except Exception as e:
        logger.debug(f"context_is_closed: Exception caught (likely closed context): {e}")
        return True

# --- Global Helper Function for Replay Logic: ensure_browser_session ---
async def ensure_browser_session(
    force_new_context_if_existing: bool = False,
) -> Tuple[Optional[CustomBrowser], Optional[CustomBrowserContext]]:
    global _ui_global_browser, _ui_global_browser_context, logger
    async with _browser_init_lock:
        browser_needs_real_init = False
        if not _ui_global_browser: browser_needs_real_init = True
        elif not _ui_global_browser._actual_playwright_browser: _ui_global_browser = None; browser_needs_real_init = True        
        else:
            core_pw_object = _ui_global_browser._actual_playwright_browser
            if isinstance(core_pw_object, PlaywrightBrowser):
                if not core_pw_object.is_connected(): _ui_global_browser = None; browser_needs_real_init = True
            elif isinstance(core_pw_object, PlaywrightBrowserContextType):
                if context_is_closed(core_pw_object): _ui_global_browser = None; browser_needs_real_init = True;
            else: _ui_global_browser = None; browser_needs_real_init = True;
        if browser_needs_real_init:            
            cdp_url = os.getenv("CHROME_CDP_URL"); chrome_path = os.getenv("CHROME_PATH")             
            cfg = BrowserConfig(headless=False,disable_security=True,cdp_url=cdp_url,chrome_instance_path=chrome_path,extra_chromium_args=[f"--window-size={1280},{1100}","--disable-web-security"])
            _ui_global_browser = CustomBrowser(config=cfg)
            try: 
                await _ui_global_browser.async_init()
                if not _ui_global_browser._actual_playwright_browser: raise Exception("async_init fail")
                if _ui_global_browser_context and hasattr(_ui_global_browser_context, 'browser') and _ui_global_browser_context.browser != _ui_global_browser: 
                    try: await _ui_global_browser_context.close() 
                    except: pass
                    _ui_global_browser_context = None
            except Exception as e: logger.error(f"Browser Init Fail: {e}",exc_info=True);_ui_global_browser=None;return None,None
        if not _ui_global_browser: return None,None
        context_needs_recheck=False
        if not _ui_global_browser_context: context_needs_recheck=True
        elif hasattr(_ui_global_browser_context,'browser') and _ui_global_browser_context.browser!=_ui_global_browser: 
            try: await _ui_global_browser_context.close() 
            except: pass
            _ui_global_browser_context=None;context_needs_recheck=True
        elif not hasattr(_ui_global_browser_context,'playwright_context') or context_is_closed(_ui_global_browser_context.playwright_context): 
            _ui_global_browser_context=None;context_needs_recheck=True
        if force_new_context_if_existing and _ui_global_browser_context:
            try: await _ui_global_browser_context.close() 
            except: pass
            _ui_global_browser_context=None;context_needs_recheck=True
        if context_needs_recheck:
            try:
                cfg=AppCustomBrowserContextConfig(enable_input_tracking=False,browser_window_size=BrowserContextWindowSize(width=1280,height=1100))
                if _ui_global_browser.config and _ui_global_browser.config.cdp_url: _ui_global_browser_context=await _ui_global_browser.reuse_existing_context(config=cfg)
                if not _ui_global_browser_context: _ui_global_browser_context=await _ui_global_browser.new_context(config=cfg)
                if not(_ui_global_browser_context and _ui_global_browser_context.playwright_context):raise Exception("Context link invalid")
            except Exception as e:logger.error(f"Context Establish Fail: {e}",exc_info=True);_ui_global_browser_context=None
        if _ui_global_browser_context and not _ui_global_browser_context.pages:
            try:
                await _ui_global_browser_context.new_page()
                if not _ui_global_browser_context.pages:logger.error("Failed to create page")
            except Exception as e:logger.error(f"Error creating page: {e}",exc_info=True)
        if not(_ui_global_browser and _ui_global_browser_context and _ui_global_browser_context.pages): logger.warning("Session incomplete")
    return _ui_global_browser,_ui_global_browser_context

# Refactored to be a regular async function, sends logs to RECORDER_EVENT_LOG_Q
async def start_input_tracking_with_context() -> Tuple[Any, ...]:
    global _ui_global_browser_context # Uses the shared context populated by ensure_browser_session
    global _global_input_tracking_active, _last_manual_trace_path, RECORDER_EVENT_LOG_Q

    def _log_to_q(msg: str, is_error: bool = False):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        formatted_msg = f"[{timestamp}] {msg}"
        if is_error: logger.error(msg, exc_info=True if "exception" in msg.lower() or "error" in msg.lower() else False)
        else: logger.info(msg) # Keep internal logging
        try:
            RECORDER_EVENT_LOG_Q.put_nowait(formatted_msg)
        except asyncio.QueueFull:
            logger.warning(f"RECORDER_EVENT_LOG_Q full. Dropped: {formatted_msg}")

    status_update_val = "Initiating recording..."
    trace_path_display_val = _last_manual_trace_path or "No trace recorded yet."
    start_btn_interactive_val = False 
    stop_btn_interactive_val = False
    _log_to_q("Attempting to start input tracking...")

    try:
        _log_to_q("Ensuring browser session...")
        browser, context = await ensure_browser_session(force_new_context_if_existing=False)

        if not browser or not context: # context here is the local one from ensure_browser_session
            status_update_val = "Failed to ensure browser session for recording."
            _log_to_q(status_update_val, is_error=True)
            return (
                gr.update(value=status_update_val),
                gr.update(interactive=True), # Allow retry
                gr.update(interactive=False),
                gr.update(value=trace_path_display_val),
            )
        
        _ui_global_browser_context = context # Ensure global is set with the successfully obtained context
        _log_to_q("Browser session ensured.")

        if _global_input_tracking_active:
            status_update_val = "Input tracking is already active."
            _log_to_q(status_update_val)
            start_btn_interactive_val = False
            stop_btn_interactive_val = True
            trace_path_display_val = "Recording... (Path will be shown on stop)"
        else:
            if not os.path.exists(MANUAL_TRACES_DIR):
                os.makedirs(MANUAL_TRACES_DIR, exist_ok=True)
                _log_to_q(f"Created recordings directory: {MANUAL_TRACES_DIR}")
            
            _log_to_q(f"Calling start_input_tracking() on context id: {id(_ui_global_browser_context)}...")
            await _ui_global_browser_context.start_input_tracking(event_log_queue=RECORDER_EVENT_LOG_Q)
            # Recorder itself will put "Recording started." message in the queue now.
            
            _global_input_tracking_active = True
            status_update_val = "Input tracking started. See logs for event details."
            # _log_to_q is handled by Recorder: ("Recording started.")
            trace_path_display_val = "Recording... (Path will be shown on stop)"
            start_btn_interactive_val = False
            stop_btn_interactive_val = True
            
    except Exception as e:
        status_update_val = f"Error starting input tracking: {str(e)}"
        _log_to_q(f"Exception during start_input_tracking_with_context: {e}", is_error=True)
        start_btn_interactive_val = True 
        stop_btn_interactive_val = False
        _global_input_tracking_active = False
    
    return (
        gr.update(value=status_update_val),
        gr.update(interactive=start_btn_interactive_val),
        gr.update(interactive=stop_btn_interactive_val),
        gr.update(value=trace_path_display_val),
    )

# Refactored to be a regular async function, sends logs to RECORDER_EVENT_LOG_Q
async def stop_input_tracking_with_context() -> Tuple[Any, ...]:
    global _ui_global_browser_context
    global _global_input_tracking_active, _last_manual_trace_path, RECORDER_EVENT_LOG_Q

    def _log_to_q(msg: str, is_error: bool = False):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        formatted_msg = f"[{timestamp}] {msg}"
        if is_error: logger.error(msg, exc_info=True if "exception" in msg.lower() or "error" in msg.lower() else False)
        else: logger.info(msg)
        try:
            RECORDER_EVENT_LOG_Q.put_nowait(formatted_msg)
        except asyncio.QueueFull:
            logger.warning(f"RECORDER_EVENT_LOG_Q full. Dropped: {formatted_msg}")

    status_message_val = "Initiating stop sequence..."
    filepath_update_val = _last_manual_trace_path
    trace_info_update_val = {"message": "No trace recorded or tracking not active."}
    start_btn_interactive_val = False 
    stop_btn_interactive_val = False 

    if _last_manual_trace_path:
        try:
            trace_info_update_val = user_input_functions.get_file_info(_last_manual_trace_path)
        except Exception as e_info_initial:
            trace_info_update_val = {"error": f"Could not load info for last trace: {str(e_info_initial)}"}
            _log_to_q(f"Error loading initial trace info: {e_info_initial}", is_error=True)
    
    _log_to_q("Attempting to stop input tracking...")

    if not _ui_global_browser_context or not _global_input_tracking_active:
        status_message_val = "Input tracking not active or browser context not available."
        _log_to_q(status_message_val, is_error=True)
        start_btn_interactive_val = True 
        stop_btn_interactive_val = False 
        return (
            gr.update(value=status_message_val), 
            gr.update(interactive=start_btn_interactive_val), 
            gr.update(interactive=stop_btn_interactive_val), 
            gr.update(value=filepath_update_val),
            gr.update(value=trace_info_update_val) 
        )
    
    try:
        _log_to_q("Calling stop_input_tracking() on context...")
        filepath = await _ui_global_browser_context.stop_input_tracking()
        # Recorder will put "Recording stopped." into queue.
        _global_input_tracking_active = False 

        if filepath:
            _last_manual_trace_path = filepath 
            filepath_update_val = filepath
            status_message_val = f"Input tracking stopped. Trace saved to: {filepath}"
            _log_to_q(f"Trace saved: {filepath}")
            try:
                trace_info_update_val = user_input_functions.get_file_info(filepath)
                _log_to_q(f"Successfully loaded info for new trace: {filepath}")
            except Exception as e_info:
                _log_to_q(f"Error getting trace info for display: {e_info}", is_error=True)
                trace_info_update_val = {"error": f"Could not load trace info: {str(e_info)}"}
        else:
            status_message_val = "Input tracking stopped. No new events were recorded to save."
            _log_to_q(status_message_val) # Also log this to queue
            if _last_manual_trace_path:
                 try:
                    trace_info_update_val = user_input_functions.get_file_info(_last_manual_trace_path)
                 except Exception as e_info_display_else:
                    _log_to_q(f"Error getting trace info (no new file path): {e_info_display_else}", is_error=True)
                    trace_info_update_val = {"error": f"Could not load trace info: {str(e_info_display_else)}"}
            else:
                 trace_info_update_val = {"message": "No trace file was saved in this or previous sessions."}
        
        start_btn_interactive_val = True
        stop_btn_interactive_val = False

    except Exception as e:
        status_message_val = f"Error stopping input tracking: {str(e)}"
        _log_to_q(f"Exception during stop_input_tracking_with_context: {e}", is_error=True)
        start_btn_interactive_val = not _global_input_tracking_active 
        stop_btn_interactive_val = _global_input_tracking_active    
        # trace_info_update_val remains as it was, or updated with error if that part failed
        if "error" not in trace_info_update_val and e: # Add general error if not already specific
            trace_info_update_val = {"error": f"Error stopping tracking: {str(e)}"}

    return (
        gr.update(value=status_message_val), 
        gr.update(interactive=start_btn_interactive_val), 
        gr.update(interactive=stop_btn_interactive_val), 
        gr.update(value=filepath_update_val),
        gr.update(value=trace_info_update_val)
    )

async def stream_replay_ui(
    trace_path: str, 
    speed: float, 
    override_files_temp_list: Optional[List[Any]],
    request: gr.Request
) -> AsyncGenerator[str, None]:
    print("[WEBUI stream_replay_ui] Entered function.", flush=True)
    global _ui_global_browser, _ui_global_browser_context, logger, manager_log_q
    
    override_files_paths: List[str] = []
    print(f"[WEBUI stream_replay_ui] trace_path: {trace_path}, speed: {speed}, override_files_temp_list: {override_files_temp_list}", flush=True)
    if override_files_temp_list:
        for temp_file in override_files_temp_list:
            if hasattr(temp_file, 'name') and isinstance(temp_file.name, str):
                override_files_paths.append(temp_file.name)
            elif isinstance(temp_file, str):
                override_files_paths.append(temp_file)
            else:
                logger.warning(f"stream_replay_ui: Skipping unexpected item type {type(temp_file)} in override_files_temp_list")
    print(f"[WEBUI stream_replay_ui] Processed override_files_paths: {override_files_paths}", flush=True)

    log_buffer = ""
    def _accumulate_log(new_text: str) -> str:
        nonlocal log_buffer
        if log_buffer and not log_buffer.endswith("\n"):
            log_buffer += "\n"
        log_buffer += new_text
        return log_buffer

    print("[WEBUI stream_replay_ui] Right before first try...finally block.", flush=True)
    try:
        log_buffer = _accumulate_log(f"Initiating replay for: {Path(trace_path).name}")
        yield log_buffer
    except Exception as e_first_yield:
        print(f"[WEBUI stream_replay_ui] ERROR during/after first yield (before session): {e_first_yield}", flush=True)
        log_buffer = _accumulate_log(f"Error before starting: {e_first_yield}")
        yield log_buffer
        return 
    finally:
        print("[WEBUI stream_replay_ui] After first yield attempt (inside finally).", flush=True)

    logger.info(f"stream_replay_ui: Replay for '{trace_path}'. Ensuring browser session...")
    print(f"[WEBUI stream_replay_ui] Ensuring browser session...", flush=True)
    live_browser, live_context = await ensure_browser_session()
    logger.debug(f"stream_replay_ui: After ensure_browser_session - live_browser: {type(live_browser)}, live_context: {type(live_context)}")
    print(f"[WEBUI stream_replay_ui] ensure_browser_session returned: browser={type(live_browser)}, context={type(live_context)}", flush=True)

    if not live_browser or not live_context:
        err_msg = "Error: Failed to ensure browser session for replay. Check logs from ensure_browser_session."
        logger.error(err_msg)
        log_buffer = _accumulate_log(f"SESSION ERROR: {err_msg}")
        yield log_buffer
        print(f"[WEBUI stream_replay_ui] Yielded SESSION ERROR. Returning.", flush=True)
        return
    
    log_buffer = _accumulate_log("🔌 Browser session ensured. Starting replay thread...")
    yield log_buffer
    print(f"[WEBUI stream_replay_ui] Yielded 'Browser session ensured'.", flush=True)

    ui_async_q: asyncio.Queue[str] = asyncio.Queue()
    done_event = threading.Event()
    main_loop = asyncio.get_running_loop()
    print(f"[WEBUI stream_replay_ui] Initialized ui_async_q, done_event, and got main_loop: {main_loop}.", flush=True)

    cdp_url_for_thread = None
    if live_browser and hasattr(live_browser, 'config') and live_browser.config and hasattr(live_browser.config, 'cdp_url') and live_browser.config.cdp_url:
        cdp_url_for_thread = live_browser.config.cdp_url
        print(f"[WEBUI stream_replay_ui] Retrieved CDP URL for thread: {cdp_url_for_thread}", flush=True)
    else:
        print("[WEBUI stream_replay_ui] ERROR: Could not retrieve cdp_url from live_browser.config.cdp_url.", flush=True)

    if not cdp_url_for_thread:
        err_msg_cdp = "Error: CDP URL for thread is not available. Cannot connect worker thread to browser."
        logger.error(err_msg_cdp)
        log_buffer = _accumulate_log(f"CDP ERROR: {err_msg_cdp}")
        yield log_buffer
        print(f"[WEBUI stream_replay_ui] Yielded CDP ERROR. Returning.", flush=True)
        return

    logger.debug(f"stream_replay_ui: Calling start_replay_sync_api_in_thread for {trace_path}")    
    print(f"[WEBUI stream_replay_ui] Calling start_replay_sync_api_in_thread with trace_path={trace_path}, speed={speed}, files={override_files_paths}", flush=True)
    done_event = start_replay_sync_api_in_thread(
        trace_path, 
        speed, 
        override_files_paths, 
        ui_async_q, 
        main_loop,
        cdp_url_for_thread
    )
    print(f"[WEBUI stream_replay_ui] start_replay_sync_api_in_thread call completed. Returned done_event: {done_event}", flush=True)
    log_buffer = _accumulate_log("--- Replay thread started ---")
    yield log_buffer
    print(f"[WEBUI stream_replay_ui] Yielded 'Replay thread started'. Beginning monitor loop.", flush=True)

    loop_count = 0
    while not done_event.is_set() or not ui_async_q.empty():
        loop_count += 1
        try:
            while True: 
                line = ui_async_q.get_nowait()
                log_buffer = _accumulate_log(line)
                yield log_buffer
                ui_async_q.task_done()
        except asyncio.QueueEmpty:
            pass
        
        yield log_buffer 
        await asyncio.sleep(0.25)

    logger.info("stream_replay_ui: Replay thread finished. Final log flush.")
    print(f"[WEBUI stream_replay_ui] Monitor loop exited. Final log flush. done_event.is_set(): {done_event.is_set()}, ui_async_q.empty(): {ui_async_q.empty()}", flush=True)
    while not ui_async_q.empty():
        try:
            line = ui_async_q.get_nowait()
            log_buffer = _accumulate_log(line)
            yield log_buffer
            ui_async_q.task_done()
        except asyncio.QueueEmpty:
            print(f"[WEBUI stream_replay_ui] Final flush: ui_async_q is empty.", flush=True)
            break
    
    log_buffer = _accumulate_log("--- Replay completed✨ ---")
    yield log_buffer
    logger.info("stream_replay_ui: Streaming finished.")
    print(f"[WEBUI stream_replay_ui] Yielded final 'Replay process fully completed'. Exiting function.", flush=True)

# --- NEW: Recorder Log Streaming Function ---
async def _stream_recorder_log() -> AsyncGenerator[str, None]:
    """Continuously streams logs from RECORDER_EVENT_LOG_Q to a Gradio Textbox."""
    global RECORDER_EVENT_LOG_Q
    log_accumulator = ""
    while True:
        try:
            new_messages = []
            # queue_was_empty_at_start = RECORDER_EVENT_LOG_Q.empty() # Optional: for more refined debug logging
            while not RECORDER_EVENT_LOG_Q.empty():
                try:
                    msg = RECORDER_EVENT_LOG_Q.get_nowait()
                    new_messages.append(msg)
                    RECORDER_EVENT_LOG_Q.task_done()
                except asyncio.QueueEmpty:
                    break
            
            if new_messages:
                logger.debug(f"[_stream_recorder_log]: Pulled {len(new_messages)} new messages from RECORDER_EVENT_LOG_Q: {new_messages}")
                for msg_line in new_messages:
                    if log_accumulator and not log_accumulator.endswith("\n"):
                        log_accumulator += "\n"
                    log_accumulator += msg_line
                yield log_accumulator.strip()
            else:
                # logger.debug(f"[_stream_recorder_log]: No new messages in RECORDER_EVENT_LOG_Q this cycle. Accumulator: '{log_accumulator[:50]}...'") # Optional debug
                yield log_accumulator.strip()

        except Exception as e_stream_rec_log:
            logger.error(f"Error in _stream_recorder_log: {e_stream_rec_log}", exc_info=True)
            err_msg_for_ui = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ⚠️ Logger stream error: {e_stream_rec_log}"
            if log_accumulator and not log_accumulator.endswith("\n"):
                log_accumulator += "\n"
            log_accumulator += err_msg_for_ui
            yield log_accumulator.strip()
        
        await asyncio.sleep(0.3)

# --- Global UI Definitions ---
css = """ 
    /* Your CSS styles here, e.g.: */
    .gradio-container { width: 80% !important; max-width: 90% !important; margin-left: auto !important; margin-right: auto !important; } 
""" 

# Define the theme map globally
theme_map = {
    "Default": Default(),
    "Soft": Soft(),
    "Citrus": Citrus(),
    "Monochrome": Monochrome(),
    "Glass": Glass(),
    "Ocean": Ocean(),
    "Origin": Base() 
} 
# --- End Global UI Definitions ---

# --- Main UI ---
def create_ui(theme_name="Citrus"):

    with gr.Blocks(theme=theme_map.get(theme_name, Default()), css=css) as demo: # Added .get for safety
        # ... (Define trace_file_path Textbox for general use if needed)

        with gr.Tabs() as tabs:
            # ... (Other Tabs: Settings, Prompt Agent, Record, etc.) ...

            # New: Record tab
            with gr.TabItem("🛑 Record", id=9):
                
                gr.Markdown("### 🛑 Record User Input")
                with gr.Row():
                    with gr.Column(scale=2):
                        input_track_status = gr.Textbox(
                            label="Recording Status",
                            value="Recording not started. Browser will be launched or reused on first record attempt.",
                            interactive=False,
                            lines=2 # Allow a bit more space for messages
                        )
                    with gr.Column(scale=1):
                        input_track_start_btn = gr.Button("▶️ Start Recording", variant="primary")
                        input_track_stop_btn = gr.Button("⏹️ Stop Recording", variant="stop", interactive=False)

                gr.Markdown("### 📜 Last Recorded Trace Info")
                recorded_trace_info_display = gr.JSON(
                    label="Last Recorded Trace Details",
                    value={"message": "No trace recorded in this session yet."}
                )
                
                # Hidden textbox to store/pass the path of the last recorded trace
                last_recorded_trace_path_hidden = gr.Textbox(visible=False, label="Last Recorded Trace Path Hidden")

                # New Textbox for Record Status Logs
                record_status_logs_output = gr.Textbox(
                    label="Record Status Logs", 
                    interactive=False, 
                    lines=10, 
                    max_lines=20, 
                    autoscroll=True,
                    show_label=True
                )

                input_track_start_btn.click(
                    fn=start_input_tracking_with_context,
                    inputs=[],
                    outputs=[
                        input_track_status, 
                        input_track_start_btn, 
                        input_track_stop_btn, 
                        last_recorded_trace_path_hidden
                    ]
                )
                
                input_track_stop_btn.click(
                    fn=stop_input_tracking_with_context,
                    inputs=[],
                    outputs=[
                        input_track_status, 
                        input_track_start_btn, 
                        input_track_stop_btn, 
                        last_recorded_trace_path_hidden, 
                        recorded_trace_info_display
                    ]
                )

            with gr.TabItem("▶️ Replay", id=10):
                gr.Markdown("### 📂 Input Trace Files")
                refresh_traces_btn = gr.Button("🔄 Refresh Trace Files", variant="secondary")
                trace_files_list = gr.Dataframe(
                    headers=["Name", "Created", "Size", "Events"],
                    label="Available Traces for Replay", interactive=True, wrap=True
                )
                override_upload_files_component = gr.File(
                    label="Override files for selected trace", file_count="multiple", 
                    interactive=True, visible=False, value=None
                )
                with gr.Row():
                    trace_info_display_replay = gr.JSON(
                        label="Trace File Info",
                        value={"message": "Select a trace file above to view details"}
                    )
                    with gr.Column(): # Use gr.Column for trace_actions
                        trace_replay_btn = gr.Button("▶️ Replay Trace", variant="primary")
                        replay_speed_input = gr.Number(label="Replay Speed", value=1.0, minimum=0.1, interactive=True)
                
                with gr.Row(): 
                    replay_status_output = gr.Textbox(
                        label="Replay Status Logs", interactive=False, lines=20, max_lines=40, 
                        show_label=True, autoscroll=True, elem_id="replay_status_logs_textbox"
                    )

                selected_trace_path_for_replay = gr.Textbox(label="Selected Trace Path", interactive=False, visible=False)
                trace_file_details_state_replay = gr.State([]) # Keep if used by trace_files_list.select

                # --- Event Handlers for Replay Tab ---
                def handle_trace_selection_for_uploads(df_data: pd.DataFrame, evt: gr.SelectData):
                    if evt.selected and evt.index is not None and len(evt.index) > 0:
                        selected_row_index = evt.index[0]
                        if "Name" in df_data.columns and 0 <= selected_row_index < len(df_data):
                            file_name = df_data.iloc[selected_row_index]["Name"]
                            trace_path = str(Path(MANUAL_TRACES_DIR) / file_name)
                            if trace_path and Path(trace_path).exists():
                                required_files = get_upload_file_names_from_trace(str(trace_path))
                                if required_files:
                                    label_text = f"Override/Provide for: {Path(trace_path).name} (Needs: {', '.join(required_files)})"
                                    return gr.update(label=label_text, visible=True, value=None, interactive=True), str(trace_path)
                                return gr.update(label="No file uploads in trace", visible=True, value=None, interactive=False), str(trace_path)
                    return gr.update(visible=False, value=None), ""

                trace_files_list.select(
                    fn=handle_trace_selection_for_uploads,
                    inputs=[trace_files_list],
                    outputs=[override_upload_files_component, selected_trace_path_for_replay]
                )
                
                def update_trace_info_for_replay_tab(local_trace_file_path: str):
                    if not local_trace_file_path: return {"message": "No trace selected"}
                    return user_input_functions.get_file_info(local_trace_file_path) 
                
                selected_trace_path_for_replay.change(
                    fn=update_trace_info_for_replay_tab,
                    inputs=[selected_trace_path_for_replay],
                    outputs=[trace_info_display_replay]
                )
                
                refresh_traces_btn.click( # Assuming refresh_traces is defined globally or accessible
                    fn=refresh_traces, 
                    inputs=[],
                    outputs=[trace_files_list, trace_file_details_state_replay] 
                )

                # MODIFIED: trace_replay_btn click handler
                # It now directly calls the imported replay_log_streamer_snippet.
                # replay_log_streamer_snippet in the manager will be responsible for calling ensure_browser_session via imported getters.
                trace_replay_btn.click(
                    fn=stream_replay_ui, # New async generator UI callback
                    inputs=[
                        selected_trace_path_for_replay, 
                        replay_speed_input, 
                        override_upload_files_component
                    ],
                    outputs=[replay_status_output],
                    queue=True,
                    concurrency_limit=None
                )

                gr.Markdown("--- DEBUG: Minimal Stream Test ---")
                with gr.Row():
                    minimal_test_btn = gr.Button("▶️ Run Minimal Stream Test")
                    minimal_test_output = gr.Textbox(label="Minimal Test Output", interactive=False)
                
                async def minimal_stream_test_fn() -> AsyncGenerator[str, None]:
                    print("[MINIMAL_TEST] Entered minimal_stream_test_fn")
                    yield "Minimal Test: Line 1"
                    print("[MINIMAL_TEST] After yield 1")
                    await asyncio.sleep(1) # Simulate some async work
                    print("[MINIMAL_TEST] After sleep 1")
                    yield "Minimal Test: Line 1\nMinimal Test: Line 2"
                    print("[MINIMAL_TEST] After yield 2")
                    await asyncio.sleep(1)
                    print("[MINIMAL_TEST] After sleep 2")
                    yield "Minimal Test: Line 1\nMinimal Test: Line 2\nMinimal Test: Line 3 (Done)"
                    print("[MINIMAL_TEST] Minimal test finished")

                minimal_test_btn.click(
                    fn=minimal_stream_test_fn,
                    outputs=minimal_test_output,
                    queue=True,
                    concurrency_limit=None # behaves like queue=False performance
                )
        
        # --- Add demo.load hook for recorder log streaming ---
        demo.load(_stream_recorder_log, inputs=None, outputs=[record_status_logs_output])

    return demo
# --- End: Main UI ---

# --- Main entry ----
if __name__ == "__main__":
    # Ensure MANUAL_TRACES_DIR exists at startup (MANUAL_TRACES_DIR should be defined globally)
    # demo variable must be defined before demo.launch(), typically demo = create_ui()
    demo = create_ui(theme_name="Citrus") # Assuming create_ui() is defined above and returns the demo instance

    if not Path(MANUAL_TRACES_DIR).exists(): # Check before creating
        Path(MANUAL_TRACES_DIR).mkdir(parents=True, exist_ok=True)
        logger.info(f"Created MANUAL_TRACES_DIR at: {Path(MANUAL_TRACES_DIR).resolve()}")
    else:
        logger.info(f"MANUAL_TRACES_DIR exists at: {Path(MANUAL_TRACES_DIR).resolve()}")

    logger.info(f"Launching Gradio demo. Access at http://127.0.0.1:7860")
    demo.launch(server_name="127.0.0.1", server_port=7860, debug=True, allowed_paths=[MANUAL_TRACES_DIR])

_browser_init_lock = asyncio.Lock() # Add lock for ensure_browser_session