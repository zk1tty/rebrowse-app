import pdb
import pyperclip
from pathlib import Path
import shutil
from typing import Optional, Type
from pydantic import BaseModel
from browser_use.agent.views import ActionResult
from browser_use.browser.context import BrowserContext
from browser_use.controller.service import Controller, DoneAction
from main_content_extractor import MainContentExtractor
from browser_use.controller.views import (
    ClickElementAction,
    DoneAction,
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

class CustomController(Controller):
    """A controller that extends browser_use controllerfunctionality.

    Attributes:
        exclude_actions (list[str]): List of actions to exclude from the controller.
        output_model (Optional[Type[BaseModel]]): Optional custom output model for the controller.
        browser_context (Optional[BrowserContext]): The browser context this controller operates on.

    Features:
        - Clipboard operations (copy/paste)
        - Browser keyboard simulation
        - Standard browser actions
        - Action exclusion capability
        - Custom output model support
    """
    def __init__(self, 
                 browser_context: Optional[BrowserContext] = None,
                 exclude_actions: list[str] = [],
                 output_model: Optional[Type[BaseModel]] = None
                 ):
        super().__init__(exclude_actions=exclude_actions, output_model=output_model)
        self.browser_context = browser_context
        self._register_custom_actions()

    # TRY: clipboard actions
    def _register_custom_actions(self):
        """Register all custom browser actions"""

        @self.registry.action("Copy text to clipboard")
        def copy_to_clipboard(text: str):
            pyperclip.copy(text)
            return ActionResult(extracted_content=text)

        @self.registry.action("Paste text from clipboard")
        async def paste_from_clipboard(browser: BrowserContext, selector: str | None = None):
            text = pyperclip.paste()
            page = await browser.get_current_page()
            if selector:
                try:
                    target_element = page.locator(selector).first
                    # Ensure element is ready before trying to interact
                    await target_element.wait_for(state="visible", timeout=3000) 
                    await target_element.focus(timeout=1000)
                    logger.info(f"Focused on selector '{selector}' for pasting.")
                except Exception as e:
                    logger.warning(f"Could not focus on selector '{selector}' for paste: {e}. Pasting into current focus.")
            
            # Types into the focused element (either the one from selector or pre-existing focus)
            await page.keyboard.type(text)
            return ActionResult(extracted_content=text)

        @self.registry.action("Upload local file")
        async def upload_local_file(browser: BrowserContext, selector: str, file_path: str):
            page = await browser.get_current_page()
            await page.locator(selector).set_input_files(file_path)
            return ActionResult(extracted_content=file_path)

        @self.registry.action("Download remote file")
        async def download_remote_file(browser: BrowserContext, url: str, dest_dir: str, trigger_selector: str|None=None):
            page = await browser.get_current_page()
            async with page.expect_download() as dl_info:
                if trigger_selector:
                    await page.locator(trigger_selector).click()
                else:
                    # If no trigger selector, assume direct navigation initiates download
                    # This might need adjustment if direct navigation doesn't always trigger a download for the given URL.
                    await page.goto(url) # Consider if this should be page.goto(download_url_param) or similar
            dl = await dl_info.value
            # Ensure dest_dir exists, create if not (though Path.mkdir parents=True would also work)
            # For simplicity, assuming dest_dir is a valid, existing directory or will be handled by user.
            target = Path(dest_dir).expanduser() / dl.suggested_filename
            await dl.save_as(target)
            return ActionResult(extracted_content=str(target))

    async def execute(self, action_name: str, **kwargs):
        """
        This method is called by TraceReplayer.
        It directly implements the actions it knows how to replay, bypassing browser_use's execute_action.
        """
        logger.debug(f"CustomController.execute CALLED for action: '{action_name}', args: {kwargs}")

        if not hasattr(self, 'browser_context') or not self.browser_context:
            logger.error("CustomController.execute: self.browser_context is not available. Action cannot be executed.")
            raise RuntimeError("CustomController.browser_context not set. Controller needs a BrowserContext to execute actions.")

        page = await self.browser_context.get_current_page() # Get Playwright page from our CustomBrowserContext
        if not page:
            logger.error("CustomController.execute: Could not get current page from browser_context.")
            raise RuntimeError("Failed to get current page for action execution.")

        if action_name == "Upload local file":
            selector = kwargs.get("selector")
            file_path = kwargs.get("file_path")
            if not selector or not file_path:
                logger.error(f"Missing selector or file_path for 'Upload local file'. Got: selector='{selector}', file_path='{file_path}'")
                raise ValueError("Selector and file_path are required for Upload local file action.")
            
            logger.info(f"Directly executing 'Upload local file': selector='{selector}', file_path='{file_path}'")
            try:
                await page.locator(selector).set_input_files(file_path)
                logger.info(f"Successfully set input files for selector '{selector}' with path '{file_path}'")
                # ActionResult is part of browser_use, but replayer may not use the return value directly.
                # For consistency with other actions if they were from browser_use, we can return it.
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

            original_url_for_logging = kwargs.get("url", "N/A") # Get original URL if present, just for logging
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
            selector = kwargs.get("selector") # Optional for paste
            logger.info(f"Directly executing 'Paste text from clipboard' into selector: '{selector if selector else 'current focus'}'")
            try:
                text_to_paste = pyperclip.paste()
                if selector:
                    try:
                        target_element = page.locator(selector).first
                        await target_element.wait_for(state="visible", timeout=3000)
                        await target_element.focus(timeout=1000)
                        logger.info(f"Focused on selector '{selector}' for pasting.")
                    except Exception as e_focus:
                        logger.warning(f"Could not focus on selector '{selector}' for paste: {e_focus}. Pasting into current page focus.")
                await page.keyboard.type(text_to_paste)
                return ActionResult(extracted_content=text_to_paste)
            except Exception as e:
                logger.error(f"Error during direct execution of 'Paste text from clipboard': {e}", exc_info=True)
                raise

        # Add other direct action handlers here if TraceReplayer calls them
        # via controller.execute("Some Other Action", ...)

        else:
            logger.error(f"CustomController.execute received unhandled action_name: '{action_name}'. This controller only directly handles specific actions for replay.")
            # If you want to try falling back to browser_use registry for other actions:
            # if hasattr(self.registry, 'execute_action') and callable(self.registry.execute_action):
            #     logger.info(f"Falling back to self.registry.execute_action for '{action_name}'")
            #     return await self.registry.execute_action(action_name, params={'browser': self.browser_context, **kwargs})
            raise NotImplementedError(f"CustomController.execute does not handle action: '{action_name}'.")