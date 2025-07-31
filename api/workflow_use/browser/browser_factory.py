#!/usr/bin/env python3
"""
BrowserFactory: Single responsibility browser lifecycle management

This class provides clean browser creation and management, replacing the scattered
browser creation patterns throughout the codebase.

Key responsibilities:
- Create workflow browsers using WorkflowService._create_browser_instance()
- Start browsers and verify they're ready
- Create browser + rrweb recorder combinations (atomic operation)
- Browser cleanup and resource management

What it DOESN'T do:
- rrweb injection or management (delegated to RRWebRecorder)
- Visual streaming setup (delegated to RRWebStreamersManager)
- Workflow execution (stays in WorkflowService)
"""

import asyncio
import logging
from typing import Optional, Tuple, Callable, Dict, Any, List
from browser_use import Browser
from browser_use.browser import BrowserProfile
from playwright.async_api import Page

from .profile_manager import profile_manager
from .custom_screensaver import show_custom_dvd_screensaver
from ..rrweb.recorder import RRWebRecorder

logger = logging.getLogger(__name__)


class BrowserFactory:
    """
    Factory for creating browsers with optional rrweb recording.
    
    Single Responsibility: Browser lifecycle management and atomic creation.
    Does NOT handle recording details - that's RRWebRecorder's job.
    """
    
    def __init__(self):
        """Initialize the browser factory."""
        self._active_sessions: Dict[str, Dict[str, Any]] = {}
        logger.info("BrowserFactory initialized")
    
    async def create_browser_with_rrweb(
        self, 
        mode: str, 
        session_id: str, 
        event_callback: Optional[Callable] = None,
        user_id: Optional[str] = None,
        headless: bool = True
    ) -> Tuple[Browser, RRWebRecorder]:
        """
        Create a browser with rrweb recording capability.
        
        This method creates a complete browser+recorder setup atomically.
        If any step fails, the entire operation fails fast.
        
        Args:
            mode: Browser mode (e.g., 'visual', 'headless')
            session_id: Unique session identifier
            event_callback: Callback function for rrweb events
            user_id: Optional user identifier for profile management
            headless: Whether to run browser in headless mode
            
        Returns:
            Tuple of (Browser, RRWebRecorder) ready for use
            
        Raises:
            RuntimeError: If browser creation or recorder setup fails
        """
        logger.info(f"Creating browser with rrweb for session {session_id} (mode: {mode})")
        
        try:
            # Step 1: Create browser instance
            browser = await self._create_browser_instance(
                session_id=session_id,
                user_id=user_id,
                headless=headless
            )
            
            # Step 2: Get the browser page
            page = await self._get_browser_page(browser, session_id)
            
            # Step 3: Show screensaver (for visual modes)
            if mode == 'visual':
                await self._setup_screensaver(page, session_id)
            
            # Step 4: Create RRWebRecorder
            recorder = RRWebRecorder(
                session_id=session_id,
                page=page,
                event_callback=event_callback
            )
            
            # Step 5: Attach recorder to browser for controller access
            browser._rrweb_recorder = recorder
            logger.debug(f"Attached _rrweb_recorder to browser for session {session_id}")
            
            # Step 6: Store session information
            self._active_sessions[session_id] = {
                'browser': browser,
                'recorder': recorder,
                'mode': mode,
                'created_at': asyncio.get_event_loop().time()
            }
            
            logger.info(f"✅ Browser+Recorder created successfully for session {session_id}")
            return browser, recorder
            
        except Exception as e:
            logger.error(f"❌ Failed to create browser with rrweb for session {session_id}: {e}")
            # Clean up any partial state
            await self._cleanup_failed_creation(session_id)
            raise RuntimeError(f"Browser creation failed for session {session_id}: {e}")
    
    async def create_browser_only(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        headless: bool = True
    ) -> Browser:
        """
        Create a browser without rrweb recording.
        
        Args:
            session_id: Unique session identifier  
            user_id: Optional user identifier for profile management
            headless: Whether to run browser in headless mode
            
        Returns:
            Browser instance ready for use
            
        Raises:
            RuntimeError: If browser creation fails
        """
        logger.info(f"Creating browser-only for session {session_id}")
        
        try:
            # Create browser instance
            browser = await self._create_browser_instance(
                session_id=session_id,
                user_id=user_id,
                headless=headless
            )
            
            # Store session information (no recorder)
            self._active_sessions[session_id] = {
                'browser': browser,
                'recorder': None,
                'mode': 'browser_only',
                'created_at': asyncio.get_event_loop().time()
            }
            
            logger.info(f"✅ Browser-only created successfully for session {session_id}")
            return browser
            
        except Exception as e:
            logger.error(f"❌ Failed to create browser-only for session {session_id}: {e}")
            await self._cleanup_failed_creation(session_id)
            raise RuntimeError(f"Browser creation failed for session {session_id}: {e}")
    
    async def cleanup_session(self, session_id: str) -> bool:
        """
        Clean up a session and its resources.
        
        Args:
            session_id: Session to clean up
            
        Returns:
            True if cleanup was successful, False otherwise
        """
        if session_id not in self._active_sessions:
            logger.warning(f"Session {session_id} not found for cleanup")
            return False
        
        logger.info(f"Cleaning up session {session_id}")
        
        try:
            session_info = self._active_sessions[session_id]
            
            # Stop recorder if present
            recorder = session_info.get('recorder')
            if recorder:
                await recorder.stop_recording()
                logger.debug(f"Recorder stopped for session {session_id}")
            
            # Close browser
            browser = session_info.get('browser')
            if browser:
                await browser.close()
                logger.debug(f"Browser closed for session {session_id}")
            
            # Clean up profile
            profile_manager.cleanup_session(session_id)
            logger.debug(f"Profile cleaned up for session {session_id}")
            
            # Remove from active sessions
            del self._active_sessions[session_id]
            
            logger.info(f"✅ Session {session_id} cleaned up successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error cleaning up session {session_id}: {e}")
            # Remove from active sessions even if cleanup had issues
            self._active_sessions.pop(session_id, None)
            return False
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get information about an active session"""
        session_info = self._active_sessions.get(session_id)
        if not session_info:
            return None
        
        return {
            'session_id': session_id,
            'mode': session_info['mode'],
            'created_at': session_info['created_at'],
            'has_recorder': session_info['recorder'] is not None,
            'browser_active': session_info['browser'] is not None
        }
    
    def list_active_sessions(self) -> List[str]:
        """Get list of active session IDs"""
        return list(self._active_sessions.keys())
    
    async def get_browser_for_session(self, session_id: str) -> Optional[Browser]:
        """Get browser instance for a session"""
        session_info = self._active_sessions.get(session_id)
        return session_info.get('browser') if session_info else None
    
    async def get_recorder_for_session(self, session_id: str) -> Optional[RRWebRecorder]:
        """Get recorder instance for a session"""
        session_info = self._active_sessions.get(session_id)
        return session_info.get('recorder') if session_info else None
    
    # ===================================================================
    # PRIVATE METHODS: Browser Creation Steps
    # ===================================================================
    
    async def _create_browser_instance(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        headless: bool = True
    ) -> Browser:
        """
        Create the actual browser instance with profile.
        
        Raises:
            RuntimeError: If browser creation fails
        """
        try:
            # Get browser profile configuration
            config = profile_manager.create_browser_profile_config(
                session_id=session_id,
                user_id=user_id
            )
            
            # Override with method parameters
            config.update({
                'headless': headless
            })
            
            logger.debug(f"Using profile config for session {session_id}")
            
            # Create browser with profile
            profile = BrowserProfile(**config)
            browser = Browser(browser_profile=profile)
            
            # Start the browser
            await browser.start()
            logger.debug(f"Browser instance created and started for session {session_id}")
            
            return browser
            
        except Exception as e:
            logger.error(f"Failed to create browser instance for session {session_id}: {e}")
            raise RuntimeError(f"Browser instance creation failed: {e}")
    
    async def _get_browser_page(self, browser: Browser, session_id: str) -> Page:
        """
        Get the main page from the browser.
        
        Raises:
            RuntimeError: If page retrieval fails
        """
        try:
            # Get the browser's page
            page = await browser.get_current_page()
            if not page:
                raise RuntimeError("Browser page not available")
            
            logger.debug(f"Browser page retrieved for session {session_id}")
            return page
            
        except Exception as e:
            logger.error(f"Failed to get browser page for session {session_id}: {e}")
            raise RuntimeError(f"Page retrieval failed: {e}")
    
    async def _setup_screensaver(self, page: Page, session_id: str) -> None:
        """
        Setup screensaver for visual mode with verification.
        
        Raises:
            RuntimeError: If screensaver setup fails
        """
        try:
            logger.debug(f"Setting up screensaver for session {session_id}")
            
            # Navigate to about:blank first if needed
            if page.url == '' or page.url == 'about:blank':
                await page.goto('about:blank', timeout=10000)
            
            # Show the real bouncing DVD screensaver (with JavaScript physics)
            await show_custom_dvd_screensaver(page)
            
            # 🎯 SIMPLE: Verify rich content was created (static approach guarantees success)
            content_check = await page.evaluate("""
                () => {
                    const overlay = document.getElementById('pretty-loading-animation');
                    const totalElements = document.querySelectorAll('*').length;
                    const sparkles = document.querySelectorAll('.sparkle').length;
                    
                    return {
                        overlayExists: !!overlay,
                        totalElements: totalElements,
                        sparkles: sparkles,
                        richContent: totalElements > 30  // Static approach should create 40+ elements
                    };
                }
            """)
            
            if content_check['richContent']:
                logger.info(f"✅ Rich screensaver content created for session {session_id}")
                logger.info(f"   Total elements: {content_check['totalElements']}")
                logger.info(f"   Sparkles: {content_check['sparkles']}")
            else:
                logger.warning(f"⚠️ Expected rich content but only got {content_check['totalElements']} elements")
            
            logger.debug(f"Static screensaver setup completed for session {session_id}")
            
        except Exception as e:
            logger.error(f"Failed to setup screensaver for session {session_id}: {e}")
            raise RuntimeError(f"Screensaver setup failed: {e}")
    
    async def _cleanup_failed_creation(self, session_id: str) -> None:
        """Clean up any partial state from failed browser creation"""
        try:
            # Remove from active sessions if present
            if session_id in self._active_sessions:
                session_info = self._active_sessions[session_id]
                
                # Try to close browser if it was created
                browser = session_info.get('browser')
                if browser:
                    try:
                        await browser.close()
                    except Exception:
                        pass  # Ignore cleanup errors
                
                del self._active_sessions[session_id]
            
            # Clean up profile
            profile_manager.cleanup_session(session_id)
            
        except Exception as e:
            logger.debug(f"Error during failed creation cleanup for session {session_id}: {e}")


# Global factory instance
browser_factory = BrowserFactory()
