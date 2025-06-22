import asyncio
import base64
from pathlib import Path
from typing import Optional
from browser_use import Browser
from browser_use.browser.browser import BrowserProfile

def get_rebrowse_logo_data_url() -> Optional[str]:
    """Convert the local rebrowse.png to a data URL for use in the browser"""
    try:
        # Try multiple potential locations for rebrowse.png
        possible_paths = [
            Path("rebrowse.png"),  # Current directory
            Path("../rebrowse.png"),  # Parent directory
            Path("../../rebrowse.png"),  # Project root
            Path(__file__).parent / "rebrowse.png",  # Same as script
            Path(__file__).parent.parent / "rebrowse.png",  # One level up
        ]
        
        logo_path = None
        for path in possible_paths:
            if path.exists():
                logo_path = path
                break
        
        if not logo_path:
            print("ℹ️ rebrowse.png not found, using text logo")
            return None
        
        # Read the image file and convert to base64
        with open(logo_path, "rb") as image_file:
            image_data = image_file.read()
            base64_data = base64.b64encode(image_data).decode('utf-8')
            
        # Create data URL
        data_url = f"data:image/png;base64,{base64_data}"
        print(f"✅ Loaded rebrowse.png logo ({len(image_data)} bytes)")
        return data_url
        
    except Exception as e:
        print(f"ℹ️ Using text logo (rebrowse.png not available: {e})")
        return None

async def show_custom_dvd_screensaver(page, logo_url: Optional[str] = None, logo_text: str = "REBROWSE") -> None:
    """Custom simple ASCII logo screensaver"""
    # ASCII art logo for REBROWSE
    ascii_logo = """
██████╗ ███████╗██████╗ ██████╗  ██████╗ ██╗    ██╗███████╗███████╗
██╔══██╗██╔════╝██╔══██╗██╔══██╗██╔═══██╗██║    ██║██╔════╝██╔════╝
██████╔╝█████╗  ██████╔╝██████╔╝██║   ██║██║ █╗ ██║███████╗█████╗  
██╔══██╗██╔══╝  ██╔══██╗██╔══██╗██║   ██║██║███╗██║╚════██║██╔══╝  
██║  ██║███████╗██████╔╝██║  ██║╚██████╔╝╚███╔███╔╝███████║███████╗
╚═╝  ╚═╝╚══════╝╚═════╝ ╚═╝  ╚═╝ ╚═════╝  ╚══╝╚══╝ ╚══════╝╚══════╝
    """

    await page.evaluate(f"""() => {{
        document.title = 'Rebrowse - Setting up...';

        // Remove any existing loading animation
        const existing = document.getElementById('pretty-loading-animation');
        if (existing) existing.remove();

        // Create the main overlay
        const loadingOverlay = document.createElement('div');
        loadingOverlay.id = 'pretty-loading-animation';
        loadingOverlay.style.position = 'fixed';
        loadingOverlay.style.top = '0';
        loadingOverlay.style.left = '0';
        loadingOverlay.style.width = '100vw';
        loadingOverlay.style.height = '100vh';
        loadingOverlay.style.background = 'linear-gradient(135deg, #ff69b4 0%, #ff1493 50%, #da70d6 100%)';
        loadingOverlay.style.zIndex = '99999';
        loadingOverlay.style.overflow = 'hidden';
        loadingOverlay.style.display = 'flex';
        loadingOverlay.style.alignItems = 'center';
        loadingOverlay.style.justifyContent = 'center';
        loadingOverlay.style.flexDirection = 'column';

        // Create the ASCII logo container
        const logoContainer = document.createElement('pre');
        logoContainer.textContent = `{ascii_logo}`;
        logoContainer.style.color = '#ffffff';
        logoContainer.style.fontFamily = 'monospace';
        logoContainer.style.fontSize = '16px';
        logoContainer.style.lineHeight = '1.2';
        logoContainer.style.textAlign = 'center';
        logoContainer.style.margin = '0';
        logoContainer.style.padding = '20px';
        logoContainer.style.textShadow = '0 0 10px rgba(255, 255, 255, 0.8), 0 0 20px rgba(255, 105, 180, 0.6)';
        logoContainer.style.animation = 'pulse 2s ease-in-out infinite';

        // Create subtitle
        const subtitle = document.createElement('div');
        subtitle.textContent = 'Setting up browser automation...';
        subtitle.style.color = '#ffffff';
        subtitle.style.fontFamily = 'Arial, sans-serif';
        subtitle.style.fontSize = '18px';
        subtitle.style.marginTop = '20px';
        subtitle.style.textAlign = 'center';
        subtitle.style.opacity = '0.9';
        subtitle.style.textShadow = '0 0 5px rgba(255, 255, 255, 0.5)';

        loadingOverlay.appendChild(logoContainer);
        loadingOverlay.appendChild(subtitle);
        document.body.appendChild(loadingOverlay);

        // Add pulse animation CSS
        const style = document.createElement('style');
        style.textContent = `
            @keyframes pulse {{
                0% {{ 
                    text-shadow: 0 0 10px rgba(255, 255, 255, 0.8), 0 0 20px rgba(255, 105, 180, 0.6);
                    transform: scale(1);
                }}
                50% {{ 
                    text-shadow: 0 0 15px rgba(255, 255, 255, 1), 0 0 30px rgba(255, 105, 180, 0.8);
                    transform: scale(1.02);
                }}
                100% {{ 
                    text-shadow: 0 0 10px rgba(255, 255, 255, 0.8), 0 0 20px rgba(255, 105, 180, 0.6);
                    transform: scale(1);
                }}
            }}
        `;
        document.head.appendChild(style);
    }}""")

