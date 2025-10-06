"""
Browser Profile Manager

Managing user profiles and session directories for browseruse BrowserProfile
Separates user-persistent data from temporary session data.
"""

import os
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class BrowserProfileManager:
    """
    Manages browser profiles and session directories with clean separation:
    
    - User Profiles: Persistent data stored in ~/.browseruse/profiles/{user_id}/
      Contains: cookies, login sessions, preferences, bookmarks
      
    - Session Directories: Temporary data for workflow execution
      Contains: cache, temp files, workflow-specific data
      Cleaned up after each session
    """
    
    def __init__(self):
        self.base_profile_dir = Path.home() / ".browseruse" / "profiles"
        self.base_session_dir = Path(tempfile.gettempdir()) / "browseruse_sessions"
        
        # Ensure base directories exist
        self.base_profile_dir.mkdir(parents=True, exist_ok=True)
        self.base_session_dir.mkdir(parents=True, exist_ok=True)
    
    def get_user_profile_dir(self, user_id: str) -> Path:
        """
        Get or create user profile directory for persistent data.
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            Path to user's persistent profile directory
        """
        user_profile_dir = self.base_profile_dir / user_id
        user_profile_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"User profile directory: {user_profile_dir}")
        return user_profile_dir
    
    def get_session_dir(self, session_id: str) -> Path:
        """
        Get or create session directory for temporary data.
        
        Args:
            session_id: Unique identifier for the session
            
        Returns:
            Path to session's temporary directory
        """
        session_dir = self.base_session_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Session directory: {session_dir}")
        return session_dir
    
    def cleanup_session(self, session_id: str) -> bool:
        """
        Clean up session directory after workflow completion.
        
        Args:
            session_id: Session identifier to clean up
            
        Returns:
            True if cleanup successful, False otherwise
        """
        try:
            session_dir = self.base_session_dir / session_id
            if session_dir.exists():
                # Kill any lingering zombieChromium processes using this session directory
                try:
                    killed = self.kill_chromium_processes_for_dir(session_dir)
                    if killed:
                        logger.info(f"Killed {killed} Chromium processes for session {session_id}")
                except Exception as _e:
                    logger.debug(f"Failed to kill Chromium processes for {session_id}: {_e}")
                # Remove Chromium singleton lock artifacts if present
                self._remove_chromium_singleton_locks(session_dir)
                shutil.rmtree(session_dir, ignore_errors=True)
                logger.info(f"Cleaned up session directory: {session_dir}")
                return True
            return True
        except Exception as e:
            logger.error(f"Error cleaning up session {session_id}: {e}")
            return False
    
    def cleanup_old_sessions(self, max_age_hours: int = 24) -> int:
        """
        Clean up old session directories to prevent disk space issues.
        
        Args:
            max_age_hours: Maximum age of sessions to keep (default: 24 hours)
            
        Returns:
            Number of sessions cleaned up
        """
        import time
        
        cleaned_count = 0
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        try:
            for session_dir in self.base_session_dir.iterdir():
                if session_dir.is_dir():
                    # Check if directory is older than max_age
                    dir_age = current_time - session_dir.stat().st_mtime
                    if dir_age > max_age_seconds:
                        shutil.rmtree(session_dir, ignore_errors=True)
                        logger.info(f"Cleaned up old session: {session_dir.name}")
                        cleaned_count += 1
        except Exception as e:
            logger.error(f"Error during old session cleanup: {e}")
        
        logger.info(f"Cleaned up {cleaned_count} old sessions")
        return cleaned_count

    def _remove_chromium_singleton_locks(self, directory: Path) -> None:
        """Best-effort removal of Chromium ProcessSingleton lock files.

        This is safe to call on both ephemeral session dirs and persistent profiles.
        For persistent profiles, we only delete lock artifacts; the profile remains.
        """
        try:
            patterns = [
                'SingletonLock',
                'SingletonCookie',
                'SingletonSocket',
            ]
            removed = 0
            for name in patterns:
                target = directory / name
                if target.exists():
                    try:
                        target.unlink()
                        removed += 1
                    except Exception:
                        pass
            if removed:
                logger.info(f"Removed {removed} Chromium Singleton* lock files from {directory}")
        except Exception as e:
            logger.debug(f"Failed to remove singleton locks in {directory}: {e}")
    
    # Enhance post-failure cleanup
    def kill_chromium_processes_for_dir(self, directory: Path) -> int:
        """Kill Chromium/Chrome processes whose cmdline references the given directory.

        Returns number of processes killed (best-effort). Falls back to pkill if psutil is unavailable.
        """
        killed_count = 0
        dir_str = str(directory)
        try:
            import psutil  # type: ignore
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    name = (proc.info.get('name') or '').lower()
                    if not name:
                        continue
                    if 'chrome' in name or 'chromium' in name:
                        cmdline = proc.info.get('cmdline') or []
                        if any(dir_str in (arg or '') for arg in cmdline):
                            try:
                                proc.kill()
                                proc.wait(timeout=3)
                                killed_count += 1
                            except Exception:
                                # Best-effort; continue attempting others
                                continue
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                    continue
        except Exception:
            # Fallback: try pkill by directory path match (may not report count)
            try:
                import subprocess  # type: ignore
                subprocess.run(['pkill', '-f', dir_str], check=False, capture_output=True)
            except Exception:
                pass
        return killed_count
    
    def get_user_profile_info(self, user_id: str) -> Dict[str, Any]:
        """
        Get information about user's profile.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary with profile information
        """
        profile_dir = self.get_user_profile_dir(user_id)
        
        # Calculate profile size
        total_size = 0
        file_count = 0
        for root, dirs, files in os.walk(profile_dir):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    total_size += os.path.getsize(file_path)
                    file_count += 1
                except (OSError, IOError):
                    pass
        
        return {
            'user_id': user_id,
            'profile_path': str(profile_dir),
            'exists': profile_dir.exists(),
            'size_bytes': total_size,
            'file_count': file_count,
            'created_time': profile_dir.stat().st_ctime if profile_dir.exists() else None,
            'modified_time': profile_dir.stat().st_mtime if profile_dir.exists() else None
        }
    
    def create_browser_profile_config(self, session_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create browser profile configuration for session.
        
        Args:
            session_id: Session identifier
            user_id: Optional user identifier for persistent profile features
            
        Returns:
            Configuration dictionary for BrowserProfile
        """
        # Always use session directory for user_data_dir to avoid conflicts
        session_dir = self.get_session_dir(session_id)
        
        config = {
            'user_data_dir': str(session_dir),
            'headless': True,
            'disable_security': True,
            # Keep the browser session alive across step-level agent tasks,
            # So Agent won’t auto-close the browser after a single step’s fallback success.
            # visual/streaming workflows can continue executing subsequent steps.
            'keep_alive': True,
            
            # 🎯 CRITICAL: Enable CSP bypass for rrweb recording (like official rrweb implementation)
            'bypass_csp': True,
            
            # 🖥️ Viewport configuration for visual recording
            'viewport': {'width': 1920, 'height': 1080},
            'window_size': {'width': 1920, 'height': 1080},
            
            'args': [
                # CORE SECURITY AND CSP BYPASS (deduplicated)
                '--disable-web-security',
                '--allow-running-insecure-content',
                '--disable-security-warnings',
                '--disable-extensions',
                '--disable-site-isolation-trials',
                '--disable-site-isolation-for-policy',
                
                '--disable-features=CORSMismatchKillSwitch',
                '--disable-features=SameSiteByDefaultCookies',
                '--disable-features=CookiesWithoutSameSiteMustBeSecure',

                # CONTENT SCRIPT INJECTION / MISC
                '--disable-features=ScriptStreaming',
                '--js-flags=--expose-gc',

                # CERT/SSL RELAXATIONS
                '--ignore-ssl-errors-spki-list',
                '--ignore-ssl-errors',
                '--ignore-certificate-errors-spki-list',
                '--ignore-certificate-errors',
                '--disable-certificate-transparency-logs',

                # USER AGENT AND AUTOMATION HIDING
                '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                '--no-first-run',
                '--disable-default-browser-check',
                # '--disable-blink-features=AutomationControlled', # TODO: Remove this for LinkedIn auth?
                '--disable-infobars',
                '--password-store=basic',
                '--use-mock-keychain',
                '--no-service-autorun',

                # CONTAINER/HEADLESS STABILITY
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
				'--no-zygote',

                '--disable-gpu',
                '--disable-gpu-sandbox',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
                '--disable-features=TranslateUI',

                # Dbus safety
                # DBus / Audio / Ozone safety for headless containers
                '--no-default-browser-check',
                '--noerrdialogs',
                '--autoplay-policy=no-user-gesture-required',
                '--disable-features=AudioServiceOutOfProcess',
                '--disable-features=UseOzonePlatform',
                '--disable-features=MediaSessionService',
                '--no-sandbox-and-elevated',
                '--disable-dev-tools',
                '--disable-breakpad',
                '--disable-crash-reporter',
                '--disable-in-process-stack-traces',
                '--disable-logging',
                '--mute-audio',
                '--allow-pre-commit-input',
                '--force-color-profile=srgb',
                '--force-device-scale-factor=1',

                # PERFORMANCE OPTIMIZATIONS FOR RECORDING
                
                '--disable-software-rasterizer',

                # CRITICAL: MEMORY CAP
                '--max_old_space_size=512',
            ]
        }
        
        # TODO: Future enhancement: If user_id provided, copy persistent data
        if user_id:
            logger.info(f"Session {session_id} associated with user {user_id}")
            # TODO: Copy user preferences, cookies, etc. from user profile
            # user_profile_dir = self.get_user_profile_dir(user_id)
            # self._copy_user_data_to_session(user_profile_dir, session_dir)
        
        # In production containers, prefer Playwright-managed Chromium binary to avoid CDP connection issues
        try:
            is_production = os.getenv('RAILWAY_ENVIRONMENT') is not None or os.getenv('RENDER') is not None
            if is_production:
                # Common Playwright Chromium locations (keep list short and fast)
                candidates = [
                    "/root/.cache/ms-playwright/chromium-1180/chrome-linux/chrome",
                    "/root/.cache/ms-playwright/chromium-1179/chrome-linux/chrome",
                    "/root/.cache/ms-playwright/chromium-1169/chrome-linux/chrome",
                ]
                chromium_path = None
                for p in candidates:
                    if os.path.exists(p):
                        chromium_path = p
                        break
                # Fallback: scan ms-playwright directory shallowly
                if chromium_path is None:
                    base_dir = "/root/.cache/ms-playwright"
                    if os.path.exists(base_dir):
                        try:
                            for name in sorted(os.listdir(base_dir), reverse=True):
                                maybe = os.path.join(base_dir, name, "chrome-linux", "chrome")
                                if os.path.exists(maybe):
                                    chromium_path = maybe
                                    break
                        except Exception:
                            pass
                if chromium_path:
                    config['executable_path'] = chromium_path
                    logger.info(f"Using Playwright Chromium binary: {chromium_path}")
        except Exception as e:
            logger.debug(f"Chromium executable detection failed: {e}")
        
        return config


# Global instance for easy access
profile_manager = BrowserProfileManager()