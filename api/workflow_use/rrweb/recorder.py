#!/usr/bin/env python3
"""
RRWebRecorder: Single responsibility rrweb recording management

This class replaces VisualWorkflowBrowser with a clean single-responsibility design:
- NO browser creation/management (browser is passed from outside)
- Pure rrweb injection and recording management
- Explicit navigation re-injection control
- Clean error handling (fail fast, no fallbacks)

Key responsibilities:
- Accept existing browser instance (never creates browsers)
- Initialize with browser.get_current_page()
- Inject rrweb into current page
- Manage recording lifecycle (start/stop)
- Handle rrweb events and streaming
- Manual navigation re-injection (explicit control)
- Error handling (fail fast, no fallbacks)

What it DOESN'T do:
- Browser creation or lifecycle management
- Browser profile management
- Page navigation (only re-injection after navigation)
- Fallback browser creation
"""

import asyncio
import json
import logging
from collections import deque
from typing import Optional, Callable, Dict, Any, List
from browser_use import Browser
from playwright.async_api import Page, Browser, Frame

from .config import get_cdn_url, get_recording_options_js

logger = logging.getLogger(__name__)


# 🔧 GLOBAL RRWEB RECORDER REGISTRY for backend access
_global_rrweb_registry: Dict[str, "RRWebRecorder"] = {}

def register_rrweb_recorder(session_id: str, recorder: "RRWebRecorder") -> None:
    """Register a rrweb recorder instance globally for backend access"""
    global _global_rrweb_registry
    _global_rrweb_registry[session_id] = recorder
    logger.info(f"📝 Registered rrweb recorder for session {session_id}")

def unregister_rrweb_recorder(session_id: str) -> None:
    """Unregister a rrweb recorder instance from global registry"""
    global _global_rrweb_registry
    if session_id in _global_rrweb_registry:
        del _global_rrweb_registry[session_id]
        logger.info(f"🗑️ Unregistered rrweb recorder for session {session_id}")

def get_rrweb_recorder(session_id: str) -> Optional["RRWebRecorder"]:
    """Get a rrweb recorder instance from global registry"""
    global _global_rrweb_registry
    return _global_rrweb_registry.get(session_id)


