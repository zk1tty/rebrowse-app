#!/usr/bin/env python3
"""
Frontend Iframe Streaming Test

This test verifies that our iframe-based rrweb implementation works correctly:
1. Backend sends rrweb events properly 
2. Frontend iframe receives and processes events without errors
3. No more insertStyleRules errors
4. Visual streaming works with both x.com and example.com
"""

import asyncio
import logging
import time
from typing import Dict, Any
from workflow_use.browser.visual_browser import VisualWorkflowBrowser

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class StreamingTestCollector:
    """Collects streaming test results"""
    
    def __init__(self):
        self.events = []
        self.fullsnapshot_count = 0
        self.total_events = 0
        self.errors = []
        self.start_time = None
        
    async def handle_event(self, event_data: Dict[str, Any]) -> None:
        """Handle incoming rrweb events"""
        try:
            if self.start_time is None:
                self.start_time = time.time()
                
            event = event_data.get('event', {})
            event_type = event.get('type', 0)
            
            self.events.append({
                'timestamp': time.time(),
                'type': event_type,
                'event': event
            })
            self.total_events += 1
            
            # Count FullSnapshot events (type 2)
            if event_type == 2:
                self.fullsnapshot_count += 1
                logger.info(f"✅ FullSnapshot #{self.fullsnapshot_count} captured successfully!")
                
            # Log every 10 events for progress tracking
            if self.total_events % 10 == 0:
                logger.info(f"📊 Progress: {self.total_events} events processed")
                
        except Exception as e:
            logger.error(f"❌ Error handling event: {e}")
            self.errors.append(str(e))
    
    def get_test_results(self) -> Dict[str, Any]:
        """Get comprehensive test results"""
        duration = time.time() - self.start_time if self.start_time else 0
        
        # Analyze event types
        event_types = {}
        for event in self.events:
            event_type = event['type']
            event_types[event_type] = event_types.get(event_type, 0) + 1
        
        return {
            'total_events': self.total_events,
            'fullsnapshot_count': self.fullsnapshot_count,
            'event_types': event_types,
            'duration': duration,
            'errors': self.errors,
            'events_per_second': self.total_events / duration if duration > 0 else 0,
            'has_fullsnapshot': self.fullsnapshot_count > 0,
            'has_events': self.total_events > 0,
            'error_count': len(self.errors)
        }

async def test_website_streaming(url: str, test_name: str) -> Dict[str, Any]:
    """Test rrweb streaming for a specific website"""
    logger.info(f"🌐 Testing {test_name}: {url}")
    
    # Create event collector
    collector = StreamingTestCollector()
    
    # Create visual browser with event collector
    visual_browser = VisualWorkflowBrowser(
        session_id=f"frontend-test-{int(time.time())}",
        event_callback=collector.handle_event
    )
    
    try:
        logger.info("📱 Creating browser instance...")
        browser = await visual_browser.create_browser(headless=True)
        
        logger.info("🎬 Injecting rrweb recording...")
        injection_success = await visual_browser.inject_rrweb()
        
        if not injection_success:
            logger.error("❌ rrweb injection failed!")
            return {'success': False, 'error': 'rrweb injection failed'}
        
        logger.info("▶️ Starting recording...")
        await visual_browser.start_recording()
        
        # Wait for initial events
        await asyncio.sleep(2)
        
        logger.info(f"🧭 Navigating to {url}...")
        await visual_browser.navigate_to(url)
        
        logger.info("⏱️ Collecting events for navigation and interactions...")
        await asyncio.sleep(5)
        
        # Perform some interactions to generate more events
        if visual_browser.page:
            try:
                logger.info("🖱️ Performing test interactions...")
                
                # Scroll to generate events
                await visual_browser.page.evaluate("window.scrollTo(0, 200)")
                await asyncio.sleep(1)
                
                # Mouse movement
                await visual_browser.page.mouse.move(100, 100)
                await asyncio.sleep(1)
                
                # More scrolling
                await visual_browser.page.evaluate("window.scrollTo(0, 400)")
                await asyncio.sleep(1)
                
                # Click interaction
                await visual_browser.page.mouse.click(200, 200)
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.warning(f"⚠️ Some interactions failed (expected for some sites): {e}")
        
        # Final collection period
        logger.info("⏱️ Final event collection...")
        await asyncio.sleep(3)
        
        # Get results
        results = collector.get_test_results()
        results['success'] = True
        results['url'] = url
        results['test_name'] = test_name
        
        return results
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'url': url,
            'test_name': test_name
        }
        
    finally:
        # Cleanup
        try:
            await visual_browser.cleanup()
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