def patch_browser_use_screensaver(logo_url: Optional[str] = None, logo_text: str = "REBROWSE"):
    """Monkey patch the browser-use screensaver function with our custom one"""
    try:
        from browser_use.browser.session import BrowserSession
        
        # Store the original function
        original_func = getattr(BrowserSession, '_show_dvd_screensaver_loading_animation', None)
        if original_func and not hasattr(BrowserSession, '_original_show_dvd_screensaver'):
            setattr(BrowserSession, '_original_show_dvd_screensaver', original_func)
        
        # Replace with our custom function
        async def custom_screensaver(self, page):
            await show_custom_dvd_screensaver(page, logo_url, logo_text)
        
        setattr(BrowserSession, '_show_dvd_screensaver_loading_animation', custom_screensaver)
        
        logo_info = logo_url or "rebrowse.png (auto)" if get_rebrowse_logo_data_url() else logo_text
        print(f"🌸 Custom Rebrowse screensaver enabled! Logo: {logo_info}")
        
    except ImportError as e:
        print(f"⚠️ Could not patch screensaver: {e}")
    except Exception as e:
        print(f"⚠️ Screensaver patch error: {e}")

async def example_workflow():
    """Example of using the browser for automation
    
    This demonstrates basic browser automation tasks:
    - Opening a browser with custom configuration
    - Navigating to websites
    - Extracting information (page title)
    - Taking screenshots (optional)
    - Proper cleanup
    """
    
    # Create browser with production-like settings
    profile = BrowserProfile(
        headless=False,  # Set to True for headless mode (no browser window)
        disable_security=True,  # Needed for automation, disables web security
        args=[
            '--no-sandbox',                # Required for many environments
            '--disable-dev-shm-usage',     # Overcome limited resource problems
            # '--disable-gpu',             # Uncomment for headless mode or if GPU issues
            '--disable-web-security',      # Disable web security for automation
            '--no-first-run',             # Skip first run wizards
            '--disable-extensions'         # Disable browser extensions
        ]
    )
    
    print("🚀 Starting browser automation example...")
    
    # Enable custom Rebrowse screensaver
    patch_browser_use_screensaver()
    
    browser = Browser(browser_profile=profile)
    await browser.start()
    
    try:
        page = await browser.get_current_page()
        
        # Example 1: Navigate to Rebrowse website
        print("📍 Navigating to rebrowse.me...")
        await page.goto("https://rebrowse.me")
        
        # Get page title
        title = await page.title()
        print(f"📄 Page title: {title}")
        
        # Get page URL
        url = page.url
        print(f"🔗 Current URL: {url}")
        
        # Example 2: Take a screenshot (uncomment to enable)
        # print("📸 Taking screenshot...")
        # await page.screenshot(path="rebrowse_screenshot.png")
        # print("✅ Screenshot saved as 'rebrowse_screenshot.png'")
        
        # Example 3: Extract text content (uncomment to try)
        # body_text = await page.text_content('body')
        # print(f"📝 Page contains {len(body_text)} characters")
        
        # Example 4: Navigate to another page for comparison
        print("📍 Navigating to httpbin.org...")
        await page.goto("https://httpbin.org/")
        
        new_title = await page.title()
        print(f"📄 New page title: {new_title}")
        
    except Exception as e:
        print(f"❌ Error during automation: {e}")
        
    finally:
        print("🔄 Closing browser...")
        await browser.close()
        print("✅ Browser automation completed!")

async def headless_example():
    """Example of running browser in headless mode (no GUI)"""
    
    print("🤖 Starting headless browser example...")
    
    # Enable custom screensaver (won't show in headless but good for testing)
    patch_browser_use_screensaver()
    
    profile = BrowserProfile(
        headless=True,  # No browser window will appear
        disable_security=True,
        args=[
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',              # Usually needed for headless
            '--disable-web-security',
            '--no-first-run',
            '--disable-extensions'
        ]
    )
    
    browser = Browser(browser_profile=profile)
    await browser.start()
    
    try:
        page = await browser.get_current_page()
        await page.goto("https://httpbin.org/json")
        
        title = await page.title()
        print(f"📄 Headless page title: {title}")
        
    finally:
        await browser.close()
        print("✅ Headless automation completed!")

if __name__ == "__main__":
    print("=== Browser-Use Example Script ===")
    print("This script demonstrates browser automation with browser-use library")
    print()
    
    # Run the main example
    asyncio.run(example_workflow())
    
    print()
    print("=" * 50)
    print()
    
    # Run headless example
    asyncio.run(headless_example())
    
    print()
    print("🎉 All examples completed!")
    print()
    print("Next steps:")
    print("- Modify this script for your automation needs")
    print("- Check browser-use documentation for more features")
    print("- Use headless=True for production/server environments") 