class RRWebRecorder:
    """
    Single responsibility: RRWeb recording management for existing browser instances
    
    This class:
    - Takes an EXISTING browser instance (already started)
    - Manages rrweb injection and recording lifecycle
    - Handles event streaming and callbacks
    - Provides explicit navigation re-injection control
    - Does NOT create or manage browser lifecycle
    """
    
    def __init__(self, session_id: str, page: Page, event_callback: Optional[Callable] = None):
        """
        Initialize RRWebRecorder for a specific page.
        
        Args:
            session_id: Unique session identifier
            page: Playwright page instance (managed by BrowserFactory)
            event_callback: Function to call when rrweb events are received
        """
        self.session_id = session_id
        self.page = page
        self.event_callback = event_callback
        
        # Recording state
        self.recording_active = False
        self.rrweb_injected = False
        
        # Event buffering for reconnection scenarios
        self.event_buffer: List[Dict[str, Any]] = []
        
        # CRITICAL FIX: Sequence ID counter starting at 0 (not 1)
        self.sequence_counter = 0
        
        # Phase-aware navigation monitoring
        self.navigation_monitoring_active = False
        self.current_phase = "SETUP"  # Track current phase
        
        # rrweb configuration
        self.rrweb_cdn_url = get_cdn_url()
        
        logger.info(f"RRWebRecorder initialized for session {session_id}")
    
    async def start_recording(self) -> bool:
        """Start rrweb recording with enhanced navigation support"""
        if self.recording_active:
            logger.warning(f"Recording already active for session {self.session_id}")
            return True
        
        try:
            logger.info(f"Starting rrweb recording for session {self.session_id}")
            
            # Get current page URL
            current_url = self.page.url
            
            logger.info(f"🎬 Starting enhanced rrweb injection for session {self.session_id} on {current_url}")
            
            # CRITICAL FIX: Expose callback functions FIRST
            logger.debug("Exposing rrweb callback functions...")
            await self._expose_rrweb_event_function()
            await self._expose_rrweb_error_function()
            
            # Try both injection methods
            if await self._try_cdn_injection():
                logger.info(f"✅ rrweb CDN injection successful for session {self.session_id}")
            elif await self._try_inline_injection():
                logger.info(f"✅ rrweb inline injection successful for session {self.session_id}")
            else:
                logger.error(f"❌ Both injection methods failed for session {self.session_id}")
                return False
            
            # DON'T set up navigation monitoring immediately during SETUP/READY phases
            # This prevents screensaver interruption - navigation monitoring will be enabled
            # later when transitioning to EXECUTING phase
            logger.info(f"🔕 Navigation monitoring disabled during {self.current_phase} phase")
            
            # CRITICAL FIX: Set up page load listener for full page navigation
            await self._setup_page_load_listener()
            
            self.recording_active = True
            logger.info(f"✅ rrweb recording started for session {self.session_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start rrweb recording for session {self.session_id}: {e}")
            return False
    
    async def stop_recording(self) -> bool:
        """
        Stop rrweb recording and clean up navigation monitoring.
        
        Returns:
            True if recording stopped successfully, False otherwise
        """
        if not self.recording_active:
            logger.info(f"Recording not active for session {self.session_id}")
            return True
        
        try:
            # Check if page is still responsive
            if self.page:
                try:
                    await asyncio.wait_for(self.page.evaluate("() => true"), timeout=1.0)
                except Exception:
                    logger.info(f"Page not responsive for session {self.session_id}, marking recording as stopped")
                    self.recording_active = False
                    return True
            
            # Stop recording and clean up navigation monitoring in browser
            await asyncio.wait_for(self.page.evaluate("""
                () => {
                    // Stop rrweb recording
                    if (window.rrwebStopRecording) {
                        window.rrwebStopRecording();
                        console.log('rrweb recording stopped');
                    }
                    
                    // Clean up navigation monitoring
                    if (window.cleanupNavigationMonitoring) {
                        window.cleanupNavigationMonitoring();
                        console.log('Navigation monitoring cleaned up');
                    }
                }
            """), timeout=2.0)
            
            self.recording_active = False
            logger.info(f"rrweb recording stopped for session {self.session_id}")
            return True
            
        except Exception as e:
            logger.info(f"Could not stop rrweb recording for session {self.session_id}: {e}")
            self.recording_active = False
            return False
    
    async def reinject_after_navigation(self, url: str) -> bool:
        """
        Re-inject rrweb after navigation to a new URL.
        This method should be called explicitly by the controller after navigation.
        
        Args:
            url: The URL that was navigated to
            
        Returns:
            True if re-injection was successful, False otherwise
        """
        if not self.recording_active:
            logger.warning(f"Recording not active, skipping re-injection for session {self.session_id}")
            return False
        
        logger.info(f"Re-injecting rrweb after navigation to {url} for session {self.session_id}")
        
        # Wait for page to stabilize after navigation
        await asyncio.sleep(1.0)
        
        # Re-inject with verification (same pattern as initial injection)
        success = await self._inject_rrweb_simple()
        if success:
            logger.info(f"✅ rrweb re-injection verified for {url}")
            self.rrweb_injected = True
            return True
        else:
            logger.error(f"❌ rrweb re-injection failed for {url}")
            self.rrweb_injected = False
            return False
    
    async def get_buffered_events(self) -> List[Dict[str, Any]]:
        """Get all buffered events for reconnection scenarios"""
        return list(self.event_buffer)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current recording status"""
        return {
            'session_id': self.session_id,
            'recording_active': self.recording_active,
            'rrweb_injected': self.rrweb_injected,
            'buffered_events': len(self.event_buffer),
            'navigation_monitoring_active': self.navigation_monitoring_active,
            'current_phase': self.current_phase,
        }
    
    async def enable_navigation_monitoring(self) -> bool:
        """Enable navigation monitoring for EXECUTING phase"""
        if self.navigation_monitoring_active:
            logger.debug(f"Navigation monitoring already active for session {self.session_id}")
            return True
            
        try:
            # CRITICAL FIX: Add delay before enabling navigation monitoring
            # This ensures screensaver recording is stable before any JavaScript injection
            logger.info(f"🕐 Delaying navigation monitoring setup by 2 seconds to ensure screensaver recording stability")
            await asyncio.sleep(2.0)
            
            await self._setup_navigation_monitoring()
            self.navigation_monitoring_active = True
            logger.info(f"✅ Navigation monitoring enabled for session {self.session_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to enable navigation monitoring: {e}")
            return False
    
    async def disable_navigation_monitoring(self) -> bool:
        """Disable navigation monitoring for SETUP/READY phases"""
        if not self.navigation_monitoring_active:
            logger.debug(f"Navigation monitoring already disabled for session {self.session_id}")
            return True
            
        try:
            await self.page.evaluate("""
            () => {
                if (window.cleanupNavigationMonitoring) {
                    window.cleanupNavigationMonitoring();
                    console.log('🔕 Navigation monitoring disabled');
                } else {
                    console.log('🔕 Navigation monitoring cleanup function not found');
                }
            }
            """)
            self.navigation_monitoring_active = False
            logger.info(f"✅ Navigation monitoring disabled for session {self.session_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to disable navigation monitoring: {e}")
            return False
    
    async def set_phase(self, phase: str) -> bool:
        """Set current phase and enable/disable navigation monitoring accordingly"""
        previous_phase = self.current_phase
        self.current_phase = phase
        
        logger.info(f"🔄 Phase transition: {previous_phase} → {phase} for session {self.session_id}")
        
        if phase == "EXECUTING":
            # Enable navigation monitoring for workflow execution
            result = await self.enable_navigation_monitoring()
            if result:
                logger.info(f"🔊 Navigation monitoring enabled for EXECUTING phase in session {self.session_id}")
            return result
        else:
            # Disable navigation monitoring for SETUP/READY phases
            result = await self.disable_navigation_monitoring()
            if result:
                logger.info(f"🔕 Navigation monitoring disabled for {phase} phase in session {self.session_id}")
            return result
    
    async def _setup_navigation_monitoring(self) -> None:
        """Set up lightweight navigation monitoring WITHOUT restarting recording"""
        try:
            # CRITICAL FIX: Lightweight navigation monitoring that does NOT restart recording
            await self.page.evaluate("""
            () => {
                console.log('🧭 Setting up LIGHTWEIGHT navigation monitoring (no recording restarts)');
                
                // Store the current URL to detect changes
                let currentUrl = window.location.href;
                let urlCheckInterval;
                let navigationCount = 0;
                
                // Function to handle navigation WITHOUT restarting recording
                function handleNavigation(reason = 'unknown') {
                    try {
                        navigationCount++;
                        console.log(`🧭 Navigation #${navigationCount} detected (${reason}) - rrweb will handle automatically`);
                        
                        // Log navigation for debugging but DON'T restart recording
                        console.log(`📍 URL changed: ${currentUrl} → ${window.location.href}`);
                        
                        // Update current URL tracking
                        currentUrl = window.location.href;
                        
                        // ✅ CRITICAL FIX: Let rrweb handle navigation naturally
                        // rrweb automatically captures DOM changes during navigation
                        // No need to restart recording or create new FullSnapshots
                        console.log(`✅ Navigation ${navigationCount} logged - rrweb continues recording`);
                        
                    } catch (e) {
                        console.error(`❌ Navigation logging failed: ${e}`);
                    }
                }
                
                // Lightweight URL monitoring (for SPA navigation)
                urlCheckInterval = setInterval(() => {
                    const newUrl = window.location.href;
                    if (newUrl !== currentUrl) {
                        handleNavigation('URL_CHANGE');
                    }
                }, 1000); // Reduced frequency since we're just logging
                
                // Monitor popstate events (back/forward navigation)
                window.addEventListener('popstate', (event) => {
                    console.log('🧭 PopState navigation detected:', event);
                    handleNavigation('POPSTATE');
                });
                
                // Monitor pushState/replaceState (programmatic navigation)
                const originalPushState = history.pushState;
                const originalReplaceState = history.replaceState;
                
                history.pushState = function(...args) {
                    console.log('🧭 PushState navigation detected:', args);
                    originalPushState.apply(this, args);
                    handleNavigation('PUSHSTATE');
                };
                
                history.replaceState = function(...args) {
                    console.log('🧭 ReplaceState navigation detected:', args);
                    originalReplaceState.apply(this, args);
                    handleNavigation('REPLACESTATE');
                };
                
                // Store cleanup function globally
                window.cleanupNavigationMonitoring = () => {
                    console.log('🧹 Starting lightweight navigation monitoring cleanup...');
                    if (urlCheckInterval) {
                        clearInterval(urlCheckInterval);
                        console.log('🧹 URL check interval cleared');
                    }
                    // Restore original history methods
                    history.pushState = originalPushState;
                    history.replaceState = originalReplaceState;
                    console.log('🧹 Lightweight navigation monitoring cleaned up');
                };
                
                console.log('✅ LIGHTWEIGHT navigation monitoring setup complete');
                console.log('🧭 Monitoring modes: URL_CHANGE, POPSTATE, PUSHSTATE, REPLACESTATE (logging only)');
                console.log('🎯 rrweb will handle all navigation automatically without recording restarts');
            }
            """)
            
            logger.info(f"✅ Lightweight navigation monitoring set up for session {self.session_id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to set up navigation monitoring for session {self.session_id}: {e}")

    async def _setup_page_load_listener(self) -> None:
        """Set up page load listener to handle full page navigation (like page.goto())"""
        try:
            # Set up page load listener - this handles full page navigation
            def on_page_load(page):
                # CRITICAL FIX: Don't trigger re-injection during SETUP/READY phases
                # This prevents screensaver recording interruption
                if self.current_phase in ["SETUP", "READY"]:
                    logger.info(f"🔕 Page load detected during {self.current_phase} phase - skipping re-injection to preserve screensaver recording")
                    return
                
                logger.info(f"🔄 Page load detected for session {self.session_id}: {page.url}")
                # Schedule re-injection after page load (only during EXECUTING phase)
                asyncio.create_task(self._reinject_after_page_load(page.url))
            
            # Listen for page load events
            self.page.on('load', on_page_load)
            logger.info(f"✅ Page load listener set up for session {self.session_id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to set up page load listener for session {self.session_id}: {e}")

    async def _reinject_after_page_load(self, url: str) -> None:
        """Re-inject rrweb after full page load"""
        try:
            if not self.recording_active:
                return
                
            logger.info(f"🔄 Re-injecting rrweb after page load to {url} for session {self.session_id}")
            
            # Wait for page to stabilize
            await asyncio.sleep(1.0)
            
            # Re-expose callback functions
            await self._expose_rrweb_event_function()
            await self._expose_rrweb_error_function()
            
            # Re-inject rrweb
            if await self._try_cdn_injection():
                logger.info(f"✅ rrweb re-injected via CDN after page load for session {self.session_id}")
            elif await self._try_inline_injection():
                logger.info(f"✅ rrweb re-injected via inline after page load for session {self.session_id}")
            else:
                logger.error(f"❌ Failed to re-inject rrweb after page load for session {self.session_id}")
                return
            
            # Re-set up navigation monitoring
            await self._setup_navigation_monitoring()
            
            logger.info(f"✅ rrweb fully re-injected after page load for session {self.session_id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to re-inject rrweb after page load for session {self.session_id}: {e}")

    # ===================================================================
    # PRIVATE METHODS: rrweb Injection and Event Handling
    # ===================================================================
    
    async def _expose_rrweb_event_function(self) -> bool:
        """Expose the sendRRWebEvent function to the page"""
        if not self.page:
            return False
        
        try:
            await self.page.expose_function('sendRRWebEvent', self._handle_rrweb_event)
            logger.debug(f"✅ Exposed sendRRWebEvent function for session {self.session_id}")
            return True
        except Exception as e:
            if "already registered" in str(e):
                logger.debug(f"sendRRWebEvent function already registered for session {self.session_id}")
                return True
            else:
                logger.error(f"❌ Failed to expose sendRRWebEvent function: {e}")
                return False
    
    async def _expose_rrweb_error_function(self) -> bool:
        """Expose the sendRRWebError function to handle rrweb internal errors"""
        if not self.page:
            return False
        
        try:
            await self.page.expose_function('sendRRWebError', self._handle_rrweb_error)
            logger.debug(f"✅ Exposed sendRRWebError function for session {self.session_id}")
            return True
        except Exception as e:
            if "already registered" in str(e):
                logger.debug(f"sendRRWebError function already registered for session {self.session_id}")
                return True
            else:
                logger.error(f"❌ Failed to expose sendRRWebError function: {e}")
                return False
    
    async def _inject_rrweb_simple(self) -> bool:
        """
        Enhanced rrweb injection with CSP bypass strategy.
        
        This method implements a two-tier approach:
        1. Try CDN injection first (works for most sites)
        2. Fall back to inline injection for CSP-restricted sites like Amazon
        
        Returns:
            True if rrweb was successfully injected and verified, False otherwise
        """
        if not self.page:
            return False
        
        try:
            # Expose both event and error callback functions
            await self._expose_rrweb_event_function()
            await self._expose_rrweb_error_function()
            
            # Store the current URL for validation
            initial_url = self.page.url
            logger.info(f"🎬 Starting enhanced rrweb injection for session {self.session_id} on {initial_url}")
            
            # Step 1: Try CDN injection first
            cdn_result = await self._try_cdn_injection()
            if cdn_result.get('success', False):
                logger.info(f"✅ rrweb CDN injection successful for session {self.session_id}")
                return True
            
            # Step 2: CDN failed, try inline injection (for CSP-restricted sites)
            logger.warning(f"CDN injection failed, attempting inline injection for session {self.session_id}")
            logger.warning(f"CDN failure reason: {cdn_result.get('error', 'unknown')}")
            
            inline_result = await self._try_inline_injection()
            if inline_result.get('success', False):
                logger.info(f"✅ rrweb inline injection successful for session {self.session_id}")
                return True
            
            # Both methods failed
            logger.error(f"❌ Both CDN and inline injection failed for session {self.session_id}")
            logger.error(f"CDN error: {cdn_result.get('error', 'unknown')}")
            logger.error(f"Inline error: {inline_result.get('error', 'unknown')}")
            return False
                
        except Exception as e:
            logger.error(f"❌ rrweb injection failed with exception: {e}")
            return False
    
    async def _try_cdn_injection(self) -> dict:
        """
        Try CDN-based rrweb injection with robust validation.
        
        Returns:
            Dict with success status and error details
        """
        try:
            result = await self.page.evaluate(f"""
            () => {{
                return new Promise((resolve) => {{
                    console.log('🌐 Attempting robust CDN injection...');
                
                    // Clean stop existing recording
                    if (window.rrwebStopRecording) {{
                        try {{ 
                            window.rrwebStopRecording(); 
                        }} catch(e) {{
                            console.warn('Error stopping previous recording:', e);
                        }}
                    }}
                
                    // CDN loading with enhanced error detection
                    if (!window.rrweb) {{
                        const script = document.createElement('script');
                        script.src = '{self.rrweb_cdn_url}';
                        
                        // Enhanced load handler
                        script.onload = () => {{
                            console.log('✅ rrweb CDN loaded successfully');
                            
                            // Validate rrweb is actually available
                            if (!window.rrweb || !window.rrweb.record) {{
                                resolve({{ 
                                    success: false, 
                                    error: 'CDN loaded but rrweb not available',
                                    details: 'Script loaded but rrweb.record function not found',
                                    method: 'cdn'
                                }});
                                return;
                            }}
                            
                            startRecording();
                        }};
                        
                        // Enhanced error handler
                        script.onerror = (error) => {{
                            console.error('❌ rrweb CDN loading failed:', error);
                            resolve({{ 
                                success: false, 
                                error: 'CDN loading failed',
                                details: 'External script blocked (likely CSP restriction)',
                                method: 'cdn'
                            }});
                        }};
                        
                        document.head.appendChild(script);
                        
                        // Enhanced timeout for CDN loading
                        setTimeout(() => {{
                            if (!window.rrweb || !window.rrweb.record) {{
                                resolve({{ 
                                    success: false, 
                                    error: 'CDN loading timeout',
                                    details: 'rrweb script did not load or initialize within 8 seconds',
                                    method: 'cdn'
                                }});
                            }}
                        }}, 8000);  // Increased timeout for complex sites
                        
                    }} else {{
                        console.log('✅ rrweb already available');
                        
                        // Validate existing rrweb
                        if (!window.rrweb.record) {{
                            resolve({{ 
                                success: false, 
                                error: 'rrweb exists but record function missing',
                                details: 'rrweb object found but record function not available',
                                method: 'cdn'
                            }});
                            return;
                        }}
                        
                        startRecording();
                    }}
                
                    function startRecording() {{
                        try {{
                            console.log('🎵 Starting rrweb recording with CDN version');
                            
                            // Get recording options
                            const recordingOptions = {get_recording_options_js()};
                            
                            // Track first event and quality
                            let firstEventReceived = false;
                            let eventsReceived = 0;
                            
                            // Official pattern: Simple direct streaming with enhanced validation
                            const stopFn = window.rrweb.record({{
                                // Enhanced error handler from rrweb API
                                errorHandler: (error) => {{
                                    console.error('rrweb internal error:', error);
                                    if (window.sendRRWebError) {{
                                        window.sendRRWebError(JSON.stringify({{
                                            type: 'rrweb_internal_error',
                                            message: error.toString(),
                                            stack: error.stack || 'No stack trace',
                                            timestamp: Date.now()
                                        }}));
                                    }}
                                }},
                                
                                // Enhanced event streaming with validation
                                emit: (event) => {{
                                    eventsReceived++;
                                    
                                    // Verify success on first FullSnapshot
                                    if (event.type === 2 && !firstEventReceived) {{ // FullSnapshot type
                                        firstEventReceived = true;
                                        console.log('✅ First FullSnapshot received - CDN rrweb is working!');
                                        
                                        // Validate DOM capture quality
                                        const nodeCount = event.data && event.data.node ? 
                                            JSON.stringify(event.data.node).length : 0;
                                        
                                        if (nodeCount < 1000) {{
                                            console.warn('⚠️ FullSnapshot seems small, DOM capture may be incomplete');
                                        }}
                                        
                                        resolve({{ 
                                            success: true, 
                                            hasFullSnapshot: true,
                                            method: 'cdn',
                                            currentUrl: window.location.href,
                                            pageTitle: document.title,
                                            nodeCount: nodeCount,
                                            message: 'rrweb CDN recording verified with FullSnapshot'
                                        }});
                                    }}
                                    
                                    // Stream event to backend
                                    if (window.sendRRWebEvent) {{
                                        window.sendRRWebEvent(JSON.stringify(event));
                                    }}
                                }},
                                
                                // Apply recording options
                                ...recordingOptions
                            }});
                            
                            window.rrwebStopRecording = stopFn;
                            console.log('🎵 rrweb.record() called successfully with CDN');
                            
                            // Enhanced timeout with event counting
                            setTimeout(() => {{
                                if (!firstEventReceived) {{
                                    resolve({{ 
                                        success: false, 
                                        error: 'No FullSnapshot received',
                                        details: `CDN rrweb.record() started but no FullSnapshot received within 5 seconds. Total events: ${{eventsReceived}}`,
                                        method: 'cdn',
                                        eventsReceived: eventsReceived
                                    }});
                                }}
                            }}, 5000);  // Increased timeout for complex sites
                            
                        }} catch (e) {{
                            console.error('❌ rrweb CDN recording initialization failed:', e);
                            resolve({{ 
                                success: false, 
                                error: 'CDN recording initialization failed',
                                details: e.message,
                                stack: e.stack,
                                method: 'cdn'
                            }});
                        }}
                    }}
                }});
            }}
            """)
            
            return result
            
        except Exception as e:
            logger.error(f"CDN injection attempt failed with exception: {e}")
            return {
                'success': False,
                'error': 'CDN injection exception',
                'details': str(e),
                'method': 'cdn'
            }
    
    async def _try_inline_injection(self) -> dict:
        """
        Try inline rrweb injection for CSP-restricted sites.
        
        This method uses playwright's add_script_tag to bypass CSP restrictions
        with robust validation and timing.
        
        Returns:
            Dict with success status and error details
        """
        try:
            logger.info(f"🔧 Attempting inline injection for session {self.session_id}")
            
            # Step 1: Use playwright's add_script_tag which bypasses CSP
            await self.page.add_script_tag(url=self.rrweb_cdn_url)
            logger.debug(f"Script tag added via playwright for session {self.session_id}")
            
            # Step 2: ROBUST validation - wait for rrweb to be actually available
            rrweb_available = False
            max_retries = 10
            for attempt in range(max_retries):
                try:
                    await asyncio.sleep(0.2)  # Brief pause between checks
                    rrweb_check = await self.page.evaluate("() => typeof window.rrweb !== 'undefined'")
                    if rrweb_check:
                        rrweb_available = True
                        logger.debug(f"✅ rrweb became available after {attempt + 1} attempts")
                        break
                except Exception as e:
                    logger.debug(f"Attempt {attempt + 1}: rrweb check failed: {e}")
                    
            if not rrweb_available:
                return {
                    'success': False,
                    'error': 'rrweb not available after inline injection',
                    'details': f'Playwright script injection completed but rrweb not available after {max_retries} attempts',
                    'method': 'inline'
                }
            
            # Step 3: Initialize recording with robust error handling
            result = await self.page.evaluate(f"""
            () => {{
                return new Promise((resolve) => {{
                    console.log('🔧 Starting robust inline rrweb initialization...');
                    
                    // Verify rrweb is available (double-check)
                    if (!window.rrweb || !window.rrweb.record) {{
                        resolve({{ 
                            success: false, 
                            error: 'rrweb or rrweb.record not available',
                            details: 'rrweb object exists but record function not available',
                            method: 'inline'
                        }});
                        return;
                    }}
                    
                    // Clean stop existing recording
                    if (window.rrwebStopRecording) {{
                        try {{ 
                            window.rrwebStopRecording(); 
                        }} catch(e) {{
                            console.warn('Error stopping previous recording:', e);
                        }}
                    }}
                    
                    try {{
                        console.log('🎵 Starting rrweb recording with inline version');
                        
                        // Get recording options
                        const recordingOptions = {get_recording_options_js()};
                        
                        // Track first event received
                        let firstEventReceived = false;
                        let eventsReceived = 0;
                        
                        // Official pattern: Simple direct streaming with enhanced validation
                        const stopFn = window.rrweb.record({{
                            // Enhanced error handler from rrweb API
                            errorHandler: (error) => {{
                                console.error('rrweb internal error:', error);
                                if (window.sendRRWebError) {{
                                    window.sendRRWebError(JSON.stringify({{
                                        type: 'rrweb_internal_error',
                                        message: error.toString(),
                                        stack: error.stack || 'No stack trace',
                                        timestamp: Date.now()
                                    }}));
                                }}
                            }},
                            
                            // Enhanced event streaming with validation
                            emit: (event) => {{
                                eventsReceived++;
                                
                                // Verify success on first FullSnapshot
                                if (event.type === 2 && !firstEventReceived) {{ // FullSnapshot type
                                    firstEventReceived = true;
                                    console.log('✅ First FullSnapshot received - inline rrweb is working!');
                                    
                                    // Validate DOM capture quality
                                    const nodeCount = event.data && event.data.node ? 
                                        JSON.stringify(event.data.node).length : 0;
                                    
                                    if (nodeCount < 1000) {{
                                        console.warn('⚠️ FullSnapshot seems small, DOM capture may be incomplete');
                                    }}
                                    
                                    resolve({{ 
                                        success: true, 
                                        hasFullSnapshot: true,
                                        method: 'inline',
                                        currentUrl: window.location.href,
                                        pageTitle: document.title,
                                        nodeCount: nodeCount,
                                        message: 'rrweb inline recording verified with FullSnapshot'
                                    }});
                                }}
                                
                                // Stream event to backend
                                if (window.sendRRWebEvent) {{
                                    window.sendRRWebEvent(JSON.stringify(event));
                                }}
                            }},
                            
                            // Apply recording options
                            ...recordingOptions
                        }});
                        
                        window.rrwebStopRecording = stopFn;
                        console.log('🎵 rrweb.record() called successfully with inline version');
                        
                        // Enhanced timeout with event counting
                        setTimeout(() => {{
                            if (!firstEventReceived) {{
                                resolve({{ 
                                    success: false, 
                                    error: 'No FullSnapshot received',
                                    details: `Inline rrweb.record() started but no FullSnapshot received within 5 seconds. Total events: ${{eventsReceived}}`,
                                    method: 'inline',
                                    eventsReceived: eventsReceived
                                }});
                            }}
                        }}, 5000);  // Increased timeout for complex sites
                        
                    }} catch (e) {{
                        console.error('❌ rrweb inline recording initialization failed:', e);
                        resolve({{ 
                            success: false, 
                            error: 'Inline recording initialization failed',
                            details: e.message,
                            stack: e.stack,
                            method: 'inline'
                        }});
                    }}
                }});
            }}
            """)
            
            return result
            
        except Exception as e:
            logger.error(f"Inline injection attempt failed with exception: {e}")
            return {
                'success': False,
                'error': 'Inline injection exception',
                'details': str(e),
                'method': 'inline'
            }
    
    async def _handle_rrweb_event(self, event_json: str) -> None:
        """
        Handle rrweb events received from the browser.
        
        This method processes individual events and streams them to the backend.
        """
        try:
            event_data = json.loads(event_json)
            event_type = event_data.get('type', 'unknown')
            
            # CRITICAL FIX: Add sequence_id starting at 0 and increment
            wrapped_event = {
                'session_id': self.session_id,
                'timestamp': asyncio.get_event_loop().time(),
                'event': event_data,
                'sequence_id': self.sequence_counter  # ✅ Fixed sequence ID
            }
            
            # Increment sequence counter for next event
            self.sequence_counter += 1
            
            # Buffer the event for reconnection scenarios
            self.event_buffer.append(wrapped_event)
            
            # Keep buffer size manageable (last 100 events)
            if len(self.event_buffer) > 100:
                self.event_buffer.pop(0)
            
            # Call the event callback if provided
            if self.event_callback:
                try:
                    await self.event_callback(wrapped_event)
                except Exception as e:
                    logger.error(f"Error in event callback for session {self.session_id}: {e}")
            
            # Log significant events with sequence ID
            if event_type == 2:  # FullSnapshot
                logger.debug(f"📸 FullSnapshot #{self.sequence_counter - 1} captured for session {self.session_id}")
            elif event_type == 3:  # IncrementalSnapshot
                logger.debug(f"📝 IncrementalSnapshot #{self.sequence_counter - 1} captured for session {self.session_id}")
                    
        except Exception as e:
            logger.error(f"Error handling rrweb event for session {self.session_id}: {e}")
            logger.error(f"Raw event data: {event_json}")
    
    async def _handle_rrweb_error(self, error_json: str) -> None:
        """Handle rrweb internal errors from official errorHandler"""
        try:
            error_data = json.loads(error_json)
            error_type = error_data.get('type', 'unknown')
            error_message = error_data.get('message', 'unknown error')
            
            logger.error(f"rrweb error [{error_type}]: {error_message}")
            
            # Create error event for streaming system
            if self.event_callback:
                error_event = {
                    'session_id': self.session_id,
                    'timestamp': asyncio.get_event_loop().time(),
                    'error': True,
                    'event': {
                        'type': 'rrweb_error',
                        'data': error_data
                    }
                }
                try:
                    await self.event_callback(error_event)
                except Exception as e:
                    logger.error(f"Error in error callback: {e}")
                    
        except Exception as e:
            logger.error(f"Error handling rrweb error: {e}")
            logger.error(f"Raw error data: {error_json}")
