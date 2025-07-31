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

    # Simple HTML for real bouncing animation
    screensaver_html = f"""
        <div id="pretty-loading-animation" style="
            position: fixed;
            top: 0; left: 0;
            width: 100vw; height: 100vh;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            z-index: 99999;
            overflow: hidden;
        ">
            <div id="bouncing-logo" style="
                position: absolute;
                left: 50px;
                top: 50px;
                transition: filter 0.3s ease;
            ">
                {logo_element}
            </div>
        </div>
    """
    
    await page.evaluate(f"""() => {{
        console.log('🏀 Creating REAL bouncing DVD screensaver...');
        
        document.title = 'rebrowse - Setting up...';
        
        // Remove existing screensaver
        const existing = document.getElementById('pretty-loading-animation');
        if (existing) existing.remove();
        
        // Stop any existing animation loops
        if (window.dvdAnimationId) {{
            cancelAnimationFrame(window.dvdAnimationId);
        }}
        
        // Add HTML content to body
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = `{screensaver_html}`;
        document.body.appendChild(tempDiv.firstElementChild);
        
        // Real DVD bouncing animation with JavaScript
        const logo = document.getElementById('bouncing-logo');
        if (!logo) {{
            console.error('Logo element not found');
            return;
        }}
        
        // Animation state
        let x = 50;
        let y = 50;
        let velocityX = 6;    // 2.0x faster speed (original was 3)
        let velocityY = 4;    // 2.0x faster speed (original was 2)
        let currentColorIndex = 0;
        
        // Neon color palette with shocking/vibrant tones - matching the original pink intensity
        const colors = [
            'hue-rotate(0deg) saturate(2) brightness(1.3) contrast(1.2)',           // Original shocking pink
            'hue-rotate(80deg) saturate(2.5) brightness(1.4) contrast(1.3)',       // Neon yellow-green
            'hue-rotate(120deg) saturate(2.2) brightness(1.3) contrast(1.2)',      // Neon green  
            'hue-rotate(180deg) saturate(2.4) brightness(1.4) contrast(1.3)',      // Neon cyan
            'hue-rotate(240deg) saturate(2.3) brightness(1.3) contrast(1.2)',      // Neon blue
            'hue-rotate(0deg) saturate(2.5) brightness(1.4) contrast(1.3) hue-rotate(340deg)'  // Neon red
        ];
        
        function getWindowSize() {{
            return {{
                width: window.innerWidth,
                height: window.innerHeight
            }};
        }}
        
        function getLogoSize() {{
            const rect = logo.getBoundingClientRect();
            return {{
                width: rect.width,
                height: rect.height
            }};
        }}
        
        function changeColor() {{
            currentColorIndex = (currentColorIndex + 1) % colors.length;
            logo.style.filter = colors[currentColorIndex];
            
            // Add a brief glow effect on bounce
            logo.style.transform = 'scale(1.1)';
            setTimeout(() => {{
                logo.style.transform = 'scale(1)';
            }}, 100);
        }}
        
        function animate() {{
            const windowSize = getWindowSize();
            const logoSize = getLogoSize();
            
            // Update position
            x += velocityX;
            y += velocityY;
            
            // Check for collisions and bounce
            let bounced = false;
            
            // Right edge collision
            if (x + logoSize.width >= windowSize.width) {{
                x = windowSize.width - logoSize.width;
                velocityX = -Math.abs(velocityX);  // Ensure negative velocity
                bounced = true;
            }}
            
            // Left edge collision  
            if (x <= 0) {{
                x = 0;
                velocityX = Math.abs(velocityX);  // Ensure positive velocity
                bounced = true;
            }}
            
            // Bottom edge collision
            if (y + logoSize.height >= windowSize.height) {{
                y = windowSize.height - logoSize.height;
                velocityY = -Math.abs(velocityY);  // Ensure negative velocity
                bounced = true;
            }}
            
            // Top edge collision
            if (y <= 0) {{
                y = 0;
                velocityY = Math.abs(velocityY);  // Ensure positive velocity
                bounced = true;
            }}
            
            // Change color if bounced
            if (bounced) {{
                changeColor();
                console.log(`🏀 Bounced! New color: ${{colors[currentColorIndex]}}`);
            }}
            
            // Apply position
            logo.style.left = x + 'px';
            logo.style.top = y + 'px';
            
            // Continue animation
            window.dvdAnimationId = requestAnimationFrame(animate);
        }}
        
        // Handle window resize
        window.addEventListener('resize', () => {{
            const windowSize = getWindowSize();
            const logoSize = getLogoSize();
            
            // Ensure logo stays within bounds after resize
            if (x + logoSize.width > windowSize.width) {{
                x = windowSize.width - logoSize.width;
            }}
            if (y + logoSize.height > windowSize.height) {{
                y = windowSize.height - logoSize.height;
            }}
        }});
        
        // Start the animation
        console.log('✅ Starting real DVD bouncing animation!');
        console.log('   • Bounces off window edges');
        console.log('   • Constant speed movement');
        console.log('   • Color changes on bounce');
        
        // Wait for rrweb to be fully loaded before starting animation
        function startAnimationWhenReady() {{
            // Check if rrweb is present and active
            const rrwebActive = (
                typeof window.rrweb !== 'undefined' || 
                typeof window.__rrweb_original__ !== 'undefined' ||
                typeof window.rrwebRecord !== 'undefined' ||
                document.querySelector('script[src*="rrweb"]') !== null
            );
            
            console.log('🔍 RRWeb detection:', {{
                rrweb_exists: typeof window.rrweb !== 'undefined',
                rrweb_original: typeof window.__rrweb_original__ !== 'undefined', 
                rrweb_record: typeof window.rrwebRecord !== 'undefined',
                rrweb_script: document.querySelector('script[src*="rrweb"]') !== null,
                will_wait_for_rrweb: rrwebActive
            }});
            
            if (rrwebActive) {{
                console.log('🎯 RRWeb detected - waiting additional 500ms for full setup...');
                setTimeout(() => {{
                    console.log('🚀 Starting animation after rrweb setup');
                    animate();
                }}, 500);
            }} else {{
                console.log('🚀 No rrweb detected - starting animation immediately');
                animate();
            }}
        }}
        
        // Wait a moment for layout, then check for rrweb and start
        setTimeout(() => {{
            startAnimationWhenReady();
        }}, 200);
    }}""")


