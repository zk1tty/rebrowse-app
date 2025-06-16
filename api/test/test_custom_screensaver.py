#!/usr/bin/env python3
"""
Test script to demonstrate the rebrowse custom DVD screensaver
"""
import asyncio
import sys
from pathlib import Path

# Add the project root to Python path for robust imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from browser_use import Browser
from workflow_use.browser.custom_screensaver import patch_browser_use_screensaver

async def test_rebrowse_screensaver():
    """Test the rebrowse custom DVD screensaver"""
    
    print("🎮 Testing rebrowse Custom DVD Screensaver...")
    
    # Use rebrowse logo (auto-detects rebrowse.png)
    print("\n🚀 Testing with rebrowse.png logo...")
    patch_browser_use_screensaver(
        logo_url=None,  # Will auto-detect rebrowse.png
        logo_text="rebrowse"  # Fallback text
    )
    
    browser = Browser()
    await browser.start()
    
    # The screensaver should appear on the about:blank page
    print("✨ rebrowse screensaver should be visible now!")
    print("   - Beautiful purple gradient background")
    print("   - Bouncing rebrowse.png logo with rounded corners")
    print("   - Sparkle effects floating around")
    print("   - Rainbow color changes on bounce")
    print("   - Title: 'rebrowse - Setting up...'")
    
    # Wait a bit to see the animation
    await asyncio.sleep(15)
    
    await browser.close()
    print("✅ rebrowse logo screensaver test completed!")
    
    print("\n🎉 rebrowse DVD screensaver is ready!")
    print("\n🌟 Features:")
    print("   ✨ Auto-detects your rebrowse.png logo")
    print("   🎨 Beautiful purple gradient background")
    print("   🌈 Color-changing effects on bounce")
    print("   ✨ Sparkle particle effects")
    print("   🎮 Smooth DVD screensaver physics")
    print("   📱 Responsive design")
    print("   🚀 Production ready for Railway!")

if __name__ == "__main__":
    asyncio.run(test_rebrowse_screensaver()) 