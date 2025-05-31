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

from dotenv import load_dotenv
load_dotenv()

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

# --- Global Logging Setup ---
from src.utils.replay_streaming_manager import start_replay_async_thread_mgr, log_q as manager_log_q # Import new function

# BasicConfig should still be called once in webui.py for general console logging
if not logging.getLogger().handlers and not logging.getLogger().hasHandlers():
    logging.basicConfig(
        level=logging.DEBUG, 
        format='%(asctime)s - %(name)s - %(levelname)s - [%(module)s.%(funcName)s:%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
else:
    if logging.getLogger().getEffectiveLevel() > logging.DEBUG:
        logging.getLogger().setLevel(logging.DEBUG)

# Specific logger levels are still set in webui.py for console output
logging.getLogger('src.utils.replayer').setLevel(logging.DEBUG) # For console
logging.getLogger('src.controller.custom_controller').setLevel(logging.DEBUG) # For console
# ... other specific logger.setLevel calls for console ...

logger = logging.getLogger(__name__) # Logger for webui.py itself
logger.info("WebUI: Base logging configured. UI log: ReplayStreamingManager.")

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
# These are managed by the UI and other parts of the application.
_ui_global_browser: Optional[CustomBrowser] = None
_ui_global_browser_context: Optional[CustomBrowserContext] = None
_global_agent: Optional[Any] = None # Replace Any with your actual Agent type if available globally
_global_input_tracking_active: bool = False
# logger is defined after logging setup by: logger = logging.getLogger(__name__)

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

async def stream_replay_ui(
    trace_path: str, 
    speed: float, 
    override_files_temp_list: Optional[List[Any]], # Gradio File component gives list of tempfile._TemporaryFileWrapper
    request: gr.Request
) -> AsyncGenerator[str, None]: # Correct: This generator now yields plain strings
    """UI-facing async generator to stream replay logs."""
    print("[WEBUI stream_replay_ui] Entered function.", flush=True)
    global _ui_global_browser, _ui_global_browser_context, logger, manager_log_q
    
    # Process override_files_temp_list to get a list of file paths (strings)
    override_files_paths: List[str] = []
    print(f"[WEBUI stream_replay_ui] trace_path: {trace_path}, speed: {speed}, override_files_temp_list: {override_files_temp_list}", flush=True)
    if override_files_temp_list:
        for temp_file in override_files_temp_list:
            if hasattr(temp_file, 'name') and isinstance(temp_file.name, str):
                override_files_paths.append(temp_file.name)
            elif isinstance(temp_file, str): # Should not happen with gr.File but good to check
                override_files_paths.append(temp_file)
            else:
                logger.warning(f"stream_replay_ui: Skipping unexpected item type {type(temp_file)} in override_files_temp_list")
    print(f"[WEBUI stream_replay_ui] Processed override_files_paths: {override_files_paths}", flush=True)

    log_buffer = ""
    def _accumulate_log(new_text: str) -> str: # Renamed and changed return type
        nonlocal log_buffer
        if log_buffer and not log_buffer.endswith("\n"):
            log_buffer += "\n"
        log_buffer += new_text
        return log_buffer # Crucial: Return the plain string

    print("[WEBUI stream_replay_ui] Right before first try...finally block.", flush=True)
    try:
        # Yield the raw string for the first update
        log_buffer = _accumulate_log(f"Initiating replay for: {Path(trace_path).name}")
        yield log_buffer
    except Exception as e_first_yield:
        # Handle potential errors during the very first yield if necessary, though less common for simple accumulation
        print(f"[WEBUI stream_replay_ui] ERROR during/after first yield (before session): {e_first_yield}", flush=True)
        log_buffer = _accumulate_log(f"Error before starting: {e_first_yield}")
        yield log_buffer
        return # Stop if first yield itself fails critically
    finally:
        print("[WEBUI stream_replay_ui] After first yield attempt (inside finally).", flush=True)

    # Restore Browser Session Logic
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
        return # Stop this async generator
    
    log_buffer = _accumulate_log("Browser session ensured. Starting replay thread...")
    yield log_buffer
    print(f"[WEBUI stream_replay_ui] Yielded 'Browser session ensured'.", flush=True)

    # Restore Replay Worker Thread Starting Logic
    ui_async_q: asyncio.Queue[str] = asyncio.Queue()
    done_event = threading.Event()
    print(f"[WEBUI stream_replay_ui] Initialized ui_async_q and done_event.", flush=True)

    logger.debug(f"stream_replay_ui: Calling start_replay_async_thread_mgr for {trace_path}")    
    print(f"[WEBUI stream_replay_ui] Calling start_replay_async_thread_mgr with trace_path={trace_path}, speed={speed}, files={override_files_paths}", flush=True)
    done_event = start_replay_async_thread_mgr(trace_path, speed, override_files_paths, live_browser, live_context, ui_async_q)
    print(f"[WEBUI stream_replay_ui] start_replay_async_thread_mgr call completed. Returned done_event: {done_event}", flush=True)
    log_buffer = _accumulate_log("Replay thread started. Monitoring logs...")
    yield log_buffer
    print(f"[WEBUI stream_replay_ui] Yielded 'Replay thread started'. Beginning monitor loop.", flush=True)

    # Restore Log Streaming Loop
    loop_count = 0
    while not done_event.is_set() or not ui_async_q.empty():
        loop_count += 1
        # print(f"[WEBUI stream_replay_ui] Monitor loop iteration: {loop_count}. done_event.is_set(): {done_event.is_set()}, ui_async_q.empty(): {ui_async_q.empty()}", flush=True) # Verbose
        try:
            # Drain queue quickly
            while True: 
                line = ui_async_q.get_nowait()
                print(f"[WEBUI stream_replay_ui] Got line from ui_async_q: '{line}'", flush=True)
                log_buffer = _accumulate_log(line)
                yield log_buffer
                ui_async_q.task_done() # Important for asyncio.Queue if joined later, good practice
        except asyncio.QueueEmpty:
            # print(f"[WEBUI stream_replay_ui] ui_async_q is empty in this check.", flush=True) # Verbose
            pass # No new messages
        
        # Yield the current accumulated buffer directly to keep connection alive / update UI
        yield log_buffer 
        # print(f"[WEBUI stream_replay_ui] Yielded keep-alive/current buffer ('{log_buffer}'). Sleeping.", flush=True) # Verbose
        await asyncio.sleep(0.25) # Polling interval

    # Restore Final log flush
    logger.info("stream_replay_ui: Replay thread finished. Final log flush.")
    print(f"[WEBUI stream_replay_ui] Monitor loop exited. Final log flush. done_event.is_set(): {done_event.is_set()}, ui_async_q.empty(): {ui_async_q.empty()}", flush=True)
    while not ui_async_q.empty():
        try:
            line = ui_async_q.get_nowait()
            print(f"[WEBUI stream_replay_ui] Final flush: Got line from ui_async_q: '{line}'", flush=True)
            log_buffer = _accumulate_log(line)
            yield log_buffer
            ui_async_q.task_done()
        except asyncio.QueueEmpty:
            print(f"[WEBUI stream_replay_ui] Final flush: ui_async_q is empty.", flush=True)
            break
    
    log_buffer = _accumulate_log("--- Replay process fully completed ---")
    yield log_buffer
    logger.info("stream_replay_ui: Streaming finished.")
    print(f"[WEBUI stream_replay_ui] Yielded final 'Replay process fully completed'. Exiting function.", flush=True)

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

# --- Main UI ---
def create_ui(theme_name="Citrus"):

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
                    queue=True,                    # <- keep the queue on
                    concurrency_limit=None         # behaves like queue=False performance-wise
                )
        
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