def patch_browser_use_screensaver(logo_url: Optional[str] = None, logo_text: str = "rebrowse", css_only: bool = False):
    """
    Monkey patch the browser-use screensaver function with our custom one.
    Call this before creating any Browser instances.
    
    Args:
        logo_url: URL to your custom logo image (optional, will auto-use rebrowse.png)
        logo_text: Text to display if no logo URL provided (default: "rebrowse")
        css_only: If True, use CSS-only animation for maximum rrweb compatibility
    """
    try:
        from browser_use.browser.session import BrowserSession
        
        # Store the original function (in case we want to restore it)
        original_func = getattr(BrowserSession, '_show_dvd_screensaver_loading_animation', None)
        if original_func and not hasattr(BrowserSession, '_original_show_dvd_screensaver'):
            setattr(BrowserSession, '_original_show_dvd_screensaver', original_func)
        
        # Choose animation type
        if css_only:
            # CSS-only version for maximum rrweb compatibility
            async def css_only_screensaver(self, page):
                await show_css_only_dvd_screensaver(page, logo_url, logo_text)
            setattr(BrowserSession, '_show_dvd_screensaver_loading_animation', css_only_screensaver)
            print(f"✅ CSS-only rebrowse DVD screensaver patched! Logo: {logo_url or logo_text}")
        else:
            # Enhanced JavaScript version
            async def custom_screensaver(self, page):
                await show_custom_dvd_screensaver(page, logo_url, logo_text)
            setattr(BrowserSession, '_show_dvd_screensaver_loading_animation', custom_screensaver)
            print(f"✅ Enhanced rebrowse DVD screensaver patched! Logo: {logo_url or logo_text}")
        
    except ImportError as e:
        print(f"❌ Failed to patch browser-use screensaver: {e}")
    except Exception as e:
        print(f"❌ Error patching screensaver: {e}")


