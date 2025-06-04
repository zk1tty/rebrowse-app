from __future__ import annotations
import logging, time, asyncio, inspect
from pathlib import Path
from typing import Optional

from browser_use.browser.browser import Browser # Import Browser for type hinting
from browser_use.browser.context import BrowserContext, BrowserContextConfig # Import base class and its config
from src.browser.custom_context_config import CustomBrowserContextConfig as AppCustomBrowserContextConfig # Specific config for this app

logger = logging.getLogger(__name__) # Define logger for this module

logger.debug(f"custom_context.py importing Recorder. Timestamp: {time.time()}")
from src.utils.recorder import Recorder
logger.debug(f"Recorder imported in custom_context.py. Timestamp: {time.time()}")
if Recorder:
    init_method = getattr(Recorder, '__init__', None)
    if init_method:
        sig = inspect.signature(init_method)
        logger.debug(f"Signature of imported Recorder.__init__ in custom_context.py: {sig}")
    else:
        logger.debug("Recorder.__init__ method not found on imported Recorder class in custom_context.py")
else:
    logger.debug("Recorder could not be imported in custom_context.py")

from src.utils.replayer import TraceReplayerSync, Drift, load_trace # Updated import

class CustomBrowserContext(BrowserContext):
    """Wrapper around a Playwright BrowserContext to add record/replay helpers."""

    # ---------------- construction helpers -----------------

    def __init__(self, pw_context, browser: 'Browser', config: AppCustomBrowserContextConfig = AppCustomBrowserContextConfig()): # Add browser and config
        super().__init__(browser=browser, config=config) # Call super with browser and config
        self._ctx = pw_context                          # Playwright BrowserContext
        # self._pages = pw_context.pages # pages is a dynamic property
        self.recorder: Optional[Recorder] = None
        # self.save_dir is now handled by base class if config is used correctly, or can be specific here
        # For now, let specific save_dir override if base doesn't use it from config the same way.
        self.save_dir = Path(getattr(config, 'save_input_tracking_path', "./tmp/input_tracking")) 
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self._dom_bridge_initialized_on_context = False # New instance flag

        # Removed: asyncio.create_task(self._ensure_dom_bridge())
        
    @property
    def playwright_context(self):
        return self._ctx

    @classmethod
    def from_existing(cls, pw_context, browser: 'Browser', config: AppCustomBrowserContextConfig = AppCustomBrowserContextConfig()): # Add browser and config
        # This method creates an instance, so it needs to provide what __init__ expects.
        # The base BrowserContext does not have from_existing, so this is specific.
        # It should call cls(pw_context, browser, config)
        return cls(pw_context=pw_context, browser=browser, config=config)

    # ---------------- private bootstrap -------------------

    BINDING = "__uit_relay"

    async def _ensure_dom_bridge(self):
        from src.utils.recorder import Recorder as UITracker # Moved import here to be used

        try:
            binding_flag_name = f"_binding_{self.BINDING}_exposed"
            if not getattr(self._ctx, binding_flag_name, False):
                logger.debug(f"Binding '{self.BINDING}' not yet exposed on context {id(self._ctx)}. Exposing now via CBC instance {id(self)}.")
                await self._ctx.expose_binding(self.BINDING, self._on_binding_wrapper)
                setattr(self._ctx, binding_flag_name, True) # Mark on the Playwright context
                logger.debug(f"Binding '{self.BINDING}' exposed and marked on context {id(self._ctx)}.")
            else:
                logger.debug(f"Binding '{self.BINDING}' already marked as exposed on context {id(self._ctx)}. CBC instance {id(self)} reusing.")
            
            await asyncio.sleep(0) # Allow Playwright to process

            init_script_flag_name = "_uit_init_script_added_for_ctx"
            if not getattr(self._ctx, init_script_flag_name, False):
                logger.debug(f"Adding init script to context {id(self._ctx)} (first time or not previously marked).")
                # Ensure _JS_TEMPLATE is accessed correctly if Recorder is UITracker
                script_to_inject = UITracker._JS_TEMPLATE.format(binding=self.BINDING) 
                await self._ctx.add_init_script(script_to_inject)
                setattr(self._ctx, init_script_flag_name, True)
                logger.debug(f"Init script added to context {id(self._ctx)} and marked.")
            else:
                logger.debug(f"Init script already marked as added to context {id(self._ctx)}. Not re-adding.")

            # This instance's flag for having completed its part of the setup
            if not self._dom_bridge_initialized_on_context:
                 self._dom_bridge_initialized_on_context = True
                 logger.debug(f"DOM bridge setup sequence completed by this CBC instance {id(self)} for context {id(self._ctx)}.")
            # else:
            #      logger.debug(f"DOM bridge setup sequence previously completed by this CBC instance {id(self)}.") # Can be noisy

        except Exception as e:
            # If setup fails, this instance definitely hasn't initialized the bridge for itself.
            self._dom_bridge_initialized_on_context = False 
            logger.error(f"Failed to ensure DOM bridge for CBC {id(self)}, context {id(self._ctx)}: {e}", exc_info=True)
            raise # Re-raise to indicate a critical setup failure.

    # ---------------- binding passthrough ------------------
    
    async def _on_binding_wrapper(self, source, payload):
        page = source.get("page") 
        if not page:
            logger.error("Page not found in binding source. Cannot initialize or use tracker.")
            return

        try: # Add try-except block
            if not self.recorder:
                logger.debug(f"Lazy-initializing Recorder for page: {page.url} (context: {id(self._ctx)})")
                self.recorder = Recorder(context=self._ctx, page=page) 
                self.recorder.is_recording = True 
                self.recorder.current_url = page.url 
                
                if self.recorder and self.recorder.context and hasattr(self.recorder, '_setup_page_listeners'): # Extra guard for linter
                    logger.debug(f"CONTEXT_EVENT: Attaching context-level 'page' event listener in CustomBrowserContext for context {id(self._ctx)}")
                    self.recorder.context.on("page", 
                        lambda p: asyncio.create_task(self._log_and_setup_page_listeners(p)))
                    
                    await self.recorder._setup_page_listeners(page) 
                elif not (self.recorder and self.recorder.context):
                    logger.error("Input tracker or its context not set after initialization during listener setup.")
                elif not hasattr(self.recorder, '_setup_page_listeners'):
                     logger.error("_setup_page_listeners method not found on input_tracker instance.")

            if self.recorder:
                await self.recorder._on_dom_event(source, payload) 
            else:
                # This case should ideally not be reached if logic above is correct
                logger.error("Input tracker somehow still not initialized in _on_binding_wrapper before passing event.")
        except Exception as e:
            logger.error(f"Error in _on_binding_wrapper: {e}", exc_info=True)
            # Potentially re-raise or handle more gracefully depending on whether Playwright
            # can recover from errors in the binding callback. For now, just log.

    # New helper method to log before calling _setup_page_listeners
    async def _log_and_setup_page_listeners(self, page_object):
        logger.debug(f"CONTEXT_EVENT: Context 'page' event fired! Page URL: {page_object.url}, Page Object ID: {id(page_object)}. Calling _setup_page_listeners.")
        if self.recorder: # Ensure input_tracker still exists
            await self.recorder._setup_page_listeners(page_object)
        else:
            logger.error("CONTEXT_EVENT: self.recorder is None when _log_and_setup_page_listeners was called.")

    # ---------------- recording API -----------------------

    async def start_input_tracking(self, event_log_queue: Optional[asyncio.Queue] = None):
        await self._ensure_dom_bridge()

        current_pages = self.pages
        page_to_use = None

        if current_pages:
            content_pages = [
                p for p in current_pages 
                if p.url and 
                   not p.url.startswith("devtools://") and 
                   not p.url.startswith("chrome://") and 
                   not p.url.startswith("about:")
            ]
            if content_pages:
                page_to_use = content_pages[0]
                logger.debug(f"Using existing content page for tracking: {page_to_use.url}")
            else:
                non_devtools_pages = [p for p in current_pages if p.url and not p.url.startswith("devtools://")]
                if non_devtools_pages:
                    page_to_use = non_devtools_pages[0]
                    logger.debug(f"No ideal content pages. Using first non-devtools page: {page_to_use.url}")
                else:
                    logger.warning("No suitable (non-devtools) pages found. Creating a new page.")
                    page_to_use = await self.new_page()
                    if page_to_use: await page_to_use.goto("about:blank")
        else:
            logger.debug("No pages in current context. Creating a new page.")
            page_to_use = await self.new_page()
            if page_to_use: await page_to_use.goto("about:blank")
        
        if not page_to_use:
            logger.error("Could not get or create a suitable page for input tracking. Tracking will not start.")
            if event_log_queue:
                try:
                    event_log_queue.put_nowait("⚠️ Error: Could not get or create a page for recording.")
                except asyncio.QueueFull:
                    logger.warning("UI event log queue full when logging page creation error.")
            return

        if not self.recorder: # Initialize Recorder if it doesn't exist
            logger.debug(f"Initializing Recorder for page: {page_to_use.url}")
            # REVERTED: Pass event_log_queue to Recorder constructor
            self.recorder = Recorder(context=self._ctx, page=page_to_use, event_log_queue=event_log_queue)
            # REMOVED: Warning about potential signature mismatch is no longer needed if server restart fixed it.
            await self.recorder.start_tracking() 
        elif not self.recorder.is_recording: # If tracker exists but not recording
            logger.debug(f"Re-activating recording on existing input tracker. Ensuring it targets page: {page_to_use.url}")
            self.recorder.page = page_to_use
            self.recorder.current_url = page_to_use.url
            # REVERTED: Ensure the existing recorder instance also gets the queue if it didn't have it.
            if event_log_queue and not (hasattr(self.recorder, 'event_log_queue') and self.recorder.event_log_queue):
                if hasattr(self.recorder, 'event_log_queue'):
                    self.recorder.event_log_queue = event_log_queue
                    logger.debug("Recorder event_log_queue updated on existing recorder instance.")
                else:
                    # This case should ideally not happen if Recorder class is consistent
                    logger.warning("Attempted to set event_log_queue on a Recorder instance lacking the attribute.")
            await self.recorder.start_tracking()
        else: # Tracker exists and is recording
            if self.recorder.page != page_to_use:
                if page_to_use: # Explicitly check page_to_use is not None here
                    logger.warning(f"Input tracker is active but on page {self.recorder.page.url if self.recorder.page else 'None'}. Forcing switch to {page_to_use.url}")
                    self.recorder.page = page_to_use
                    self.recorder.current_url = page_to_use.url
                    await self.recorder.start_tracking() # Re-run to ensure listeners are on this page
                else:
                    # This case should ideally not be reached due to earlier checks, but as a safeguard:
                    logger.error("Input tracker is active, but the determined page_to_use is None. Cannot switch tracker page.")
            else: # self.recorder.page == page_to_use
                if page_to_use: # page_to_use should not be None here if it matches a valid tracker page
                    logger.debug(f"Input tracking is already active and on the correct page: {page_to_use.url}")
                else: # Should be an impossible state if self.recorder.page was not None
                    logger.error("Input tracking is active, but page_to_use is None and matched self.recorder.page. Inconsistent state.")
        
        if page_to_use: # Final log should also be conditional
            logger.debug(f"User input tracking active. Target page: {page_to_use.url}")
        # If page_to_use is None here, an error was logged and function returned earlier.

    async def stop_input_tracking(self):
        if self.recorder and self.recorder.is_recording:
            await self.recorder.stop_tracking() 
            # Format the filename with a human-readable date and time
            timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"record_{timestamp}.jsonl"
            path = self.save_dir / filename
            jsonl_data = self.recorder.export_events_to_jsonl()
            if jsonl_data.strip():
                path.write_text(jsonl_data)
                logger.info("Saved user input tracking to %s", path)
                return str(path)
            else:
                logger.info("No events recorded, skipping file save.")
                return None
        else:
            logger.warning("Input tracking not active or tracker not initialized, nothing to stop/save.")
            return None


    # ---------------- replay API --------------------------

    async def replay_input_events(self, trace_path: str, speed: float = 2.0, keep_open: bool = True):
        current_pages = self.pages
        page_for_replay = current_pages[0] if current_pages else await self.new_page()
        if not page_for_replay:
            logger.error("Cannot replay events, no page available.")
            return False
            
        trace_data = load_trace(trace_path)
        if not trace_data:
            logger.error(f"Trace file {trace_path} is empty or could not be loaded.")
            return False
        
        # TODO: Replaying from CustomBrowserContext might require a functional controller
        # if the trace contains events like clipboard operations or file uploads/downloads
        # that rely on controller.execute().
        # This instantiation will need to be updated for TraceReplayerSync's new __init__ signature
        # if this method is to be used with the refactored replayer.
        # For now, just fixing the class name to resolve import error.
        # It will also need ui_q and main_loop if it were to call the new TraceReplayerSync.
        # This method is async, TraceReplayerSync is sync - needs careful thought if enabled.
        print("[CustomBrowserContext] WARNING: replay_input_events is using TraceReplayerSync placeholder without full args. May not function.")
        rep = TraceReplayerSync(page_for_replay, trace_data, controller=None) # Placeholder for controller, ui_q, main_loop
        try:
            rep.play(speed=speed) # play is now a synchronous method
            logger.info("Successfully replayed trace file: %s", trace_path)
            return True
        except Drift as d:
            logger.error("Drift detected during replay of %s: %s", trace_path, d)
            return False
        except Exception as e:
            import traceback
            logger.error(f"Unexpected error during replay of {trace_path}: {e}\n{traceback.format_exc()}")
            return False
        finally:
            if not keep_open:
                logger.info("Replay finished and keep_open is False. Closing context.")
                await self.close() # Call own close method

    async def close(self):
        logger.info(f"Closing CustomBrowserContext (Playwright context id: {id(self._ctx)}).")
        # Check input_tracker before accessing is_recording
        if hasattr(self, 'input_tracker') and self.recorder and self.recorder.is_recording:
            logger.info("Input tracking is active, stopping it before closing context.")
            await self.stop_input_tracking()
        
        if self._ctx:
            await self._ctx.close()
        logger.info("CustomBrowserContext closed.")

    @property
    def pages(self):
        if self._ctx:
            try:
                return self._ctx.pages
            except Exception: # Broad exception for now, ideally Playwright-specific error
                # This can happen if the context or browser is closed.
                return []
        return []
    
    async def new_page(self, **kwargs):
        if self._ctx:
            try:
                # Attempting to access pages is a way to check if context is usable
                _ = self._ctx.pages 
                return await self._ctx.new_page(**kwargs)
            except Exception as e: # Catch error if context is closed
                logger.error(f"Playwright context not available or closed when trying to create new page: {e}")
                return None
        logger.error("Playwright context (_ctx) is None, cannot create new page.")
        return None