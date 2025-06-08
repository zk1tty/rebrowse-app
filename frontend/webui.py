import pdb
import logging
import os
import gradio as gr
import queue 
import threading 
import time 
import asyncio 
import tempfile
from typing import Optional, List, Dict, Any, Union, Callable, Tuple, AsyncGenerator, TextIO
from pathlib import Path
from datetime import datetime
from gradio.themes import Default, Soft, Glass, Monochrome, Ocean, Origin, Base, Citrus
import pandas as pd
from playwright.async_api import BrowserContext as PlaywrightBrowserContextType, Browser as PlaywrightBrowser
from playwright.async_api import Browser # For isinstance check
# from playwright.async_api import async_playwright # Ensure this is removed if only for old recording logic
import json # Add json import

from dotenv import load_dotenv
load_dotenv()

# Import task templates
from task_templates import TASK_TEMPLATES

# --- Project-specific global imports needed by replay logic ---
from src.browser.custom_browser import CustomBrowser
from src.browser.custom_context import CustomBrowserContext
from src.browser.custom_context_config import CustomBrowserContextConfig as AppCustomBrowserContextConfig
from browser_use.browser.browser import BrowserConfig
from src.utils.trace_utils import get_upload_file_names_from_trace
from src.utils import user_input_functions
from browser_use.browser.context import BrowserContextWindowSize

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

# --- Global Queues and Pipe Paths ---
RECORDER_EVENT_LOG_Q: asyncio.Queue[str] = asyncio.Queue() # This queue might become less central for raw recording
HOST_STATUS_LOG_Q: asyncio.Queue[str] = asyncio.Queue() # This queue is now KEY for the new recorder
HOST_STATUS_PIPE_PATH = "/tmp/rebrowse_host_status.pipe"
# --- NEW: Command Pipe Paths to sync with host.py ---
COMMAND_PIPE_PATH = "/tmp/rebrowse_ui_command.pipe"
RESPONSE_PIPE_PATH = "/tmp/rebrowse_ui_command_response.pipe"

MANUAL_TRACES_DIR = "./tmp/input_tracking"

# --- NEW Global State for "Pipe-to-File" Recording ---
_RECORDING_ACTIVE: bool = False
_RECORDING_FILE_HANDLE: Optional[TextIO] = None
_RECORDING_ASYNC_TASK: Optional[asyncio.Task] = None
_CURRENT_RECORDING_FILE_PATH: Optional[str] = None # To store the path of the current recording
demo: Optional[gr.Blocks] = None

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
    global _ui_global_browser, _ui_global_browser_context, logger, _browser_init_lock
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
async def start_recording_logic():
    global _RECORDING_ACTIVE, _RECORDING_FILE_HANDLE, _RECORDING_ASYNC_TASK, _CURRENT_RECORDING_FILE_PATH
    global RECORDER_EVENT_LOG_Q, logger, MANUAL_TRACES_DIR

    # Log to RECORDER_EVENT_LOG_Q for the Gradio UI "Record Status Logs" textbox
    # This queue is separate from HOST_STATUS_LOG_Q used by the pipe writer
    def _log_to_ui_q(msg: str, is_error: bool = False):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        formatted_msg = f"[{timestamp}] [WebUI-Record] {msg}"
        if is_error: logger.error(msg)
        else: logger.info(msg)
        try:
            RECORDER_EVENT_LOG_Q.put_nowait(formatted_msg)
        except asyncio.QueueFull:
            logger.warning(f"RECORDER_EVENT_LOG_Q full for UI. Dropped: {formatted_msg}")

    _log_to_ui_q("Attempting to start pipe-to-file recording...")

    if _RECORDING_ACTIVE:
        _log_to_ui_q("Pipe-to-file recording is already active.")
        return

    try:
        if not os.path.exists(MANUAL_TRACES_DIR):
            os.makedirs(MANUAL_TRACES_DIR, exist_ok=True)
            _log_to_ui_q(f"Created recordings directory: {MANUAL_TRACES_DIR}")

        # Generate filename (e.g., YYYYMMDD_HHMMSS_pipe_events.jsonl)
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_trace_filename = f"{timestamp_str}_pipe_events.jsonl" # Using .jsonl as it's line-delimited JSON
        _CURRENT_RECORDING_FILE_PATH = str(Path(MANUAL_TRACES_DIR) / new_trace_filename)
        
        _log_to_ui_q(f"Opening trace file for writing: {_CURRENT_RECORDING_FILE_PATH}")
        _RECORDING_FILE_HANDLE = open(_CURRENT_RECORDING_FILE_PATH, "w", encoding="utf-8")
        
        _RECORDING_ACTIVE = True
        
        # Start the background task to write from HOST_STATUS_LOG_Q to the file
        if _RECORDING_ASYNC_TASK and not _RECORDING_ASYNC_TASK.done():
            _log_to_ui_q("Warning: Previous recording task was still present. Cancelling it.")
            _RECORDING_ASYNC_TASK.cancel()
            try: await _RECORDING_ASYNC_TASK # Allow cancellation to process
            except asyncio.CancelledError:
                 _log_to_ui_q("Previous recording task cancelled.")
        
        _RECORDING_ASYNC_TASK = asyncio.create_task(_pipe_to_file_writer())
        _log_to_ui_q(f"Pipe-to-file recording started. Saving to: {_CURRENT_RECORDING_FILE_PATH}")
            
    except Exception as e:
        _log_to_ui_q(f"Exception starting recording: {e}", is_error=True)
        logger.error(f"Exception in start_recording_logic: {e}", exc_info=True)
        _RECORDING_ACTIVE = False # Ensure state is correct
        if _RECORDING_FILE_HANDLE and not _RECORDING_FILE_HANDLE.closed:
            _RECORDING_FILE_HANDLE.close()
        _RECORDING_FILE_HANDLE = None
        _CURRENT_RECORDING_FILE_PATH = None
        if _RECORDING_ASYNC_TASK and not _RECORDING_ASYNC_TASK.done():
            _RECORDING_ASYNC_TASK.cancel()
            # No await here as we are in an exception handler already

