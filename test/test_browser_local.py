#!/usr/bin/env python3
"""
Local browser test script to verify browser functionality before Railway deployment
"""
import asyncio
import os
import shutil
import sys
from pathlib import Path

# Add the project root to Python path for robust imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from browser_use.browser.browser import Browser, BrowserProfile

async def test_browser_basic():
    """Test basic browser functionality"""
    print("🔍 Testing basic browser functionality...")
    
    try:
        # Test default browser (development mode)
        browser = Browser()
        await browser.start()
        
        page = await browser.get_current_page()
        await page.goto("data:text/html,<html><body><h1>Local Test</h1></body></html>")
        title = await page.title()
        
        await browser.close()
        
        print(f"✅ Basic browser test passed - Title: '{title}'")
        return True
        
    except Exception as e:
        print(f"❌ Basic browser test failed: {e}")
        return False

async def test_browser_headless():
    """Test headless browser configuration (production mode simulation)"""
    print("🔍 Testing headless browser configuration...")
    
    try:
        # Find Chromium executable
        chromium_paths = [
            '/usr/bin/chromium-browser',
            '/usr/bin/chromium',
            '/usr/bin/google-chrome',
            '/usr/bin/google-chrome-stable',
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',  # macOS
        ]
        
        chromium_executable = None
        for path in chromium_paths:
            if os.path.exists(path):
                chromium_executable = path
                break
        
        if not chromium_executable:
            # Try using shutil.which
            for name in ['chromium-browser', 'chromium', 'google-chrome', 'google-chrome-stable']:
                found = shutil.which(name)
                if found:
                    chromium_executable = found
                    break
        
        if not chromium_executable:
            print("⚠️  No Chromium executable found, using default")
            chromium_executable = 'chromium-browser'
        
        print(f"📍 Using Chromium: {chromium_executable}")
        
        # Create headless profile (simulating production)
        profile = BrowserProfile(
            headless=True,
            disable_security=True,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-web-security',
                '--single-process',
                '--no-first-run',
                '--disable-extensions'
            ]
        )
        
        browser = Browser(browser_profile=profile)
        await browser.start()
        
        page = await browser.get_current_page()
        await page.goto("https://httpbin.org/json")
        
        # Try to get some content
        content = await page.content()
        title = await page.title()
        
        await browser.close()
        
        print(f"✅ Headless browser test passed - Title: '{title}'")
        print(f"📄 Content length: {len(content)} characters")
        return True
        
    except Exception as e:
        print(f"❌ Headless browser test failed: {e}")
        return False

def check_system_requirements():
    """Check system requirements for browser"""
    print("🔍 Checking system requirements...")
    
    requirements = {
        "Python version": sys.version,
        "Platform": sys.platform,
        "Display": os.getenv('DISPLAY', 'not set'),
    }
    
    # Check for Chromium/Chrome
    chromium_found = []
    chromium_paths = [
        '/usr/bin/chromium-browser',
        '/usr/bin/chromium',
        '/usr/bin/google-chrome',
        '/usr/bin/google-chrome-stable',
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    ]
    
    for path in chromium_paths:
        if os.path.exists(path):
            chromium_found.append(path)
    
    # Check via which command
    for name in ['chromium-browser', 'chromium', 'google-chrome', 'google-chrome-stable']:
        found = shutil.which(name)
        if found and found not in chromium_found:
            chromium_found.append(found)
    
    requirements["Chromium/Chrome found"] = str(chromium_found) if chromium_found else "❌ None found"
    
    # Check for required libraries (Linux)
    if sys.platform.startswith('linux'):
        libs_to_check = ['libgtk-3.so.0', 'libnss3.so', 'libatk-1.0.so.0']
        for lib in libs_to_check:
            found = shutil.which(f'ldconfig -p | grep {lib}')
            requirements[f"Library {lib}"] = "✅ Found" if found else "❌ Missing"
    
    print("📋 System Requirements:")
    for key, value in requirements.items():
        print(f"  {key}: {value}")
    
    return len(chromium_found) > 0

async def test_browser_with_real_website():
    """Test browser with a real website"""
    print("🔍 Testing browser with real website...")
    
    try:
        browser = Browser()
        await browser.start()
        
        page = await browser.get_current_page()
        print("📍 Navigating to example.com...")
        await page.goto("https://example.com", timeout=30000)
        
        title = await page.title()
        url = page.url
        
        # Try to get some text content
        h1_element = await page.query_selector('h1')
        h1_text = await h1_element.text_content() if h1_element else "No H1 found"
        
        await browser.close()
        
        print(f"✅ Real website test passed")
        print(f"  Title: '{title}'")
        print(f"  URL: {url}")
        print(f"  H1 text: '{h1_text}'")
        return True
        
    except Exception as e:
        print(f"❌ Real website test failed: {e}")
        return False

async def main():
    """Run all browser tests"""
    print("🚀 Starting comprehensive browser tests...\n")
    
    # Test 1: System requirements
    system_ok = check_system_requirements()
    print()
    
    # Test 2: Basic browser
    basic_ok = await test_browser_basic()
    print()
    
    # Test 3: Headless browser
    headless_ok = await test_browser_headless()
    print()
    
    # Test 4: Real website
    website_ok = await test_browser_with_real_website()
    print()
    
    # Summary
    print("📋 Test Summary:")
    print(f"  System Requirements: {'✅ PASS' if system_ok else '❌ FAIL'}")
    print(f"  Basic Browser: {'✅ PASS' if basic_ok else '❌ FAIL'}")
    print(f"  Headless Browser: {'✅ PASS' if headless_ok else '❌ FAIL'}")
    print(f"  Real Website: {'✅ PASS' if website_ok else '❌ FAIL'}")
    
    all_passed = all([system_ok, basic_ok, headless_ok, website_ok])
    print(f"\n🎯 Overall Result: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
    
    if all_passed:
        print("\n🚀 Your browser setup is ready for Railway deployment!")
    else:
        print("\n⚠️  Please fix the failing tests before deploying to Railway.")
        print("💡 Common fixes:")
        print("  - Install Chromium: brew install chromium (macOS) or apt install chromium-browser (Linux)")
        print("  - Check display settings for headless mode")
        print("  - Ensure all required libraries are installed")

if __name__ == "__main__":
    asyncio.run(main()) 