async def show_css_only_dvd_screensaver(page, logo_url: Optional[str] = None, logo_text: str = "rebrowse") -> None:
    """CSS-only DVD screensaver for maximum rrweb compatibility"""
    # Try to use rebrowse.png if no logo_url provided
    if not logo_url:
        logo_url = get_rebrowse_logo_data_url()
    
    # Use logo or fallback text
    if logo_url:
        logo_element = f'<img src="{logo_url}" alt="rebrowse Logo" style="width: 200px; height: 200px; border-radius: 12px;">'
    else:
        logo_element = f'<div class="logo-text">{logo_text}</div>'
    
    await page.evaluate(f"""() => {{
        console.log('🎨 Creating CSS-only bouncing screensaver for rrweb compatibility...');
        
        // Remove existing screensaver
        const existing = document.getElementById('pretty-loading-animation');
        if (existing) existing.remove();
        
        // Create CSS-only screensaver
        const screensaver = document.createElement('div');
        screensaver.innerHTML = `
            <style>
                #css-screensaver {{
                    position: fixed;
                    top: 0; left: 0;
                    width: 100vw; height: 100vh;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    z-index: 99999;
                    overflow: hidden;
                }}
                
                .css-logo {{
                    position: absolute;
                    animation: cssMove 6s linear infinite, cssColor 2s ease-in-out infinite;
                }}
                
                @keyframes cssMove {{
                    0%   {{ left: 50px; top: 50px; }}
                    12.5% {{ left: calc(100vw - 250px); top: 100px; }}
                    25%  {{ left: calc(100vw - 300px); top: calc(100vh - 250px); }}
                    37.5% {{ left: 200px; top: calc(100vh - 200px); }}
                    50%  {{ left: 100px; top: calc(50vh - 100px); }}
                    62.5% {{ left: calc(100vw - 200px); top: 150px; }}
                    75%  {{ left: calc(100vw - 150px); top: calc(100vh - 150px); }}
                    87.5% {{ left: 150px; top: calc(100vh - 300px); }}
                    100% {{ left: 50px; top: 50px; }}
                }}
                
                @keyframes cssColor {{
                    0%   {{ filter: hue-rotate(0deg) saturate(2) brightness(1.3) contrast(1.2); }}
                    16%  {{ filter: hue-rotate(80deg) saturate(2.5) brightness(1.4) contrast(1.3); }}
                    32%  {{ filter: hue-rotate(120deg) saturate(2.2) brightness(1.3) contrast(1.2); }}
                    48%  {{ filter: hue-rotate(180deg) saturate(2.4) brightness(1.4) contrast(1.3); }}
                    64%  {{ filter: hue-rotate(240deg) saturate(2.3) brightness(1.3) contrast(1.2); }}
                    80%  {{ filter: hue-rotate(340deg) saturate(2.5) brightness(1.4) contrast(1.3); }}
                    100% {{ filter: hue-rotate(0deg) saturate(2) brightness(1.3) contrast(1.2); }}
                }}
                
                .logo-text {{
                    font-family: Arial, sans-serif;
                    font-size: 48px;
                    font-weight: bold;
                    color: #ff1493;
                    text-shadow: 0 0 20px rgba(255, 20, 147, 0.6);
                }}
            </style>
            
            <div id="css-screensaver">
                <div class="css-logo">
                    {logo_element}
                </div>
            </div>
        `;
        
        document.body.appendChild(screensaver);
        console.log('✅ CSS-only screensaver created - guaranteed rrweb compatibility!');
    }}""")


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