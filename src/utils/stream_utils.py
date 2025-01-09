import base64
import asyncio
from typing import AsyncGenerator
from playwright.async_api import BrowserContext, Error as PlaywrightError

async def capture_screenshot(browser_context: BrowserContext) -> str:
    """Capture and encode a screenshot"""
    try:
        # Get the implementation context
        context = getattr(browser_context, 'impl_context', None)
        if not context:
            return "<div>No browser context implementation available</div>"
            
        # Get all pages
        all_pages = context.pages
        if not all_pages:
            return "<div>Waiting for page to be available...</div>"
        # Use the first page
        page = all_pages[1]
        try:
            screenshot = await page.screenshot(
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