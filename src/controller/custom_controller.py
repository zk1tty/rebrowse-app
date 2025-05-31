import pdb
import pyperclip
from pathlib import Path
import shutil
from typing import Optional, Type, Any 
from pydantic import BaseModel
from browser_use.agent.views import ActionResult
# BaseBrowserContext might still be needed if base Controller class uses it, or for type hints if some methods expect it.
# For now, if only used by removed registered actions, it can be removed. Let's assume it can be removed for now.
# from browser_use.browser.context import BrowserContext as BaseBrowserContext
from browser_use.controller.service import Controller 
# Sync Playwright imports
from playwright.sync_api import Page as SyncPage, BrowserContext as SyncBrowserContext, TimeoutError as SyncPlaywrightTimeoutError # ADDED/MODIFIED

from main_content_extractor import MainContentExtractor
from browser_use.controller.views import (
    ClickElementAction,
    DoneAction, # Keep if used by base or other parts
    ExtractPageContentAction,
    GoToUrlAction,
    InputTextAction,
    OpenTabAction,
    ScrollAction,
    SearchGoogleAction,
    SendKeysAction,
    SwitchTabAction,
)
import logging

logger = logging.getLogger(__name__)

class CustomControllerSync(Controller): # RENAMED CLASS
    """A controller that extends browser_use controllerfunctionality using Sync Playwright API."""
    
    def __init__(self, 
                 page: SyncPage, # CHANGED: Expects a SyncPage instance
                 exclude_actions: list[str] = [],
                 output_model: Optional[Type[BaseModel]] = None
                 ):
        super().__init__(exclude_actions=exclude_actions, output_model=output_model)
        self.page = page # Store the synchronous page
        self.browser_context = page.context # Store its context (which is also sync)
        # self._register_custom_actions() # Removed call

    def execute(self, action_name: str, **kwargs): # SYNC
        logger.debug(f"CustomControllerSync.execute CALLED for action: '{action_name}', args: {kwargs}")
        page = self.page # Use the stored synchronous page
        if not page:
            logger.error("CustomControllerSync.execute: self.page is not set (should have been in __init__).")
            raise RuntimeError("Failed to get current page for action execution.")

        if action_name == "Upload local file":
            selector = kwargs.get("selector")
            file_path = kwargs.get("file_path")
            if not selector or not file_path:
                logger.error(f"Missing selector or file_path for 'Upload local file'. Got: selector='{selector}', file_path='{file_path}'")
                raise ValueError("Selector and file_path are required for Upload local file action.")
            
            logger.info(f"Directly executing 'Upload local file': selector='{selector}', file_path='{file_path}'")
            try:
                page.locator(selector).set_input_files(file_path) # SYNC
                logger.info(f"Successfully set input files for selector '{selector}' with path '{file_path}'")
                return ActionResult(extracted_content=f"Uploaded {Path(file_path).name} to {selector}")
            except Exception as e:
                logger.error(f"Error during direct execution of 'Upload local file': {e}", exc_info=True)
                raise
        
        elif action_name == "Download remote file":
            suggested_filename = kwargs.get("suggested_filename")
            recorded_local_path = kwargs.get("recorded_local_path")
            dest_dir_str = kwargs.get("dest_dir", "~/Downloads") 

            if not recorded_local_path:
                logger.error(f"Missing 'recorded_local_path' for 'Download remote file' action. Cannot replay download.")
                raise ValueError("recorded_local_path is required to replay a download.")
            
            if not suggested_filename:
                suggested_filename = Path(recorded_local_path).name 
                logger.warning(f"Missing 'suggested_filename' in download event, using name from recorded_local_path: {suggested_filename}")

            source_path = Path(recorded_local_path)
            if not source_path.exists():
                logger.error(f"Recorded local file for download does not exist: '{source_path}'")
                raise FileNotFoundError(f"Recorded file for download replay not found: {source_path}")

            dest_dir = Path(dest_dir_str).expanduser()
            dest_dir.mkdir(parents=True, exist_ok=True)
            final_dest_path = dest_dir / suggested_filename

            original_url_for_logging = kwargs.get("url", "N/A")
            logger.info(f"Replaying 'Download remote file' (original URL: {original_url_for_logging}): Copying '{source_path}' to '{final_dest_path}'")
            try:
                shutil.copy(str(source_path), str(final_dest_path))
                logger.info(f"Successfully replayed download by copying to '{final_dest_path}'")
                return ActionResult(extracted_content=str(final_dest_path))
            except Exception as e:
                logger.error(f"Error replaying 'Download remote file' by copying: {e}", exc_info=True)
                raise

        elif action_name == "Copy text to clipboard":
            text = kwargs.get("text")
            if text is None:
                logger.error("Missing text for 'Copy text to clipboard'.")
                raise ValueError("Text is required for Copy text to clipboard action.")
            logger.info(f"Directly executing 'Copy text to clipboard' for text (first 30 chars): '{text[:30]}'")
            try:
                pyperclip.copy(text)
                return ActionResult(extracted_content=text)
            except Exception as e:
                logger.error(f"Error during direct execution of 'Copy text to clipboard': {e}", exc_info=True)
                raise
        
        elif action_name == "Paste text from clipboard":
            selector = kwargs.get("selector") 
            logger.info(f"Directly executing 'Paste text from clipboard' into selector: '{selector if selector else 'current focus'}'")
            try:
                text_to_paste = pyperclip.paste()
                if selector:
                    try:
                        target_element = page.locator(selector).first
                        target_element.wait_for(state="visible", timeout=3000) # SYNC
                        target_element.focus(timeout=1000) # SYNC
                        logger.info(f"Focused on selector '{selector}' for pasting.")
                    except Exception as e_focus:
                        logger.warning(f"Could not focus on selector '{selector}' for paste: {e_focus}. Pasting into current page focus.")
                page.keyboard.type(text_to_paste) # SYNC
                return ActionResult(extracted_content=text_to_paste)
            except Exception as e:
                logger.error(f"Error during direct execution of 'Paste text from clipboard': {e}", exc_info=True)
                raise
        else:
            logger.error(f"CustomControllerSync.execute received unhandled action_name: '{action_name}'. This controller only directly handles specific actions for replay.")
            # Fallback to registry if needed (this part requires careful review of browser_use registry's sync/async nature)
            # if hasattr(self.registry, 'execute_action') and callable(self.registry.execute_action):
            #     logger.info(f"Attempting fallback to self.registry.execute_action for '{action_name}'")
            #     # How self.registry.execute_action expects browser_context (sync/async) is key here.
            #     # Assuming it might need a wrapper or the BaseBrowserContext if that's what it's typed for.
            #     # This is a placeholder and might need adjustment based on browser_use library.
            #     return self.registry.execute_action(action_name, params={'browser': self.browser_context, **kwargs}) 
            raise NotImplementedError(f"CustomControllerSync.execute does not handle action: '{action_name}'.")