# -*- coding: utf-8 -*-
# @Time    : 2025/1/2
# @Author  : wenshao
# @ProjectName: browser-use-webui
# @FileName: browser.py

from browser_use.browser.browser import Browser
from browser_use.browser.context import BrowserContext, BrowserContextConfig

from .custom_context import CustomBrowserContext


class CustomBrowser(Browser):
    async def new_context(
        self,
        config: BrowserContextConfig = BrowserContextConfig(),
        context: CustomBrowserContext = None,
    ) -> BrowserContext:
        """Create a browser context"""
        return CustomBrowserContext(config=config, browser=self, context=context)