# -*- coding: utf-8 -*-
# @Time    : 2025/1/1
# @Author  : wenshao
# @Email   : wenshaoguo1026@gmail.com
# @Project : browser-use-webui
# @FileName: context.py

import json
import logging
import os

from browser_use.browser.browser import Browser
from browser_use.browser.context import BrowserContext, BrowserContextConfig
from playwright.async_api import Browser as PlaywrightBrowser
from playwright.async_api import BrowserContext as PlaywrightBrowserContext

from .config import BrowserPersistenceConfig

logger = logging.getLogger(__name__)


class CustomBrowserContext(BrowserContext):
    def __init__(
        self,
        browser: "Browser",
        config: BrowserContextConfig = BrowserContextConfig(),
        context: PlaywrightBrowserContext = None,
    ):
        super(CustomBrowserContext, self).__init__(browser=browser, config=config)
        self.context = context
        self._page = None
        self._persistence_config = BrowserPersistenceConfig.from_env()

    @property
    def impl_context(self) -> PlaywrightBrowserContext:
        """Returns the underlying Playwright context implementation"""
        return self.context

    async def _create_context(self, browser: PlaywrightBrowser) -> PlaywrightBrowserContext:
        """Creates a new browser context with anti-detection measures and loads cookies if available."""
        if self.context:
            logger.info("Browser context already exists, returning existing context.")
            return self.context

        # Check for persistent context
        if self._persistence_config.persistent_session and len(browser.contexts) > 0:
            logger.info("Using existing persistent context.")
            self.context = browser.contexts[0]
        else:
            logger.info("Creating a new browser context.")
            self.context = await browser.new_context(
                viewport=self.config.browser_window_size,
                no_viewport=False,
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36"
                ),
                java_script_enabled=True,
                bypass_csp=self.config.disable_security,
                ignore_https_errors=self.config.disable_security,
                record_video_dir=self.config.save_recording_path,
                record_video_size=self.config.browser_window_size,
            )

        # Handle tracing
        if self.config.trace_path:
            await self.context.tracing.start(screenshots=True, snapshots=True, sources=True)

        # Load cookies
        if self.config.cookies_file and os.path.exists(self.config.cookies_file):
            with open(self.config.cookies_file, "r") as f:
                cookies = json.load(f)
                logger.info(f"Loaded {len(cookies)} cookies from {self.config.cookies_file}.")
                await self.context.add_cookies(cookies)

        # Inject anti-detection scripts
        await self.context.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            window.chrome = { runtime: {} };
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            """
        )

        # Create initial page if none exists
        if not self.context.pages:
            self._page = await self.context.new_page()
            await self._page.goto('about:blank')

        return self.context

    async def new_page(self):
        """Creates and returns a new page in this context."""
        if not self.context:
            await self._create_context(await self.browser.get_playwright_browser())
        return await self.context.new_page()

    async def get_current_page(self):
        """Returns the current page or creates one if none exists."""
        if not self.context:
            await self._create_context(await self.browser.get_playwright_browser())
        pages = self.context.pages
        if not pages:
            logger.warning("No existing pages in the context. Creating a new page.")
            return await self.context.new_page()
        return pages[0]

    async def close(self):
        """Override close to respect persistence setting."""
        if not self._persistence_config.persistent_session and self.context:
            await self.context.close()
            self.context = None

    @property
    def pages(self):
        """Returns list of pages in the context."""
        if not self.context:
            logger.warning("Attempting to access pages but context is not initialized.")
            return []
        return self.context.pages
