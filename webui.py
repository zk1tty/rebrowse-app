from src.browser.custom_browser import CustomBrowser
import pdb
import logging
import os
import gradio as gr
import queue 
import threading 
import time 
import asyncio 
import tempfile 
from typing import Optional, List, Dict, Any, Union, Callable
from pathlib import Path
from gradio.themes import Default, Soft, Glass, Monochrome, Ocean, Origin, Base, Citrus
import pandas as pd

from dotenv import load_dotenv

load_dotenv()
# import os # Duplicates removed
import glob
import asyncio
import argparse

# Import task templates
from task_templates import TASK_TEMPLATES

# --- Project-specific global imports needed by replay logic ---
from src.browser.custom_browser import CustomBrowser
from src.browser.custom_context import CustomBrowserContext
from src.controller.custom_controller import CustomController
from src.utils.replayer import TraceReplayer, load_trace, Drift
from src.browser.custom_context_config import CustomBrowserContextConfig as AppCustomBrowserContextConfig
from browser_use.browser.browser import BrowserConfig
from src.utils.trace_utils import get_upload_file_names_from_trace # ADDED
from src.utils import user_input_functions # ADDED for get_file_info
from browser_use.browser.context import BrowserContextWindowSize # ADDED IMPORT

# --- User Snippet: Section 1 & 2: Queue-based log capture ---
log_q: queue.Queue[str] = queue.Queue()

class WebuiQueueHandler(logging.Handler): # Renamed from QueueHandler to avoid potential name collisions during refactor
    """Push each formatted log record into a threadsafe queue."""
    def emit(self, record: logging.LogRecord):
        log_q.put(self.format(record))

# One-time attachment (do this only once in the file)
# Remove any previous basicConfig or root logger handlers if re-running this setup logic (e.g. dev mode)
for h_old in list(logging.getLogger().handlers):
    logging.getLogger().removeHandler(h_old)

