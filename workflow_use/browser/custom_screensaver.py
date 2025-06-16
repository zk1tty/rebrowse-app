"""
Custom DVD screensaver animation to replace browser-use default logo
"""
import asyncio
import base64
import os
from pathlib import Path
from typing import Optional


def get_rebrowse_logo_data_url() -> Optional[str]:
    """Convert the local rebrowse.png to a data URL for use in the browser"""
    try:
        # Get the path to rebrowse.png (should be in project root)
        logo_path = Path(__file__).parent.parent.parent / "rebrowse.png"
        
        if not logo_path.exists():
            print(f"⚠️ rebrowse.png not found at {logo_path}")
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
        print(f"❌ Failed to load rebrowse.png: {e}")
        return None


async def show_custom_dvd_screensaver(page, logo_url: Optional[str] = None, logo_text: str = "rebrowse") -> None:
    """
    Custom DVD screensaver-style bouncing logo animation.
    
    Args:
        page: Playwright page instance
        logo_url: URL to your custom logo image (optional)
        logo_text: Text to display if no logo URL provided
    """
    # Try to use rebrowse.png if no logo_url provided
    if not logo_url:
        logo_url = get_rebrowse_logo_data_url()
    
    # Default to a nice gradient text if no logo available
    if not logo_url:
        logo_element = f"""
            <div class="logo-text">{logo_text}</div>
            <style>
                .logo-text {{
                    font-family: 'Arial', sans-serif;
                    font-size: 48px;
                    font-weight: bold;
                    background: linear-gradient(45deg, #ff6b6b, #4ecdc4, #45b7d1, #96ceb4, #feca57);
                    background-size: 300% 300%;
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    background-clip: text;
                    animation: gradientShift 3s ease infinite;
                    text-shadow: 0 0 20px rgba(255, 255, 255, 0.3);
                }}
                @keyframes gradientShift {{
                    0% {{ background-position: 0% 50%; }}
                    50% {{ background-position: 100% 50%; }}
                    100% {{ background-position: 0% 50%; }}
                }}
            </style>
        """
    else:
        logo_element = f'<img src="{logo_url}" alt="rebrowse Logo" style="width: 200px; height: auto; border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.3);">'

    await page.evaluate(f"""() => {{
        document.title = 'rebrowse - Setting up...';

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
        loadingOverlay.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
        loadingOverlay.style.zIndex = '99999';
        loadingOverlay.style.overflow = 'hidden';

        // Create the logo container
        const logoContainer = document.createElement('div');
        logoContainer.innerHTML = `{logo_element}`;
        logoContainer.style.position = 'absolute';
        logoContainer.style.left = '0px';
        logoContainer.style.top = '0px';
        logoContainer.style.zIndex = '2';
        logoContainer.style.opacity = '0.9';
        logoContainer.style.filter = 'drop-shadow(0 0 10px rgba(255, 255, 255, 0.3))';

        loadingOverlay.appendChild(logoContainer);
        document.body.appendChild(loadingOverlay);

        // Enhanced DVD screensaver bounce logic
        let x = Math.random() * (window.innerWidth - 300);
        let y = Math.random() * (window.innerHeight - 200);
        let dx = 2 + Math.random() * 1; // Slightly faster
        let dy = 2 + Math.random() * 1;
        
        // Randomize direction
        if (Math.random() > 0.5) dx = -dx;
        if (Math.random() > 0.5) dy = -dy;

        // Color change on bounce
        const colors = ['#ff6b6b', '#4ecdc4', '#45b7d1', '#96ceb4', '#feca57', '#fd79a8', '#fdcb6e'];
        let colorIndex = 0;

        function animate() {{
            const containerWidth = logoContainer.offsetWidth || 200;
            const containerHeight = logoContainer.offsetHeight || 100;
            
            x += dx;
            y += dy;

            // Bounce off edges and change color
            if (x <= 0) {{
                x = 0;
                dx = Math.abs(dx);
                changeColor();
            }}
            if (x >= window.innerWidth - containerWidth) {{
                x = window.innerWidth - containerWidth;
                dx = -Math.abs(dx);
                changeColor();
            }}
            if (y <= 0) {{
                y = 0;
                dy = Math.abs(dy);
                changeColor();
            }}
            if (y >= window.innerHeight - containerHeight) {{
                y = window.innerHeight - containerHeight;
                dy = -Math.abs(dy);
                changeColor();
            }}

            logoContainer.style.left = x + 'px';
            logoContainer.style.top = y + 'px';

            requestAnimationFrame(animate);
        }}

        function changeColor() {{
            colorIndex = (colorIndex + 1) % colors.length;
            logoContainer.style.filter = `drop-shadow(0 0 20px ${{colors[colorIndex]}}) hue-rotate(${{colorIndex * 45}}deg)`;
        }}

        animate();

        // Add some sparkle effects
        function createSparkle() {{
            const sparkle = document.createElement('div');
            sparkle.style.position = 'absolute';
            sparkle.style.width = '4px';
            sparkle.style.height = '4px';
            sparkle.style.background = 'white';
            sparkle.style.borderRadius = '50%';
            sparkle.style.left = Math.random() * window.innerWidth + 'px';
            sparkle.style.top = Math.random() * window.innerHeight + 'px';
            sparkle.style.opacity = '0.8';
            sparkle.style.animation = 'sparkle 2s linear infinite';
            sparkle.style.zIndex = '1';
            
            loadingOverlay.appendChild(sparkle);
            
            setTimeout(() => sparkle.remove(), 2000);
        }}

        // Add sparkle animation CSS
        const sparkleStyle = document.createElement('style');
        sparkleStyle.textContent = `
            @keyframes sparkle {{
                0% {{ opacity: 0; transform: scale(0); }}
                50% {{ opacity: 1; transform: scale(1); }}
                100% {{ opacity: 0; transform: scale(0); }}
            }}
        `;
        document.head.appendChild(sparkleStyle);

        // Create sparkles periodically
        setInterval(createSparkle, 300);
    }}""")


