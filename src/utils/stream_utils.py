import base64
import asyncio
from typing import AsyncGenerator
from playwright.async_api import BrowserContext, Error as PlaywrightError

async def capture_screenshot(browser_context) -> str:
    """Capture and encode a screenshot"""
    try:
        # Get the implementation context - handle both direct Playwright context and wrapped context
        context = browser_context
        if hasattr(browser_context, 'context'):
            context = browser_context.context
        
        if not context:
            return "<div>No browser context available</div>"
            
        # Get all pages
        pages = context.pages
        if not pages:
            return "<div>Waiting for page to be available...</div>"

        # Use the first non-blank page or fallback to first page
        active_page = None
        for page in pages:
            if page.url != 'about:blank':
                active_page = page
                break
        
        if not active_page and pages:
            active_page = pages[0]
            
        if not active_page:
            return "<div>No active page available</div>"

        # Take screenshot
        try:
            screenshot = await active_page.screenshot(
                type='jpeg',
                quality=75,
                scale="css"
            )
            encoded = base64.b64encode(screenshot).decode('utf-8')
            return f'<img src="data:image/jpeg;base64,{encoded}" style="width:100%; max-width:1200px; border:1px solid #ccc;">'
        except Exception as e:
            return f"<div class='error'>Screenshot failed: {str(e)}</div>"
            
    except Exception as e:
        return f"<div class='error'>Screenshot error: {str(e)}</div>"