logging.basicConfig( # Establish base console logging if desired, or remove if queue is only target
    level=logging.DEBUG, 
    format='%(asctime)s - %(name)s - %(levelname)s - [%(module)s.%(funcName)s:%(lineno)d] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

_snippet_queue_handler = WebuiQueueHandler()
_snippet_queue_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
_snippet_queue_handler.setLevel(logging.INFO) # Capture INFO and above for the UI queue

root_logger = logging.getLogger() 
root_logger.addHandler(_snippet_queue_handler)
if root_logger.getEffectiveLevel() > logging.INFO: # Ensure root logger will pass INFO to our handler
    root_logger.setLevel(logging.INFO)

# Configure levels for other specific loggers from your project as needed
# Example: logging.getLogger('src.utils.replayer').setLevel(logging.DEBUG)

logger = logging.getLogger(__name__) # Logger for webui.py itself
logger.info("User Snippet: WebuiQueueHandler initialized for Gradio streaming.")

def _harvest_log_queue_snippet() -> str:
    """Return all queued log lines as one newline-joined string."""
    lines = []
    while not log_q.empty():
        try:
            lines.append(log_q.get_nowait())
        except queue.Empty:
            break
    return "\n".join(lines)
# --- End User Snippet: Section 1 & 2 ---

# --- Global variables for replay thread parameters ---
_replay_params_lock = threading.Lock()
_replay_current_params: Optional[Dict[str, Any]] = None
_replay_done_event: Optional[threading.Event] = None # To signal completion
_replay_target_function_for_thread: Optional[Callable[[], None]] = None # To pass the actual replay logic

# It no longer yields, it's a regular async function that returns a status string.
# Its INFO logs will be captured by the QueueHandler.
async def global_replay_trace_wrapper(
    selected_trace_path: str, 
    local_replay_speed: float, 
    override_files_list: Optional[List[Union[tempfile._TemporaryFileWrapper, str]]]
) -> str:
    logger.info(f"--- replay_trace_wrapper (GLOBAL): Called with path: {selected_trace_path}, Speed: {local_replay_speed} ---")
    global _global_browser_context # Needs access to the global context
    
    user_provided_file_paths = []
    if override_files_list:
        for temp_file_obj in override_files_list:
            if isinstance(temp_file_obj, str):
                user_provided_file_paths.append(temp_file_obj)
            elif hasattr(temp_file_obj, 'name'):
                file_name_attr = getattr(temp_file_obj, 'name')
                if isinstance(file_name_attr, str):
                    user_provided_file_paths.append(file_name_attr)
                # ... (else warnings as before) ...
        logger.info(f"User provided override files for replay: {user_provided_file_paths}")
    else:
        logger.info("No override files provided by user for this replay.")

    page_for_replay = await get_page_for_replay_global()
    if not page_for_replay:
        error_msg = "Error: Browser context/page not available for replay in global_replay_trace_wrapper."
        logger.error(error_msg)
        return error_msg
    
    status_message = f"Replay of '{selected_trace_path}' starting..."
    try:
        current_controller_context: Optional[CustomBrowserContext] = None
        if _global_browser_context and \
           isinstance(_global_browser_context, CustomBrowserContext) and \
           hasattr(_global_browser_context, 'playwright_context') and \
           _global_browser_context.playwright_context == page_for_replay.context:
            current_controller_context = _global_browser_context
        else:
            logger.error("Replay: _global_browser_context mismatch or invalid for replay page.")
            # Attempt to use _global_browser_context directly if it exists and seems valid, 
            # otherwise this is a critical state. 
            if isinstance(_global_browser_context, CustomBrowserContext):
                current_controller_context = _global_browser_context
                logger.warning("Using potentially mismatched _global_browser_context for controller.")
            else:
                 return "Error: Could not establish a valid CustomBrowserContext for the replay controller."
        
        if not current_controller_context: # Should be caught by above, but as safeguard
             return "Error: Controller context is None before controller instantiation."

        controller = CustomController(browser_context=current_controller_context)
        trace_events = load_trace(selected_trace_path)
        if not trace_events:
            return f"Error: Trace file {selected_trace_path} is empty or could not be loaded."

        replayer = TraceReplayer(
            page_for_replay, trace_events, controller,
            user_provided_files=user_provided_file_paths
        )
        await replayer.play(speed=local_replay_speed)
        status_message = f"Input trace '{Path(selected_trace_path).name}' replayed successfully."
    except Drift as d_err:
        logger.error(f"Drift detected during replay of {selected_trace_path}: {d_err}", exc_info=True)
        status_message = f"Drift error during replay: {d_err}"
    except Exception as e_err:
        logger.error(f"Exception during replay of {selected_trace_path}: {e_err}", exc_info=True)
        status_message = f"General error during replay: {str(e_err)}"
    
    logger.info(f"--- Replay Finished (global_replay_trace_wrapper) --- Status: {status_message}")
    return status_message

# --- Threading helpers (modified to call global_replay_trace_wrapper) ---
def _run_replay_logic_in_thread(done_event: threading.Event):
    global _replay_current_params
    params = None
    with _replay_params_lock:
        if _replay_current_params: params = _replay_current_params.copy()
    if not params: 
        logger.error("Replay thread: No parameters."); done_event.set(); return

    logger.info(f"Background replay thread started for trace: {params['trace_path']}")
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        final_status = loop.run_until_complete(global_replay_trace_wrapper(params['trace_path'], params['speed'], params['override_files']))
        logger.info(f"Background replay thread finished for trace: {params['trace_path']}. Status: {final_status}")
    except Exception as e: logger.error(f"Error in replay thread for {params['trace_path']}: {e}", exc_info=True)
    finally: done_event.set()

# start_replay_async_thread remains largely the same but calls the modified _run_replay_logic_in_thread
def start_replay_async_thread(trace_path: str, speed: float, override_files: Optional[List[Any]]) -> threading.Event:
    global _replay_current_params
    with _replay_params_lock: _replay_current_params = {"trace_path": trace_path, "speed": speed, "override_files": override_files}
    done = threading.Event()
    threading.Thread(target=_run_replay_logic_in_thread, args=(done,), daemon=True).start()
    logger.info(f"Replay thread created/started for trace: {trace_path}")
    return done

# --- Threading helpers ---
def _execute_target_in_thread():
    """Runs the function stored in _replay_target_function_for_thread."""
    global _replay_target_function_for_thread, _replay_done_event
    if _replay_target_function_for_thread and _replay_done_event:
        try:
            logger.info("Background thread: Starting execution of target function.")
            _replay_target_function_for_thread() # This function will handle its own asyncio loop if needed
            logger.info("Background thread: Target function execution finished.")
        except Exception as e_thread:
            logger.error(f"Background thread: Error executing target: {e_thread}", exc_info=True)
        finally:
            _replay_done_event.set()
    else:
        logger.error("Background thread: Target function or done event not set.")
        if _replay_done_event: _replay_done_event.set() # Ensure event is set to avoid hangs

def start_function_in_async_thread(target_callable: Callable[[], None]) -> threading.Event:
    """Launches the given callable in a daemon thread."""
    global _replay_target_function_for_thread, _replay_done_event
    
    with _replay_params_lock: # Protect access to shared globals
        _replay_target_function_for_thread = target_callable
        _replay_done_event = threading.Event()
    
    thread = threading.Thread(target=_execute_target_in_thread, daemon=True)
    thread.start()
    logger.info(f"Background thread created and started for target: {target_callable.__name__ if hasattr(target_callable, '__name__') else 'callable'}")
    return _replay_done_event

# --- Streaming generator (global) ---
def replay_log_streamer(trace_path: str, speed: float, override_files: Optional[List[Any]], request: gr.Request):
    # This function will be called by Gradio. It needs access to the actual replay logic.
    # We will set up a callable inside create_ui that captures the necessary scope.
    logger.info(f"replay_log_streamer: Called for trace '{trace_path}'. Setting up replay...")
    if not trace_path:
        yield "Error: No trace file path provided."; return

    # The callable `replay_closure` will be defined inside `create_ui` and passed via a global intermediary or state
    # For now, assume `_setup_and_get_replay_closure` is called by the click handler before this streamer
    # This is a simplification; a better way is to pass the replay function itself if Gradio allows it or use gr.State
    
    # This is where we need to bridge to the replay_trace_wrapper inside create_ui
    # This requires replay_trace_wrapper (or a wrapper around it) to be passed or accessible.
    # For this iteration, we rely on the button click in create_ui to set up the specific replay task.
    # This streamer just polls logs based on a globally managed done_event.
    
    # This global `_replay_done_event` must be set by the button click action
    # that *also* calls start_function_in_async_thread with the correct target.
    # This is becoming complex. Let's simplify: the click handler will directly start the thread
    # and this streamer will just monitor based on an event passed to it.
    # The current approach has this streamer initiate the thread via start_replay_async_thread,
    # but `start_replay_async_thread` needs the actual replay function.

    # This function will be defined inside `create_ui` and capture necessary context.
    # For now, it's a placeholder to illustrate. The actual call to start the thread
    # will happen from within `create_ui` when the button is clicked.
    # This replay_log_streamer will then be simplified to just yield logs based on a shared event.
    
    # This function will be simplified. The button click will start the thread.
    # This function, when called by Gradio's .click, will just return the initial buffer
    # and rely on a separate mechanism for the actual log streaming updates.
    # THE PATTERN PROVIDED BY USER IS: click calls this generator.

    buf = "Replay initiated... Logs will stream below.\n"; yield buf

    # The `target_for_thread_ref` needs to be a callable that executes the actual replay.
    # This callable should be prepared by the click handler in create_ui.
    # For this edit, we pass parameters to `start_replay_async_thread` which then calls
    # a globally defined `_run_replay_logic_in_thread_with_global_params` that uses global params.

    # Redefine how params are passed to the thread to use the global params set by start_replay_async_thread
    # This makes _run_replay_logic_in_thread simpler as it just picks up from _replay_current_params
    
    global _replay_current_params, _replay_params_lock
    with _replay_params_lock:
        _replay_current_params = {
            "trace_path": trace_path, 
            "speed": speed, 
            "override_files": override_files
        }

    # The target for the thread is now fixed: _run_replay_logic_in_thread
    # which uses the global _replay_current_params.
    # This function, _run_replay_logic_in_thread, must call your *actual* async replay_trace_wrapper
    # (which needs to be moved global or made accessible).
    
    done_event_for_this_replay = threading.Event()
    thread = threading.Thread(target=_run_replay_logic_in_thread, args=(done_event_for_this_replay,), daemon=True)
    thread.start()
    logger.info(f"Replay thread (new internal one) created/started for trace: {trace_path}")

    while not done_event_for_this_replay.is_set():
        new_log_lines = _harvest_log_queue_snippet()
        if new_log_lines:
            if buf and not buf.endswith('\n'): buf += "\n"
            buf += new_log_lines
            yield buf 
        time.sleep(0.25) 

    logger.info("Replay thread (internal) signaled done. Final log flush for UI.")
    new_log_lines = _harvest_log_queue_snippet()
    if new_log_lines: 
        if buf and not buf.endswith('\n'): buf += "\n"
        buf += new_log_lines
    buf += f"\n--- Replay of {Path(trace_path).name} complete (streamer). ---"
    yield buf

def create_ui(theme_name="Citrus"):
    # Ensure global theme_map and css are defined before this if gr.Blocks uses them by name
    # global theme_map, css # Or ensure they are passed in or defined locally if not global

    # Remove the inner function definitions for get_page_for_replay and replay_trace_wrapper
    # as they are now global (get_page_for_replay_global, actual_global_replay_trace_wrapper)

    with gr.Blocks(theme=theme_map.get(theme_name, Default()), css=css) as demo: # Added .get for safety
        # ... (Define trace_file_path Textbox for general use if needed)

        with gr.Tabs() as tabs:
            # ... (Other Tabs: Settings, Prompt Agent, Record, etc.) ...

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
                # (handle_trace_selection_for_uploads and update_trace_info_for_replay_tab remain as they were)
                def handle_trace_selection_for_uploads(df_data: pd.DataFrame, evt: gr.SelectData):
                    # ... (your existing logic) ...
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
                
                refresh_traces_btn.click( # Assuming refresh_traces_for_replay_tab is defined globally or accessible
                    fn=refresh_traces_for_replay_tab, 
                    inputs=[], 
                    outputs=[trace_files_list, trace_file_details_state_replay]
                )

                # MODIFIED: trace_replay_btn click handler now calls the global streamer
                trace_replay_btn.click(
                    fn=replay_log_streamer_snippet, # Calls the global streaming generator
                    inputs=[
                        selected_trace_path_for_replay, 
                        replay_speed_input, 
                        override_upload_files_component
                    ],
                    outputs=[replay_status_output]
                )
        
        # REMOVE all old polling mechanisms (log_polling_trigger, demo.load with every for polling)

    return demo

# Global refresh_traces_for_replay_tab function - ENSURE THIS IS THE ONLY DEFINITION
# The one that was a simple placeholder like `return pd.DataFrame(...), []` should be deleted.
def refresh_traces_for_replay_tab():
    logger.info("refresh_traces_for_replay_tab called (global, functional version)")
    try:
        # Ensure MANUAL_TRACES_DIR and user_input_functions are accessible here (should be global)
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
        # Ensure pd is accessible here (should be global `import pandas as pd`)
        pandas_df = pd.DataFrame(df_rows, columns=["Name", "Created", "Size", "Events"])
        return pandas_df, files_details_list 
    except Exception as e:
        logger.error(f"Error in refresh_traces_for_replay_tab: {e}", exc_info=True)
        return pd.DataFrame(columns=["Name", "Created", "Size", "Events"]), [] 

# --- Global Browser/Context Variables ---
# These are managed by the UI and other parts of the application.
_global_browser: Optional[CustomBrowser] = None
_global_browser_context: Optional[CustomBrowserContext] = None
_global_agent: Optional[Any] = None # Replace Any with your actual Agent type if available globally
_global_input_tracking_active: bool = False
# logger is defined after logging setup by: logger = logging.getLogger(__name__)

# --- NEW Global variable for the replay-specific context ---
# This variable needs to be set by your UI logic when a suitable context is active.
GLOBAL_REPLAY_BROWSER_CTX: Optional[CustomBrowserContext] = None

# --- Global Helper Functions for Replay Logic ---
def context_is_closed(ctx) -> bool:
    """Checks if a Playwright BrowserContext is closed."""
    if not ctx: return True # If ctx is None, treat as closed
    try:
        _ = ctx.pages # Accessing pages on a closed context raises an error
        return False
    except Exception:
        return True

# --- Global Helper Function for Replay Logic: get_page_for_replay_global ---
# THIS SHOULD BE THE ONLY DEFINITION OF THIS FUNCTION, AND IT SHOULD BE THE ROBUST ONE.
# Any placeholder versions should have been deleted.
async def get_page_for_replay_global() -> Optional[Any]: 
    # ... (Full robust logic as previously accepted and refined) ...
    global _global_browser_context, _global_browser, logger
    needs_browser_init = False
    if not _global_browser: needs_browser_init = True
    elif not _global_browser.resolved_playwright_browser: needs_browser_init = True; _global_browser = None
    elif not _global_browser.resolved_playwright_browser.is_connected(): needs_browser_init = True; _global_browser = None
    if needs_browser_init:
        try:
            logger.info("get_page_for_replay_global: Initializing CustomBrowser...")
            browser_config = BrowserConfig(headless=False, cdp_url=os.getenv("CHROME_CDP_URL"), chrome_instance_path=os.getenv("CHROME_PATH"))
            _global_browser = CustomBrowser(config=browser_config); await _global_browser.async_init()
            if not (_global_browser and _global_browser.resolved_playwright_browser and _global_browser.resolved_playwright_browser.is_connected()): raise Exception("Browser did not connect")
            _global_browser_context = None 
        except Exception as e: logger.error(f"GLOBAL BROWSER INIT FAILED: {e}", exc_info=True); _global_browser = None; return None
    if not _global_browser: logger.error("Cannot get/create context, _global_browser is None."); return None        
    needs_context_init = False
    if not _global_browser_context: needs_context_init = True
    elif hasattr(_global_browser_context, 'browser') and _global_browser_context.browser != _global_browser: _global_browser_context = None; needs_context_init = True # Check hasattr
    elif hasattr(_global_browser_context, 'playwright_context') and context_is_closed(_global_browser_context.playwright_context): _global_browser_context = None; needs_context_init = True # Check hasattr
    elif not hasattr(_global_browser_context, 'playwright_context'): _global_browser_context = None; needs_context_init = True
    if needs_context_init:
        try:
            logger.info("get_page_for_replay_global: Initializing/Reusing CustomBrowserContext...")
            ctx_config = AppCustomBrowserContextConfig(enable_input_tracking=False, browser_window_size=BrowserContextWindowSize(width=1280, height=1100))
            if _global_browser.config and _global_browser.config.cdp_url and _global_browser.resolved_playwright_browser:
                _global_browser_context = await _global_browser.reuse_existing_context(config=ctx_config)
                if not _global_browser_context: _global_browser_context = await _global_browser.new_context(config=ctx_config)
            else: _global_browser_context = await _global_browser.new_context(config=ctx_config)
            if not (_global_browser_context and hasattr(_global_browser_context, 'playwright_context') and _global_browser_context.playwright_context): raise Exception("Context or its Playwright link is invalid after creation/reuse")
        except Exception as e: logger.error(f"GLOBAL CONTEXT INIT FAILED: {e}", exc_info=True); _global_browser_context = None; return None
    if not (_global_browser_context and hasattr(_global_browser_context, 'playwright_context') and _global_browser_context.playwright_context): logger.error("Context invalid before page creation."); return None
    active_pages = _global_browser_context.pages
    if not active_pages:
        try: await _global_browser_context.new_page(); active_pages = _global_browser_context.pages
        except Exception as e: logger.error(f"GLOBAL PAGE CREATION FAILED: {e}", exc_info=True); return None
        if not active_pages: logger.error("Still no pages after new_page() call."); return None
    active_page = active_pages[0]
    if active_page.url == "about:blank" or not active_page.url.startswith("http"):
        try: await active_page.goto("https://www.google.com", wait_until="domcontentloaded", timeout=10000)
        except Exception as e: logger.warning(f"GLOBAL NAV TO GOOGLE FAILED: {e}")
    logger.info(f"get_page_for_replay_global: Successfully obtained page '{active_page.url}'.")
    return active_page

# --- Global actual_global_replay_trace_wrapper (ensure this calls the above robust get_page_for_replay_global) ---
# (Definition of actual_global_replay_trace_wrapper)

# --- Global Constants ---
MANUAL_TRACES_DIR = "./tmp/input_tracking" # ADDED global definition

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

# --- Streaming Generator (Section 4 from user snippet - NOW GLOBAL) ---
# Ensure this is the correct name used by trace_replay_btn.click in create_ui
def replay_log_streamer_snippet(trace_path: str, speed: float, override_files: Optional[List[Any]], request: gr.Request):
    logger.info(f"replay_log_streamer_snippet: Called for trace '{trace_path}'. Speed: {speed}")
    if not trace_path: yield "Error: No trace file path provided."; return
    trace_file_name = Path(trace_path).name 
    buf = f"Replay initiated for '{trace_file_name}'... Logs will stream below.\n"; yield gr.update(value=buf)
    done_event = start_replay_async_thread(trace_path, speed, override_files)
    while not done_event.is_set():
        new_log_lines = _harvest_log_queue_snippet()
        if new_log_lines:
            if buf and not buf.endswith('\n'): buf += "\n"
            buf += new_log_lines
            yield gr.update(value=buf) 
        time.sleep(0.25) 
    logger.info(f"replay_log_streamer_snippet: done_event is set for '{trace_file_name}'. Final log flush.")
    new_log_lines = _harvest_log_queue_snippet()
    if new_log_lines:
        if buf and not buf.endswith('\n'): buf += "\n"
        buf += new_log_lines
    buf += f"\n--- Replay of '{trace_file_name}' complete (streamer). ---"; yield gr.update(value=buf)

# --- Ensure this is at the end of the file, at the global scope ---

# Build once; let the `gradio` CLI launch & reload
demo = create_ui(theme_name="Citrus")   # gradio looks for "demo"
app  = demo                            # optional alias, harmless

# --- allow plain `python webui.py` ----------------------------------
if __name__ == "__main__":              # executed only when you run: python webui.py
    # Ensure MANUAL_TRACES_DIR exists at startup (MANUAL_TRACES_DIR should be defined globally)
    if not Path(MANUAL_TRACES_DIR).exists(): # Check before creating
        Path(MANUAL_TRACES_DIR).mkdir(parents=True, exist_ok=True)
        logger.info(f"Created MANUAL_TRACES_DIR at: {Path(MANUAL_TRACES_DIR).resolve()}")
    else:
        logger.info(f"MANUAL_TRACES_DIR already exists at: {Path(MANUAL_TRACES_DIR).resolve()}")

    logger.info(f"Launching Gradio demo. Access at http://127.0.0.1:7860")
    demo.launch(server_name="127.0.0.1", server_port=7860, debug=True, allowed_paths=[MANUAL_TRACES_DIR])