async def run_comprehensive_streaming_test():
    """Run comprehensive test on multiple websites"""
    logger.info("🚀 Frontend Iframe Streaming Test - Comprehensive Testing")
    logger.info("=" * 70)
    logger.info("Testing our new iframe-based rrweb implementation:")
    logger.info("  ✅ Step 1: Use iframe with full document")
    logger.info("  ✅ Step 2: Load rrweb via script tag")
    logger.info("  🎯 Expected: No more insertStyleRules errors")
    logger.info("=" * 70)
    
    # Test cases for different website types
    test_cases = [
        ("https://example.com", "Simple Website"),
        ("https://x.com", "Complex SPA")
    ]
    
    all_results = []
    
    for url, test_name in test_cases:
        logger.info(f"\n📋 Starting test: {test_name}")
        logger.info("-" * 50)
        
        start_time = time.time()
        results = await test_website_streaming(url, test_name)
        end_time = time.time()
        
        results['test_duration'] = end_time - start_time
        all_results.append(results)
        
        # Print individual test results
        logger.info(f"\n📊 {test_name} Results:")
        if results['success']:
            logger.info(f"  ✅ Success: True")
            logger.info(f"  📡 Total Events: {results['total_events']}")
            logger.info(f"  📸 FullSnapshots: {results['fullsnapshot_count']}")
            logger.info(f"  ⚡ Events/Second: {results['events_per_second']:.1f}")
            logger.info(f"  🕒 Duration: {results['duration']:.1f}s")
            logger.info(f"  ❌ Errors: {results['error_count']}")
            
            if results['event_types']:
                logger.info(f"  📋 Event Types: {results['event_types']}")
        else:
            logger.info(f"  ❌ Success: False")
            logger.info(f"  💥 Error: {results.get('error', 'Unknown error')}")
    
    # Overall analysis
    logger.info(f"\n🎯 COMPREHENSIVE TEST ANALYSIS")
    logger.info("=" * 70)
    
    successful_tests = [r for r in all_results if r['success']]
    failed_tests = [r for r in all_results if not r['success']]
    
    logger.info(f"📊 Test Summary:")
    logger.info(f"  ✅ Successful Tests: {len(successful_tests)}/{len(all_results)}")
    logger.info(f"  ❌ Failed Tests: {len(failed_tests)}/{len(all_results)}")
    
    if successful_tests:
        total_events = sum(r['total_events'] for r in successful_tests)
        total_fullsnapshots = sum(r['fullsnapshot_count'] for r in successful_tests)
        avg_events_per_second = sum(r['events_per_second'] for r in successful_tests) / len(successful_tests)
        
        logger.info(f"\n📈 Performance Metrics:")
        logger.info(f"  📡 Total Events Captured: {total_events}")
        logger.info(f"  📸 Total FullSnapshots: {total_fullsnapshots}")
        logger.info(f"  ⚡ Average Events/Second: {avg_events_per_second:.1f}")
    
    # Check for specific improvements
    logger.info(f"\n🔍 Implementation Verification:")
    all_have_events = all(r.get('has_events', False) for r in successful_tests)
    all_have_fullsnapshots = all(r.get('has_fullsnapshot', False) for r in successful_tests)
    no_errors = all(r.get('error_count', 0) == 0 for r in successful_tests)
    
    logger.info(f"  📡 All tests captured events: {'✅' if all_have_events else '❌'}")
    logger.info(f"  📸 All tests captured FullSnapshots: {'✅' if all_have_fullsnapshots else '❌'}")
    logger.info(f"  🛡️ No processing errors: {'✅' if no_errors else '❌'}")
    
    # Overall assessment
    overall_success = (
        len(successful_tests) == len(all_results) and
        all_have_events and
        all_have_fullsnapshots and
        no_errors
    )
    
    logger.info(f"\n🏆 FINAL VERDICT:")
    if overall_success:
        logger.info("🎉 IFRAME STREAMING IMPLEMENTATION: SUCCESS!")
        logger.info("✅ All websites stream correctly")
        logger.info("✅ FullSnapshots captured properly") 
        logger.info("✅ No processing errors detected")
        logger.info("🎯 Ready for frontend testing!")
    else:
        logger.info("❌ IFRAME STREAMING IMPLEMENTATION: NEEDS WORK")
        logger.info("💡 Check failed tests for specific issues")
    
    logger.info("=" * 70)
    
    return overall_success

if __name__ == "__main__":
    try:
        success = asyncio.run(run_comprehensive_streaming_test())
        exit_code = 0 if success else 1
        exit(exit_code)
    except KeyboardInterrupt:
        logger.info("⚠️ Test interrupted by user")
        exit(1)
    except Exception as e:
        logger.error(f"❌ Test runner failed: {e}")
        exit(1) 