# Refactored to be a regular async function, sends logs to RECORDER_EVENT_LOG_Q
async def stop_recording_logic():
    global _RECORDING_ACTIVE, _RECORDING_FILE_HANDLE, _RECORDING_ASYNC_TASK, _CURRENT_RECORDING_FILE_PATH
    global _last_manual_trace_path, RECORDER_EVENT_LOG_Q, logger

    # Log to RECORDER_EVENT_LOG_Q for the Gradio UI "Record Status Logs" textbox
    # TODO: wtf is _log_to_ui_q? Same logs with pipe_trace file?
    def _log_to_ui_q(msg: str, is_error: bool = False):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        formatted_msg = f"[{timestamp}] [WebUI-Record] {msg}"
        if is_error: logger.error(msg)
        else: logger.info(msg)
        try:
            RECORDER_EVENT_LOG_Q.put_nowait(formatted_msg)
        except asyncio.QueueFull:
            logger.warning(f"RECORDER_EVENT_LOG_Q full for UI. Dropped: {formatted_msg}")

    _log_to_ui_q("Attempting to stop pipe-to-file recording...")

    if not _RECORDING_ACTIVE and not _RECORDING_FILE_HANDLE:
        _log_to_ui_q("Pipe-to-file recording was not active.")
        return
    
    try:
        _RECORDING_ACTIVE = False # Signal the writer task to stop
        _log_to_ui_q("Recording flag set to inactive.")

        if _RECORDING_ASYNC_TASK and not _RECORDING_ASYNC_TASK.done():
            _log_to_ui_q("Cancelling pipe-to-file writer task...")
            _RECORDING_ASYNC_TASK.cancel()
            try:
                await _RECORDING_ASYNC_TASK
                _log_to_ui_q("Writer task finished after cancellation.")
            except asyncio.CancelledError:
                _log_to_ui_q("Writer task successfully cancelled.")
            except Exception as e_task_await:
                _log_to_ui_q(f"Error awaiting writer task: {e_task_await}", is_error=True)
                logger.error(f"Error awaiting _RECORDING_ASYNC_TASK: {e_task_await}", exc_info=True)
        _RECORDING_ASYNC_TASK = None

        if _RECORDING_FILE_HANDLE and not _RECORDING_FILE_HANDLE.closed:
            # NEW: Before closing, flush any remaining messages that might still be in HOST_STATUS_LOG_Q
            try:
                flushed_count = 0
                while not HOST_STATUS_LOG_Q.empty():
                    try:
                        pending_line = HOST_STATUS_LOG_Q.get_nowait()
                        _RECORDING_FILE_HANDLE.write(pending_line + "\n")
                        flushed_count += 1
                        HOST_STATUS_LOG_Q.task_done()
                    except asyncio.QueueEmpty:
                        break
                if flushed_count:
                    _RECORDING_FILE_HANDLE.flush()
                    logger.info(f"[stop_recording_logic] Flushed {flushed_count} remaining lines from HOST_STATUS_LOG_Q before closing file.")
            except Exception as e_flush:
                logger.error(f"[stop_recording_logic] Error flushing remaining queue messages: {e_flush}", exc_info=True)

            _log_to_ui_q(f"Closing trace file: {_CURRENT_RECORDING_FILE_PATH}")
            _RECORDING_FILE_HANDLE.flush()
            _RECORDING_FILE_HANDLE.close()
            _log_to_ui_q("Trace file closed.")
        _RECORDING_FILE_HANDLE = None

        if _CURRENT_RECORDING_FILE_PATH:
            _last_manual_trace_path = _CURRENT_RECORDING_FILE_PATH # Update for next UI cycle
            _log_to_ui_q(f"Trace saved: {_last_manual_trace_path}")
            try:
                info = user_input_functions.get_file_info(_last_manual_trace_path)
                await recorded_trace_info_display.update(info)   # push to UI once
            except Exception: pass
        else:
            _log_to_ui_q("Recording stopped, but no current file path was set.", is_error=True)

        _CURRENT_RECORDING_FILE_PATH = None # Clear for next recording

    except Exception as e:
        _log_to_ui_q(f"Error stopping recording: {e}", is_error=True)
        logger.error(f"Exception in stop_recording_logic: {e}", exc_info=True)
        # Try to revert to a safe state
        _RECORDING_ACTIVE = False 

