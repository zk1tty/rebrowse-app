#!/usr/bin/env python3
"""
Startup verification script for Playwright installation
This runs after the container starts to verify everything is working
"""
import os
import sys

def verify_playwright_installation():
    """Verify Playwright installation at startup"""
    print("🔍 Verifying Playwright installation...")
    
    # Check 1: Import Playwright
    try:
        import playwright
        print("✅ Playwright imported successfully")
    except ImportError as e:
        print(f"❌ Playwright import failed: {e}")
        return False
    
    # Check 2: Import browser-use
    try:
        from browser_use import Browser
        print("✅ browser-use imported successfully")
    except ImportError as e:
        print(f"❌ browser-use import failed: {e}")
        return False
    
    # Check 3: Check for Playwright browsers
    playwright_chromium_path = "/root/.cache/ms-playwright/chromium-1169/chrome-linux/chrome"
    if os.path.exists(playwright_chromium_path):
        print(f"✅ Playwright Chromium found at: {playwright_chromium_path}")
    else:
        print(f"⚠️ Playwright Chromium not found at: {playwright_chromium_path}")
        
        # Try to find any Playwright directory
        playwright_dir = "/root/.cache/ms-playwright"
        if os.path.exists(playwright_dir):
            try:
                contents = os.listdir(playwright_dir)
                print(f"📁 Playwright directory contents: {contents}")
            except Exception as e:
                print(f"❌ Error listing Playwright directory: {e}")
        else:
            print("❌ Playwright directory not found")
            return False
    
    # Check 4: Environment
    print(f"🌍 Environment: {'production' if os.getenv('RAILWAY_ENVIRONMENT') else 'development'}")
    print(f"🖥️ Display: {os.getenv('DISPLAY', 'not set')}")
    
    print("✅ Playwright verification completed")
    return True

if __name__ == "__main__":
    success = verify_playwright_installation()
    if not success:
        print("⚠️ Some Playwright verification checks failed")
        print("💡 Check the /health and /test-browser endpoints for more details")
    else:
        print("🎉 All Playwright verification checks passed!") 