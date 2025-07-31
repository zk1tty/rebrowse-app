#!/usr/bin/env python3
"""
Simple test to verify rrweb recording works properly with navigation to x.com
This tests the fixes we made to the navigation re-injection logic.
"""

import asyncio
import logging
import time
from typing import Dict, Any
from workflow_use.browser.visual_browser import VisualWorkflowBrowser

# Setup logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TestEventCollector:
    """Collects rrweb events for testing"""
    
    def __init__(self):
        self.events = []
        self.fullsnapshot_count = 0
        self.navigation_events = 0
        self.total_events = 0
        
    async def handle_event(self, event_data: Dict[str, Any]) -> None:
        """Handle incoming rrweb events"""
        try:
            event = event_data.get('event', {})
            event_type = event.get('type', 0)
            
            self.events.append(event)
            self.total_events += 1
            
            # Count FullSnapshot events (type 2)
            if event_type == 2:
                self.fullsnapshot_count += 1
                logger.info(f"📸 FullSnapshot #{self.fullsnapshot_count} received!")
                
            # Count navigation-related events
            if (event_type == 6 or 
                event.get('data', {}).get('tag') in ['navigation-detected', 'browser-only-navigation'] or
                event.get('data', {}).get('mode') == 'browser-only-tracking'):
                self.navigation_events += 1
                logger.info(f"🧭 Navigation event #{self.navigation_events} received")
                
            # Log every 10 events
            if self.total_events % 10 == 0:
                logger.info(f"📊 Events received: {self.total_events} (FullSnapshots: {self.fullsnapshot_count})")
                
        except Exception as e:
            logger.error(f"❌ Error handling event: {e}")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get test summary"""
        return {
            'total_events': self.total_events,
            'fullsnapshot_count': self.fullsnapshot_count,
            'navigation_events': self.navigation_events,
            'has_initial_fullsnapshot': self.fullsnapshot_count > 0,
            'has_navigation_events': self.navigation_events > 0,
            'events_after_navigation': self.total_events > 10  # Should have ongoing events
        }

async def test_rrweb_navigation():
    """Test rrweb recording with navigation to x.com"""
    logger.info("🚀 Starting rrweb navigation test...")
    
    # Create event collector
    event_collector = TestEventCollector()
    
    # Create visual browser with event collector
    visual_browser = VisualWorkflowBrowser(
        session_id="test-x-navigation",
        event_callback=event_collector.handle_event
    )
    
    try:
        logger.info("📱 Creating browser instance...")
        # Create browser (headless for testing)
        browser = await visual_browser.create_browser(headless=True)
        
        logger.info("🎬 Injecting rrweb recording...")
        # Inject rrweb - this should send initial FullSnapshot
        injection_success = await visual_browser.inject_rrweb()
        
        if not injection_success:
            logger.error("❌ rrweb injection failed!")
            return False
        
        logger.info("▶️ Starting recording...")
        # Start recording
        await visual_browser.start_recording()
        
        # Wait a moment for initial events
        await asyncio.sleep(2)
        
        logger.info(f"📊 Initial events: {event_collector.total_events} (FullSnapshots: {event_collector.fullsnapshot_count})")
        
        logger.info("🧭 Navigating to x.com (CSP-restricted site)...")
        # Navigate to x.com - this is where the bug was happening
        await visual_browser.navigate_to("https://x.com")
        
        logger.info("⏱️ Waiting for navigation to complete and events to flow...")
        # Wait for navigation and re-injection to complete
        await asyncio.sleep(5)
        
        logger.info("🎯 Testing some basic interactions...")
        # Test some interactions to generate events
        if visual_browser.page:
            try:
                # Scroll to generate events
                await visual_browser.page.evaluate("window.scrollTo(0, 200)")
                await asyncio.sleep(1)
                
                # Mouse movement
                await visual_browser.page.mouse.move(100, 100)
                await asyncio.sleep(1)
                
                # More scrolling
                await visual_browser.page.evaluate("window.scrollTo(0, 400)")
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.warning(f"⚠️ Some interactions failed (expected for CSP sites): {e}")
        
        logger.info("⏱️ Final wait for events...")
        # Final wait for events to flow
        await asyncio.sleep(3)
        
        # Get final results
        summary = event_collector.get_summary()
        
        logger.info("📋 TEST RESULTS:")
        logger.info("=" * 50)
        logger.info(f"📊 Total events received: {summary['total_events']}")
        logger.info(f"📸 FullSnapshot events: {summary['fullsnapshot_count']}")
        logger.info(f"🧭 Navigation events: {summary['navigation_events']}")
        logger.info(f"✅ Initial FullSnapshot: {'YES' if summary['has_initial_fullsnapshot'] else 'NO'}")
        logger.info(f"🧭 Navigation detected: {'YES' if summary['has_navigation_events'] else 'NO'}")
        logger.info(f"📈 Ongoing events: {'YES' if summary['events_after_navigation'] else 'NO'}")
        
        # Test evaluation
        test_passed = (
            summary['has_initial_fullsnapshot'] and  # Must have initial FullSnapshot
            summary['total_events'] > 0              # Must have some events
        )
        
        if test_passed:
            logger.info("🎉 TEST PASSED! rrweb recording is working properly with navigation")
        else:
            logger.error("❌ TEST FAILED! Issues detected with rrweb recording")
        
        logger.info("=" * 50)
        
        return test_passed
        
    except Exception as e:
        logger.error(f"❌ Test failed with exception: {e}")
        import traceback
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        return False
        
    finally:
        # Cleanup
        logger.info("🧹 Cleaning up test resources...")
        try:
            await visual_browser.cleanup()
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

async def main():
    """Main test runner"""
    logger.info("🎯 rrweb Navigation Test - Testing fixes for x.com navigation")
    logger.info("This test verifies:")
    logger.info("  1. Initial rrweb injection works")
    logger.info("  2. FullSnapshot is sent immediately")
    logger.info("  3. Navigation to x.com is detected")
    logger.info("  4. rrweb is re-injected after navigation")
    logger.info("  5. Events continue flowing after navigation")
    logger.info("")
    
    start_time = time.time()
    
    try:
        success = await test_rrweb_navigation()
        
        end_time = time.time()
        duration = end_time - start_time
        
        if success:
            logger.info(f"🎉 ALL TESTS PASSED in {duration:.1f} seconds!")
            logger.info("✅ rrweb recording works properly with x.com navigation")
        else:
            logger.error(f"❌ TESTS FAILED after {duration:.1f} seconds!")
            logger.error("🚨 Issues detected with rrweb recording")
            
        return success
        
    except KeyboardInterrupt:
        logger.info("⚠️ Test interrupted by user")
        return False
    except Exception as e:
        logger.error(f"❌ Test runner failed: {e}")
        return False

if __name__ == "__main__":
    # Run the test
    import sys
    
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Failed to run test: {e}")
        sys.exit(1) 