# --- Replay UI ---
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

############### POLLING LOG SNAPSHOTS INSTEAD OF INFINITE STREAMS ###############

# Running infinite async generators via .load() blocks subsequent UI events because
# the front-end keeps them in a perpetual "running" state.  Instead we expose
# *snapshot* functions that return the latest accumulated log text and let
# Gradio poll them every few hundred milliseconds.

_recorder_log_accum = ""
def poll_recorder_log() -> str:  # called frequently by gr.Timer.tick()
    global _recorder_log_accum, RECORDER_EVENT_LOG_Q
    new_messages = []
    while not RECORDER_EVENT_LOG_Q.empty():
        try:
            msg = RECORDER_EVENT_LOG_Q.get_nowait()
            new_messages.append(msg)
            logger.debug(f"[poll_recorder_log] new_messages: {new_messages}")
            RECORDER_EVENT_LOG_Q.task_done()
        except asyncio.QueueEmpty:
            break
    if new_messages:
        if _recorder_log_accum and not _recorder_log_accum.endswith("\n"):
            _recorder_log_accum += "\n"
        _recorder_log_accum += "\n".join(new_messages)
    return _recorder_log_accum.strip()

_host_log_accum = "[WebUI] Waiting for Native Host logs..."
def poll_host_status_log() -> str: # called frequently by gr.Timer.tick()
    global _host_log_accum, HOST_STATUS_LOG_Q
    new_messages = []
    while not HOST_STATUS_LOG_Q.empty():
        try:
            msg = HOST_STATUS_LOG_Q.get_nowait()
            new_messages.append(msg)
            logger.debug(f"[poll_host_status_log] new_messages: {new_messages}")
            HOST_STATUS_LOG_Q.task_done()
        except asyncio.QueueEmpty:
            break
    if new_messages:
        if _host_log_accum and not _host_log_accum.endswith("\n"):
            _host_log_accum += "\n"
        _host_log_accum += "\n".join(new_messages)
    return _host_log_accum.strip()

###############################################################################

