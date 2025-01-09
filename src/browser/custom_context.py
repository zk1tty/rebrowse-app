# -*- coding: utf-8 -*-
# @Time    : 2025/1/1
# @Author  : wenshao
# @Email   : wenshaoguo1026@gmail.com
# @Project : browser-use-webui
# @FileName: context.py

import json
import logging
import os

from playwright.async_api import Browser as PlaywrightBrowser, Page, BrowserContext as PlaywrightContext
from browser_use.browser.browser import Browser
from browser_use.browser.context import BrowserContext, BrowserContextConfig

logger = logging.getLogger(__name__)
class CustomBrowserContext(BrowserContext):
    def __init__(
        self,
        browser: "CustomBrowser",  # Forward declaration for CustomBrowser
        config: BrowserContextConfig = BrowserContextConfig(),
        context: PlaywrightContext = None
    ):
        super(CustomBrowserContext, self).__init__(browser=browser, config=config)
        self.context = context  # Rename to avoid confusion
        self._page = None

    @property
    def impl_context(self) -> PlaywrightContext:
        """Returns the underlying Playwright context implementation"""
        return self.context

    async def _create_context(self, browser: PlaywrightBrowser = None):
        """Creates a new browser context with anti-detection measures and loads cookies if available."""
        if self.context:
            return self.context

        # If a Playwright browser is not provided, get it from our custom browser
        pw_browser = browser or await self.browser.get_playwright_browser()
        
        context_args = {
            'viewport': self.config.browser_window_size,
            'no_viewport': False, 
            'bypass_csp': self.config.disable_security,
            'ignore_https_errors': self.config.disable_security
        }
        
        if self.config.save_recording_path:
            context_args.update({
                'record_video_dir': self.config.save_recording_path,
                'record_video_size': self.config.browser_window_size
            })

        self.context = await pw_browser.new_context(**context_args)

        if self.config.trace_path:
            await self.context.tracing.start(screenshots=True, snapshots=True, sources=True)

        # Load cookies if they exist
        if self.config.cookies_file and os.path.exists(self.config.cookies_file):
            with open(self.config.cookies_file, "r") as f:
                cookies = json.load(f)
                logger.info(
                    f"Loaded {len(cookies)} cookies from {self.config.cookies_file}"
                )
                await self.context.add_cookies(cookies)

        # Expose anti-detection scripts
        await self.context.add_init_script(
            """
            // Webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // Languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });

            // Plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });

            // Chrome runtime
            window.chrome = { runtime: {} };

            // Permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            """
        )

        # Create an initial page
        self._page = await self.context.new_page()
        await self._page.goto('about:blank')  # Ensure page is ready
        
        return self.context

    async def new_page(self) -> Page:
        """Creates and returns a new page in this context"""
        if not self.context:
            await self._create_context()
        return await self.context.new_page()

    async def __aenter__(self):
        if not self.context:
            await self._create_context()
        return self

    async def __aexit__(self, *args):
        if self.context:
            await self.context.close()
            self.context = None

    @property
    def pages(self):
        """Returns list of pages in context"""
        return self.context.pages if self.context else []

    async def get_state(self, **kwargs):
        if self.context:
            pages = self.context.pages
            if pages:
                return await super().get_state(**kwargs)
        return None

    async def get_pages(self):
        """Get pages in a way that works"""
        if not self.context:
            return []
        return self.context.pages
