import asyncio
import pdb
import os
from pathlib import Path
from typing import Optional, Union

from playwright.async_api import Browser as PlaywrightBrowser
from playwright.async_api import (
    BrowserContext as PlaywrightBrowserContext,
)
from playwright.async_api import (
    Playwright,
    async_playwright,
)
from browser_use.browser.browser import Browser, BrowserConfig
from browser_use.browser.context import BrowserContextConfig
from playwright.async_api import BrowserContext as PlaywrightBrowserContext
import logging

from src.browser.custom_context import CustomBrowserContext
from src.browser.custom_context_config import CustomBrowserContextConfig as AppCustomBrowserContextConfig

logger = logging.getLogger(__name__)


class CustomBrowser(Browser):

    # Internal attribute to store the actual Playwright Browser or BrowserContext instance
    _actual_playwright_browser: Optional[Union[PlaywrightBrowser, PlaywrightBrowserContext]] = None
    _playwright_browser_context_manager: Optional[PlaywrightBrowserContext] = None # For persistent context

    @property
    def resolved_playwright_browser(self) -> Optional[PlaywrightBrowser]:
        """Returns the underlying Playwright Browser instance if available and is a Browser, not a Context."""
        if hasattr(self, '_actual_playwright_browser') and isinstance(self._actual_playwright_browser, PlaywrightBrowser):
            return self._actual_playwright_browser
        return None

    async def async_init(self):
        playwright = await async_playwright().start()
        self.playwright = playwright
        
        self._actual_playwright_browser = None # Initialize our internal attribute

        if self.config.cdp_url:
            logger.debug(f"Attempting to connect to existing browser via CDP: {self.config.cdp_url}")
            cdp_connection_result = None 
            try:
                cdp_connection_result = await playwright.chromium.connect_over_cdp(
                    self.config.cdp_url
                )

                if cdp_connection_result:
                    self._actual_playwright_browser = cdp_connection_result
                    logger.info( 
                        f"Successfully connected to browser over CDP: {self._actual_playwright_browser}"
                    )
                    if not self._actual_playwright_browser.contexts:
                        logger.warning(
                            "Connected to browser over CDP, but no contexts found. A page/tab might need to be open."
                        )
                else:
                    logger.warning(
                        f"Playwright's connect_over_cdp returned None or a falsy value ({cdp_connection_result}) without raising an exception. Treating as connection failure."
                    )
                    self._actual_playwright_browser = None 

            except BaseException as be: 
                logger.warning(
                    f"Failed to connect to browser over CDP ({self.config.cdp_url}). Will launch a new browser instance instead. Error type: {type(be)}, Error: {be}", exc_info=True 
                )
                self._actual_playwright_browser = None

        if self._actual_playwright_browser is None and self.config.chrome_instance_path and "Google Chrome" in self.config.chrome_instance_path:
            user_data_dir = None
            if hasattr(self.config, 'extra_chromium_args') and self.config.extra_chromium_args:
                for arg in self.config.extra_chromium_args:
                    if arg.startswith('--user-data-dir='):
                        user_data_dir = arg.split('=')[1]
                        break
            
            if user_data_dir:
                launch_args = [
                    arg for arg in getattr(self.config, 'extra_chromium_args', [])
                    if not arg.startswith('--user-data-dir=')
                ]
                logger.debug(f"Launching persistent Chrome context with UserDataDir: {user_data_dir} and args: {launch_args}")
                try:
                    # When launching persistent context, playwright returns a BrowserContext, not a Browser.
                    # The context manager itself becomes the primary object to interact with.
                    self._playwright_browser_context_manager = await playwright.chromium.launch_persistent_context(
                        user_data_dir=user_data_dir,
                        headless=self.config.headless,
                        args=launch_args,
                        channel="chrome"
                    )
                    self._actual_playwright_browser = self._playwright_browser_context_manager # Store the context here
                    logger.info(f"Launched persistent Chrome. Stored BrowserContext: {self._actual_playwright_browser}")
                except Exception as e_persistent_launch:
                    logger.error(f"Failed to launch persistent Chrome context with UserDataDir '{user_data_dir}': {e_persistent_launch}", exc_info=True)
                    self._actual_playwright_browser = None
                    if hasattr(self, '_playwright_browser_context_manager'):
                        self._playwright_browser_context_manager = None

            else:
                logger.debug(f"Attempting to launch new Chrome browser instance via executable_path: {self.config.chrome_instance_path} with args: {self.config.extra_chromium_args}")
                try:
                    self._actual_playwright_browser = await playwright.chromium.launch(
                        executable_path=self.config.chrome_instance_path,
                        headless=self.config.headless,
                        args=self.config.extra_chromium_args
                    )
                    if self._actual_playwright_browser:
                        logger.info(f"Launched Chrome via executable_path. Browser: {self._actual_playwright_browser}, Connected: {self._actual_playwright_browser.is_connected()}")
                    else:
                        logger.warning(f"Launching Chrome via executable_path '{self.config.chrome_instance_path}' returned a None browser object.")
                        self._actual_playwright_browser = None
                except Exception as e_chrome_launch:
                    logger.error(f"Failed to launch Chrome via executable_path '{self.config.chrome_instance_path}': {e_chrome_launch}", exc_info=True)
                    self._actual_playwright_browser = None
        
        if self._actual_playwright_browser is None:
            logger.debug(f"Launching new default (Chromium) browser instance as fallback, with args: {self.config.extra_chromium_args}")
            try:
                self._actual_playwright_browser = await playwright.chromium.launch(
                    headless=self.config.headless,
                    args=self.config.extra_chromium_args
                )
                if self._actual_playwright_browser:
                    logger.info(f"Launched default Chromium as fallback. Browser: {self._actual_playwright_browser}, Connected: {self._actual_playwright_browser.is_connected()}")
                else:
                    logger.warning("Launching default Chromium as fallback returned a None browser object.")
                    self._actual_playwright_browser = None
            except Exception as e_default_launch:
                logger.error(f"Failed to launch default Chromium as fallback: {e_default_launch}", exc_info=True)
                self._actual_playwright_browser = None
        
        if self._actual_playwright_browser:
            if isinstance(self._actual_playwright_browser, PlaywrightBrowser):
                if self._actual_playwright_browser.is_connected():
                    logger.info(f"Playwright Browser successfully initialized and connected: {self._actual_playwright_browser}")
                else:
                    logger.error(f"Playwright Browser initialized but not connected. Browser: {self._actual_playwright_browser}")
                    self._actual_playwright_browser = None
            elif isinstance(self._actual_playwright_browser, PlaywrightBrowserContext):
                try:
                    if self._actual_playwright_browser.pages is not None: 
                         logger.info(f"Playwright BrowserContext successfully initialized (from persistent launch): {self._actual_playwright_browser}")
                    else: 
                         logger.error(f"Playwright BrowserContext initialized, but .pages is None. Context: {self._actual_playwright_browser}")
                         self._actual_playwright_browser = None
                except Exception as e_context_check: 
                    logger.error(f"Playwright BrowserContext is invalid or closed: {e_context_check}. Context: {self._actual_playwright_browser}", exc_info=True)
                    self._actual_playwright_browser = None
            else:
                logger.error(f"self._actual_playwright_browser is of unexpected type: {type(self._actual_playwright_browser)}. Value: {self._actual_playwright_browser}")
                self._actual_playwright_browser = None
        else:
            logger.error(f"All browser initialization attempts failed. Final state of self._actual_playwright_browser is None.")

    async def reuse_existing_context(self,
                                   config: Optional[AppCustomBrowserContextConfig] = None # Add optional config param
                                   ) -> Optional[CustomBrowserContext]: # Return Optional CustomBrowserContext
        from playwright.async_api import Browser as PlaywrightBrowser, BrowserContext as PlaywrightBrowserContext
        # Ensure CustomBrowserContext is imported for return type hinting and usage
        from src.browser.custom_context import CustomBrowserContext 

        if not self._actual_playwright_browser: 
            logger.warning("reuse_existing_context called on uninitialized browser. Attempting init.")
            await self.async_init()
            if not self._actual_playwright_browser: 
                logger.error("Browser not initialized after attempt in reuse_existing_context. Cannot reuse context.")
                return None # Explicitly return None on failure

        base_ctx_to_wrap = None
        if isinstance(self._actual_playwright_browser, PlaywrightBrowser):
            pw_browser_instance = self._actual_playwright_browser 
            logger.debug(f"Connected PlaywrightBrowser has {len(pw_browser_instance.contexts)} contexts for potential reuse.")
            found_context_with_pages = False
            for i, ctx in enumerate(pw_browser_instance.contexts):
                logger.debug(f"  Context [{i}]: {ctx} has {len(ctx.pages)} pages.")
                for j, page in enumerate(ctx.pages):
                    logger.debug(f"    Page [{j}] URL: {page.url}")
                if not found_context_with_pages and len(ctx.pages) > 0:
                    base_ctx_to_wrap = ctx
                    found_context_with_pages = True
                    logger.debug(f"Selecting Context [{i}] as it has pages.")
            
            if not base_ctx_to_wrap:
                if pw_browser_instance.contexts:
                    logger.warning("No context with pages found. Defaulting to the first context.")
                    base_ctx_to_wrap = pw_browser_instance.contexts[0]
                else: 
                    logger.error("No contexts found in the connected PlaywrightBrowser after attempting to connect.")
                    raise RuntimeError("No contexts found in existing browser to reuse after connection.")

        elif isinstance(self._actual_playwright_browser, PlaywrightBrowserContext):
            base_ctx_to_wrap = self._actual_playwright_browser 
            logger.debug(f"Reusing existing PlaywrightBrowserContext directly with {len(base_ctx_to_wrap.pages)} pages. Context: {base_ctx_to_wrap}")
        else:
            logger.error(f"_actual_playwright_browser is of unexpected type: {type(self._actual_playwright_browser)}. Cannot determine context to reuse.")
            return None # Return None on type error

        # Determine the config to use for the CustomBrowserContext wrapper
        config_to_use = config if config is not None else AppCustomBrowserContextConfig() # Use provided or default

        logger.debug(f"Wrapping Playwright context {base_ctx_to_wrap} with CustomBrowserContext using config: {config_to_use}")
        return CustomBrowserContext.from_existing(
            pw_context=base_ctx_to_wrap,
            browser=self, 
            config=config_to_use 
        )

    async def new_context(
            self,
            config: AppCustomBrowserContextConfig = AppCustomBrowserContextConfig()
    ) -> "CustomBrowserContext":
        
        if not hasattr(self, '_actual_playwright_browser') or not self._actual_playwright_browser:
            logger.error("Playwright browser/context holder not initialized. Call async_init() first.")
            await self.async_init()
            if not hasattr(self, '_actual_playwright_browser') or not self._actual_playwright_browser:
                 raise RuntimeError("Failed to initialize Playwright browser/context holder in new_context.")

        if isinstance(self._actual_playwright_browser, PlaywrightBrowserContext):
            logger.warning("Creating new context from an existing persistent PlaywrightBrowserContext. This might indicate an architectural issue if multiple isolated contexts are expected from a persistent launch.")
            playwright_context_to_wrap = self._actual_playwright_browser 
            logger.debug(f"Reusing persistent Playwright context: {playwright_context_to_wrap}")

        elif isinstance(self._actual_playwright_browser, PlaywrightBrowser):
            pw_browser_instance = self._actual_playwright_browser # For clarity
            options = {}
            if config.trace_path:
                pass # Tracing is started on the context later

            if config.save_recording_path:
                options["record_video_dir"] = config.save_recording_path
                options["record_video_size"] = {"width": config.browser_window_size["width"], "height": config.browser_window_size["height"]}

            if not config.no_viewport and config.browser_window_size:
                 options["viewport"] = {"width": config.browser_window_size["width"], "height": config.browser_window_size["height"]}
            else:
                options["no_viewport"] = True
            
            logger.debug(f"Creating new Playwright context with options: {options} from PlaywrightBrowser: {pw_browser_instance}")
            playwright_context_to_wrap = await pw_browser_instance.new_context(**options)
        else:
            logger.error(f"_actual_playwright_browser is of unexpected type: {type(self._actual_playwright_browser)}. Cannot create new context.")
            raise TypeError(f"_actual_playwright_browser is neither PlaywrightBrowser nor PlaywrightBrowserContext.")

        from src.browser.custom_context import CustomBrowserContext as CBC_in_CustomBrowser
        print(f"DEBUG_INIT: ID of CustomBrowserContext class in custom_browser.py: {id(CBC_in_CustomBrowser)}")

        custom_context = CBC_in_CustomBrowser(
            pw_context=playwright_context_to_wrap,
            browser=self,
            config=config
        )
        print(f"DEBUG_INIT: Type of CREATED context in custom_browser.py: {type(custom_context)}, ID of its type: {id(type(custom_context))}")
        
        if config.trace_path and playwright_context_to_wrap:
            try:
                await playwright_context_to_wrap.tracing.start(screenshots=True, snapshots=True, sources=True)
                logger.debug(f"Context tracing started. Saving to host path: {config.trace_path}")
            except Exception as e:
                logger.error(f"Failed to start tracing: {e}")

        return custom_context

    async def close(self):
        # Close the persistent context manager if it exists and is distinct
        if hasattr(self, '_playwright_browser_context_manager') and self._playwright_browser_context_manager is not None:
            logger.info("Closing persistent Playwright context manager (which is a BrowserContext).")
            context_manager_to_close = self._playwright_browser_context_manager
            assert context_manager_to_close is not None
            await context_manager_to_close.close()
            self._playwright_browser_context_manager = None
        
        # Close the main browser/context object stored in _actual_playwright_browser
        if hasattr(self, '_actual_playwright_browser') and self._actual_playwright_browser is not None:
            browser_or_context_to_close = self._actual_playwright_browser
            assert browser_or_context_to_close is not None

            # If _actual_playwright_browser was the same as _playwright_browser_context_manager and already closed, skip
            if browser_or_context_to_close == self._playwright_browser_context_manager and self._playwright_browser_context_manager is None:
                logger.info("Actual browser/context object was the persistent context manager and is already closed.")
            elif isinstance(browser_or_context_to_close, PlaywrightBrowserContext):
                 logger.info("Closing PlaywrightBrowserContext stored in _actual_playwright_browser.")
                 await browser_or_context_to_close.close()
            elif isinstance(browser_or_context_to_close, PlaywrightBrowser):
                 if browser_or_context_to_close.is_connected():
                     logger.info("Closing PlaywrightBrowser stored in _actual_playwright_browser.")
                     await browser_or_context_to_close.close()
                 else:
                     logger.info("PlaywrightBrowser in _actual_playwright_browser is not connected or already closed.")
            else:
                 logger.info(f"_actual_playwright_browser ({type(browser_or_context_to_close)}) is not a PlaywrightBrowser or PlaywrightBrowserContext that can be closed here, or is already closed.")
            self._actual_playwright_browser = None # Clear the internal attribute
        
        if hasattr(self, 'playwright') and self.playwright is not None:
            logger.info("Stopping Playwright.")
            await self.playwright.stop()
            self.playwright = None
        logger.info("CustomBrowser closed.")