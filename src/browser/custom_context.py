# -*- coding: utf-8 -*-
# @Time    : 2025/1/1
# @Author  : wenshao
# @Email   : wenshaoguo1026@gmail.com
# @Project : browser-use-webui
# @FileName: custom_context.py

import json
import logging
import os
from typing import TYPE_CHECKING

from playwright.async_api import Browser as PlaywrightBrowser, Page, BrowserContext as PlaywrightContext
from browser_use.browser.context import BrowserContext, BrowserContextConfig

if TYPE_CHECKING:
    from .custom_browser import CustomBrowser

logger = logging.getLogger(__name__)

class CustomBrowserContext(BrowserContext):
    def __init__(
            self,
            browser: 'CustomBrowser',  # Forward declaration for CustomBrowser
            config: BrowserContextConfig = BrowserContextConfig(),
            context: 'PlaywrightContext | None' = None
    ):
        super().__init__(browser=browser, config=config)  # Add proper inheritance
        self._impl_context = context  # Rename to avoid confusion
        self._page = None
        self.session = None  # Add session attribute

    @property
    def impl_context(self) -> PlaywrightContext:
        """Returns the underlying Playwright context implementation"""
        if self._impl_context is None:
            raise RuntimeError("Browser context has not been initialized")
        return self._impl_context

    async def _create_context(self, config: BrowserContextConfig | None = None):
        """Creates a new browser context"""
        if self._impl_context:
            return self._impl_context

        # Get the Playwright browser from our custom browser
        pw_browser = await self.browser.get_playwright_browser()
        
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

        self._impl_context = await pw_browser.new_context(**context_args)
        
        # Create an initial page
        self._page = await self._impl_context.new_page()
        await self._page.goto('about:blank')  # Ensure page is ready
        
        return self._impl_context

    async def new_page(self) -> Page:
        """Creates and returns a new page in this context"""
        context = await self._create_context()
        return await context.new_page()

    async def __aenter__(self):
        if not self._impl_context:
            await self._create_context()
        return self

    async def __aexit__(self, *args):
        if self._impl_context:
            await self._impl_context.close()
            self._impl_context = None

    @property
    def pages(self):
        """Returns list of pages in context"""
        return self._impl_context.pages if self._impl_context else []

    async def get_state(self, **kwargs):
        if self._impl_context:
            # pages() is a synchronous property, not an async method:
            pages = self._impl_context.pages
            if pages:
                return await super().get_state(**kwargs)
        return None

    async def get_pages(self):
        """Get pages in a way that works"""
        if not self._impl_context:
            return []
        # Again, pages() is a property:
        return self._impl_context.pages