def patch_browser_use_screensaver(logo_url: Optional[str] = None, logo_text: str = "rebrowse"):
    """
    Monkey patch the browser-use screensaver function with our custom one.
    Call this before creating any Browser instances.
    
    Args:
        logo_url: URL to your custom logo image (optional, will auto-use rebrowse.png)
        logo_text: Text to display if no logo URL provided (default: "rebrowse")
    """
    try:
        from browser_use.browser.session import BrowserSession
        
        # Store the original function (in case we want to restore it)
        original_func = getattr(BrowserSession, '_show_dvd_screensaver_loading_animation', None)
        if original_func and not hasattr(BrowserSession, '_original_show_dvd_screensaver'):
            setattr(BrowserSession, '_original_show_dvd_screensaver', original_func)
        
        # Replace with our custom function
        async def custom_screensaver(self, page):
            await show_custom_dvd_screensaver(page, logo_url, logo_text)
        
        setattr(BrowserSession, '_show_dvd_screensaver_loading_animation', custom_screensaver)
        
        logo_info = logo_url or "rebrowse.png (auto-detected)" if get_rebrowse_logo_data_url() else logo_text
        print(f"✅ Custom rebrowse DVD screensaver patched! Logo: {logo_info}")
        
    except ImportError as e:
        print(f"❌ Failed to patch browser-use screensaver: {e}")
    except Exception as e:
        print(f"❌ Error patching screensaver: {e}")


def restore_original_screensaver():
    """Restore the original browser-use screensaver"""
    try:
        from browser_use.browser.session import BrowserSession
        
        original_func = getattr(BrowserSession, '_original_show_dvd_screensaver', None)
        if original_func:
            setattr(BrowserSession, '_show_dvd_screensaver_loading_animation', original_func)
            print("✅ Original browser-use screensaver restored!")
        else:
            print("⚠️ No original screensaver found to restore")
            
    except ImportError as e:
        print(f"❌ Failed to restore screensaver: {e}")
    except Exception as e:
        print(f"❌ Error restoring screensaver: {e}") 