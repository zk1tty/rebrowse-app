# -*- coding: utf-8 -*-
# @Time    : 2025/1/2
# @Author  : wenshao
# @ProjectName: browser-use-webui
# @FileName: custom_browser.py

import logging
from playwright.async_api import Playwright, Browser as PlaywrightBrowser, async_playwright
from browser_use.browser.browser import Browser, BrowserConfig
from browser_use.browser.context import BrowserContextConfig, BrowserContext
from .custom_context import CustomBrowserContext

logger = logging.getLogger(__name__)

class CustomBrowser(Browser):
    async def new_context(
        self,
        config: BrowserContextConfig = BrowserContextConfig(),
        context=None,
    ) -> BrowserContext:
        """Create a browser context with custom implementation"""
        return CustomBrowserContext(config=config, browser=self, context=context)

    async def _init(self):
        """Initialize the browser session"""
        playwright = await async_playwright().start()
        browser = await self._setup_browser(playwright)

        self.playwright = playwright
        self.playwright_browser = browser

        return self.playwright_browser

    async def _setup_browser(self, playwright: Playwright) -> PlaywrightBrowser:
        """Sets up and returns a Playwright Browser instance with anti-detection measures."""
        try:
            disable_security_args = []
            if self.config.disable_security:
                disable_security_args = [
                    '--disable-web-security',
                    '--disable-site-isolation-trials',
                    '--disable-features=IsolateOrigins,site-per-process',
                ]

            browser = await playwright.chromium.launch(
                headless=self.config.headless,
                args=[
                    '--no-sandbox',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-infobars',
                    '--disable-background-timer-throttling',
                    '--disable-popup-blocking',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding',
                    '--disable-window-activation',
                    '--disable-focus-on-load',
                    '--no-first-run',
                    '--no-default-browser-check',
                    '--no-startup-window',
                    '--window-position=0,0',
                ]
                + disable_security_args
                + self.config.extra_chromium_args,
                proxy=self.config.proxy,
            )

            return browser
        except Exception as e:
            logger.error(f'Failed to initialize Playwright browser: {str(e)}')
            raise

    async def get_playwright_browser(self) -> PlaywrightBrowser:
        """Get a browser context"""
        if self.playwright_browser is None:
            return await self._init()

        return self.playwright_browser

    async def close(self):
        """Close the browser instance"""
        try:
            if self.playwright_browser:
                await self.playwright_browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            logger.debug(f'Failed to close browser properly: {e}')
        finally:
            self.playwright_browser = None
            self.playwright = None