async def _read_host_pipe_task():
    """Creates and reads from a named pipe, putting messages into HOST_STATUS_LOG_Q."""
    global HOST_STATUS_LOG_Q, HOST_STATUS_PIPE_PATH, logger
    
    logger.info(f"[_read_host_pipe_task] Starting. Pipe path: {HOST_STATUS_PIPE_PATH}")

    if os.path.exists(HOST_STATUS_PIPE_PATH):
        try:
            os.remove(HOST_STATUS_PIPE_PATH)
            logger.info(f"[_read_host_pipe_task] Removed existing host status pipe: {HOST_STATUS_PIPE_PATH}")
        except OSError as e:
            logger.error(f"[_read_host_pipe_task] Error removing existing host status pipe {HOST_STATUS_PIPE_PATH}: {e}")
            # Continue to try and create it anyway

    try:
        os.mkfifo(HOST_STATUS_PIPE_PATH)
        logger.info(f"[_read_host_pipe_task] Created host status pipe: {HOST_STATUS_PIPE_PATH}")
        await HOST_STATUS_LOG_Q.put(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [WebUI] Named pipe {HOST_STATUS_PIPE_PATH} created successfully.")
    except OSError as e:
        logger.error(f"[_read_host_pipe_task] Failed to create host status pipe {HOST_STATUS_PIPE_PATH}: {e}. Host status will not be available.", exc_info=True)
        await HOST_STATUS_LOG_Q.put(f"CRITICAL ERROR: [WebUI] Could not create named pipe {HOST_STATUS_PIPE_PATH}. Host logs disabled.")
        return

    logger.info(f"[_read_host_pipe_task] Listener loop started for {HOST_STATUS_PIPE_PATH}")
    while True:
        pipe_file = None # Ensure pipe_file is reset for each attempt to open
        try:
            logger.info(f"[_read_host_pipe_task] Attempting to open pipe for reading: {HOST_STATUS_PIPE_PATH} (this may block until writer connects)..." )
            pipe_file = open(HOST_STATUS_PIPE_PATH, 'r') # Blocking open
            logger.info(f"[_read_host_pipe_task] Pipe opened for reading: {HOST_STATUS_PIPE_PATH}")
            await HOST_STATUS_LOG_Q.put(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [WebUI] Pipe reader connected to {HOST_STATUS_PIPE_PATH}.")
            
            while True:
                # logger.debug(f"[_read_host_pipe_task] Waiting for line from pipe_file.readline()...")
                line = pipe_file.readline()
                # logger.debug(f"[_read_host_pipe_task] pipe_file.readline() returned: '{(line.strip() if line else "<EOF or empty line>")}'")
                if not line: 
                    logger.warning("[_read_host_pipe_task] Writer closed pipe or EOF detected. Re-opening pipe...")
                    await HOST_STATUS_LOG_Q.put(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [WebUI] Pipe writer disconnected. Attempting to reconnect...")
                    break # Break inner loop to reopen the pipe
                
                message = line.strip()
                if message: # Ensure not just an empty line
                    # logger.debug(f"[_read_host_pipe_task] Received from pipe: '{message}'")
                    await HOST_STATUS_LOG_Q.put(message) # Put the raw message from host.py
                    # logger.debug(f"[_read_host_pipe_task] Message '{message}' put to HOST_STATUS_LOG_Q.")
        except FileNotFoundError:
            logger.error(f"[_read_host_pipe_task] Pipe {HOST_STATUS_PIPE_PATH} not found. Recreating...", exc_info=False) # Less noisy for frequent checks
            await HOST_STATUS_LOG_Q.put(f"ERROR: [WebUI] Pipe {HOST_STATUS_PIPE_PATH} lost. Attempting to recreate.")
            if os.path.exists(HOST_STATUS_PIPE_PATH):
                try:
                    os.remove(HOST_STATUS_PIPE_PATH)
                except OSError as e_remove_fnf:
                    logger.error(f"[_read_host_pipe_task] Error removing existing pipe during FileNotFoundError handling: {e_remove_fnf}")
            try:
                os.mkfifo(HOST_STATUS_PIPE_PATH)
                logger.info(f"[_read_host_pipe_task] Recreated pipe {HOST_STATUS_PIPE_PATH} after FileNotFoundError.")
                await HOST_STATUS_LOG_Q.put(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [WebUI] Pipe {HOST_STATUS_PIPE_PATH} recreated.")
                await asyncio.sleep(1) # Brief pause before retrying open in the main loop
            except OSError as e_mkfifo_retry:
                logger.error(f"[_read_host_pipe_task] Failed to recreate pipe {HOST_STATUS_PIPE_PATH}: {e_mkfifo_retry}. Retrying outer loop in 10s.", exc_info=True)
                await HOST_STATUS_LOG_Q.put(f"CRITICAL ERROR: [WebUI] Failed to recreate pipe {HOST_STATUS_PIPE_PATH}. Retrying in 10s.")
                await asyncio.sleep(10) 
        except Exception as e_pipe_read_outer:
            logger.error(f"[_read_host_pipe_task] Unhandled error in pipe reading loop: {e_pipe_read_outer}", exc_info=True)
            await HOST_STATUS_LOG_Q.put(f"ERROR: [WebUI] Pipe reading loop encountered: {e_pipe_read_outer}. Retrying in 5s.")
            await asyncio.sleep(5) 
        finally:
            if pipe_file:
                try:
                    pipe_file.close()
                    logger.info(f"[_read_host_pipe_task] Closed pipe file handle for {HOST_STATUS_PIPE_PATH} in finally block.")
                except Exception as e_close_finally:
                    logger.error(f"[_read_host_pipe_task] Error closing pipe in finally: {e_close_finally}")
        
        # If loop broken due to readline EOF or other error causing pipe_file to close, 
        # this sleep prevents a tight loop if open() immediately fails again.
        await asyncio.sleep(1) # Wait a bit before retrying the main while True loop (re-opening pipe)


# --- Test function for demo.load ---
def _test_load_function():
    logging.getLogger(__name__).critical("[_test_load_function] syncTEST LOAD FUNCTION EXECUTED CRITICAL LOG AT VERY TOP OF LOAD")

async def _async_test_load_function():
    logging.getLogger(__name__).critical("[_async_test_load_function] ASYNC TEST LOAD FUNCTION EXECUTED CRITICAL LOG AT VERY TOP OF LOAD")
    await asyncio.sleep(0.1) # Minimal async work

# --- Global UI Definitions ---
css = """ 
    /* Your CSS styles here, e.g.: */
    .gradio-container { width: 80% !important; max-width: 90% !important; margin-left: auto !important; margin-right: auto !important; } 
""" 

# Define the theme map globally
theme_map = {
    "Default": Default(),
    "Soft": Soft(),
    "Citrus": Citrus(font=gr.themes.GoogleFont("Inter")),
    "Monochrome": Monochrome(),
    "Glass": Glass(),
    "Ocean": Ocean(),
    "Origin": Base() 
} 
# --- End Global UI Definitions ---

async def _write_to_response_pipe(response_data: dict):
    global RESPONSE_PIPE_PATH, logger
    try:
        json_response = json.dumps(response_data)
        logger.info(f"[_write_to_response_pipe] Attempting to open response pipe {RESPONSE_PIPE_PATH} for writing.")
        fd = os.open(RESPONSE_PIPE_PATH, os.O_WRONLY | os.O_NONBLOCK)
        with os.fdopen(fd, 'w') as pipe_writer:
            pipe_writer.write(json_response + '\n')
            pipe_writer.flush()
        logger.info(f"[_write_to_response_pipe] Successfully wrote to {RESPONSE_PIPE_PATH}: {json_response}")
    except FileNotFoundError:
        logger.error(f"[_write_to_response_pipe] ERROR: Response pipe {RESPONSE_PIPE_PATH} not found. Host.py might not be ready or pipe was removed.")
    except OSError as e:
        if e.errno == 6:
            logger.warning(f"[_write_to_response_pipe] Response pipe {RESPONSE_PIPE_PATH} has no reader. Host.py might not be listening.")
        else:
            logger.error(f"[_write_to_response_pipe] OSError writing to response pipe {RESPONSE_PIPE_PATH}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"[_write_to_response_pipe] Error writing to response pipe {RESPONSE_PIPE_PATH}: {e}", exc_info=True)

async def _process_command_from_pipe(command_str: str):
    global logger, _RECORDING_ACTIVE, _last_manual_trace_path, _record_log_stream_task, demo
    response_payload = {"status": "unknown_command", "command": command_str, "message": "Command not recognized by webui.py"}

    if command_str == "START_RECORDING":
        try:
            logger.info(f"[_process_command_from_pipe] received START from command pipe: {command_str}")
            
            await start_recording_logic()
            
            logger.info(f"[_process_command_from_pipe] _RECORDING_ACTIVE state: {_RECORDING_ACTIVE}")

            if _RECORDING_ACTIVE:
                response_payload = {"status": "recording_started", "command": command_str, "message": "Recording started successfully."}
        except Exception as e:
            logger.error(f"Error calling start_recording_logic from pipe: {e}", exc_info=True)
            response_payload = {"status": "error", "command": command_str, "message": f"Exception during start_recording: {str(e)}"}
    
    elif command_str == "STOP_RECORDING":
        try:
            logger.info(f"received STOP from command pipe: {command_str}")
            await stop_recording_logic()

            logger.info(f"[_process_command_from_pipe] LOG: Returned from stop_recording_logic. _RECORDING_ACTIVE state: {_RECORDING_ACTIVE}")
            
            if not _RECORDING_ACTIVE:
                response_payload = {
                    "status": "recording_stopped", 
                    "command": command_str, 
                    "message": "Recording stopped successfully via extension command.",
                    "filePath": _last_manual_trace_path 
                }
            else:
                response_payload = {"status": "error_stopping_recording", "command": command_str, "message": "Recording did not deactivate as expected. Check webui logs."}
        except Exception as e:
            logger.error(f"Error calling stop_recording_logic from pipe: {e}", exc_info=True)
            response_payload = {"status": "error", "command": command_str, "message": f"Exception during stop_recording: {str(e)}"}
    
    response_payload["source"] = "extension_command_response"
    await _write_to_response_pipe(response_payload)
    # TODO: No need to manually start a stream task; demo.load odens't stream.

async def _listen_command_pipe():
    """Restored: Creates and listens on COMMAND_PIPE_PATH for commands from host.py."""
    # VERY FIRST LINE - ABSOLUTE ENTRY TEST (KEEP THIS)
    print("[_listen_command_pipe RESTORED] EXECUTION STARTED - PRINT STATEMENT", flush=True)
    logging.getLogger(__name__).critical("[_listen_command_pipe RESTORED] EXECUTION STARTED - CRITICAL LOG")
    
    global COMMAND_PIPE_PATH, logger 
    logger.info(f"[_listen_command_pipe RESTORED] Starting. Command pipe path: {COMMAND_PIPE_PATH}")

    if os.path.exists(COMMAND_PIPE_PATH):
        try:
            os.remove(COMMAND_PIPE_PATH)
            logger.info(f"[_listen_command_pipe RESTORED] Removed existing command pipe: {COMMAND_PIPE_PATH}")
        except OSError as e:
            logger.error(f"[_listen_command_pipe RESTORED] Error removing existing command pipe {COMMAND_PIPE_PATH}: {e}")

    try:
        os.mkfifo(COMMAND_PIPE_PATH)
        logger.info(f"[_listen_command_pipe RESTORED] Created command pipe: {COMMAND_PIPE_PATH}")
    except OSError as e:
        logger.error(f"[_listen_command_pipe RESTORED] Failed to create command pipe {COMMAND_PIPE_PATH}: {e}. Extension commands will not be processed.", exc_info=True)
        return # Exit if pipe creation fails

    logger.info(f"[_listen_command_pipe RESTORED] Listener loop started for {COMMAND_PIPE_PATH}")
    while True:
        pipe_file_cmd = None
        try:
            logger.info(f"[_listen_command_pipe RESTORED] Attempting to open command pipe for reading: {COMMAND_PIPE_PATH} (blocks until writer)...")
            # Blocking open in a thread is fine as this whole function runs in its own thread.
            pipe_file_cmd = open(COMMAND_PIPE_PATH, 'r') 
            logger.info(f"[_listen_command_pipe RESTORED] Command pipe opened for reading: {COMMAND_PIPE_PATH}")
            
            while True:
                line = pipe_file_cmd.readline()
                if not line:
                    logger.warning("[_listen_command_pipe RESTORED] Writer (host.py) closed command pipe or EOF. Re-opening...")
                    # Close the current pipe_file_cmd before breaking to reopen
                    if pipe_file_cmd:
                        try: pipe_file_cmd.close()
                        except Exception as e_close_inner: logger.error(f"[_listen_command_pipe RESTORED] Error closing pipe in inner loop: {e_close_inner}")
                        pipe_file_cmd = None # Avoid trying to close again in finally
                    break # Break inner loop to reopen the pipe in the outer loop
                
                command = line.strip()
                if command:
                    logger.info(f"[_listen_command_pipe RESTORED] Received command: '{command}'")
                    # Create an asyncio task to process the command concurrently.
                    # This needs to be run on an event loop that _process_command_from_pipe can use.
                    # Since _listen_command_pipe is already running in its own loop (bg_loop/command_pipe_loop),
                    # we can schedule tasks on that same loop.
                    loop = asyncio.get_running_loop() # Get the loop this thread is running
                    loop.create_task(_process_command_from_pipe(command))
                    # asyncio.create_task(_process_command_from_pipe(command)) # This might try to use the wrong loop if not careful
        except FileNotFoundError: 
            logger.error(f"[_listen_command_pipe RESTORED] Command pipe {COMMAND_PIPE_PATH} not found during open/read. This shouldn't happen if created successfully. Retrying outer loop.")
            # Pipe might have been deleted externally. The outer loop will try to recreate.
        except Exception as e_cmd_pipe_outer:
            logger.error(f"[_listen_command_pipe RESTORED] Unhandled error in outer loop: {e_cmd_pipe_outer}", exc_info=True)
            # Avoid tight loop on persistent error
            await asyncio.sleep(5) # Use await since this is an async function now
        finally:
            if pipe_file_cmd:
                try: pipe_file_cmd.close()
                except Exception as e_close: logger.error(f"[_listen_command_pipe RESTORED] Error closing command pipe in finally: {e_close}")
        
        # If the pipe was closed (EOF) or an error occurred opening it, wait a bit before retrying the outer loop.
        logger.info("[_listen_command_pipe RESTORED] End of outer loop, will pause and retry pipe open if necessary.")
        await asyncio.sleep(1) # Use await

# --- Main UI ---
def create_ui(theme_name="Citrus"):
    with gr.Blocks(theme=theme_map.get(theme_name, Default()), css=css) as demo: 
        print("[create_ui] PRINT: About to call demo.load for _test_load_function", flush=True)
        demo.load(_test_load_function, inputs=None, outputs=None)
        print("[create_ui] PRINT: About to call demo.load for _async_test_load_function", flush=True)
        demo.load(_async_test_load_function, inputs=None, outputs=None)
        print("[create_ui] PRINT: About to call demo.load for _listen_command_pipe (this line is just for context, actual load removed)", flush=True)

        with gr.Tabs() as tabs:
            with gr.TabItem("🛑 Record", id=1):
                
                gr.Markdown("## how to Record? \nCheck the service worker logs, or trace file from the browser console.")

                # Record Status Logs
                record_status_logs_output = gr.Textbox(
                    label="Record Status Log", 
                    interactive=False, 
                    lines=10, 
                    max_lines=20, 
                    autoscroll=True,
                    show_label=True
                )

                with gr.Row():
                    host_status_output_tb = gr.Textbox(
                        label="Native Host Process Logs",
                        interactive=False,
                        lines=10,
                        max_lines=20,
                        autoscroll=True,
                        show_label=True,
                        elem_id="host_status_logs_textbox"
                    )

                    # NOTE: Use gr.Timer for periodic polling, as demo.load(every=...) is deprecated in Gradio 4+
                    t_rec = gr.Timer(0.5)
                    t_host = gr.Timer(0.5)

                    t_rec.tick(
                        poll_recorder_log,
                        inputs=None,
                        outputs=record_status_logs_output,
                        queue=False,
                        show_progress="hidden",
                    )
                    t_host.tick(
                        poll_host_status_log,
                        inputs=None,
                        outputs=host_status_output_tb,
                        queue=False,
                        show_progress="hidden",
                    )
                # with gr.Row():
                #     gr.Button("Pause polling").click(
                #         lambda: gr.Timer(active=False), None, [t_rec, t_host]
                #     )
                #     gr.Button("Resume polling").click(
                #         lambda: gr.Timer(active=True), None, [t_rec, t_host]
                #     )

            with gr.TabItem("▶️ Replay", id=2):
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
        
        # --- Original positions of demo.load hooks ---
        print("[create_ui] PRINT: Reaching original demo.load positions", flush=True)

    return demo
# --- End: Main UI ---

# --- Main entry ----
def _run_async_in_thread(loop: asyncio.AbstractEventLoop, coro):
    """Helper function to set the event loop for the new thread and run a coroutine."""
    asyncio.set_event_loop(loop)
    loop.run_until_complete(coro) 

# --- NEW Pipe-to-File Writer Coroutine ---
async def _pipe_to_file_writer():
    """Drains HOST_STATUS_LOG_Q and appends each line to the open trace file."""
    global _RECORDING_FILE_HANDLE, _RECORDING_ACTIVE, HOST_STATUS_LOG_Q, logger
    
    logger.info("[_pipe_to_file_writer] Started.")
    while _RECORDING_ACTIVE and _RECORDING_FILE_HANDLE:
        try:
            # Get from HOST_STATUS_LOG_Q, which is fed by _read_host_pipe_task
            line = await asyncio.wait_for(HOST_STATUS_LOG_Q.get(), timeout=1.0) 
            if _RECORDING_FILE_HANDLE and not _RECORDING_FILE_HANDLE.closed:
                _RECORDING_FILE_HANDLE.write(line + "\n")
                _RECORDING_FILE_HANDLE.flush() # Flush frequently to see live data in file
                HOST_STATUS_LOG_Q.task_done()
            else:
                # This case means recording was stopped and handle closed while waiting for queue
                logger.info("[_pipe_to_file_writer] Recording file handle closed or None while writer active. Exiting.")
                HOST_STATUS_LOG_Q.task_done() # Still mark as done
                break # Exit loop
        except asyncio.TimeoutError:
            # Just a timeout, check _RECORDING_ACTIVE again
            if not _RECORDING_ACTIVE:
                logger.info("[_pipe_to_file_writer] Recording became inactive during queue timeout. Exiting.")
                break
            continue # Continue loop if still active
        except Exception as e:
            logger.error(f"[_pipe_to_file_writer] Error: {e}", exc_info=True)
            # Potentially stop recording on persistent error or just log and continue
            await asyncio.sleep(0.1) # Brief pause before retrying get()
    logger.info("[_pipe_to_file_writer] Exited.")

if __name__ == "__main__":
    demo = create_ui(theme_name="Citrus")

    if not Path(MANUAL_TRACES_DIR).exists():
        Path(MANUAL_TRACES_DIR).mkdir(parents=True, exist_ok=True)
        logger.info(f"Created MANUAL_TRACES_DIR at: {Path(MANUAL_TRACES_DIR).resolve()}")
    else:
        logger.info(f"MANUAL_TRACES_DIR exists at: {Path(MANUAL_TRACES_DIR).resolve()}")

    # deamon to listen Record cmd: START_RECORDING/STOP_RECORDING
    # Create and start the background event loop and task for _listen_command_pipe
    command_pipe_loop = asyncio.new_event_loop()
    command_pipe_thread = threading.Thread(
        target=_run_async_in_thread,
        args=(command_pipe_loop, _listen_command_pipe()), # Pass the loop and the coroutine object
        daemon=True,
        name="RebrowseCmdPipeLoop"
    )
    command_pipe_thread.start()
    logger.info("Started _listen_command_pipe in a background daemon thread with its own event loop.")

    # Start _read_host_pipe_task in a background event loop (similar to command pipe listener)
    host_pipe_loop = asyncio.new_event_loop()
    host_pipe_thread = threading.Thread(
        target=_run_async_in_thread,
        args=(host_pipe_loop, _read_host_pipe_task()),
        daemon=True,
        name="RebrowseHostPipeLoop"
    )
    host_pipe_thread.start()
    logger.info("Started _read_host_pipe_task in a background daemon thread with its own event loop.")

    logger.info(f"Launching Gradio demo. Access at http://127.0.0.1:7860")
    demo.launch(server_name="127.0.0.1", server_port=7860, debug=False, allowed_paths=[MANUAL_TRACES_DIR])

_browser_init_lock = asyncio.Lock() # Add lock for ensure_browser_session

print("[DIAG] _RECORDING_ACTIVE flag is", _RECORDING_ACTIVE, flush=True)