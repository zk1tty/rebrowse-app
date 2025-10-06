import asyncio
import sys
import os

import uvicorn
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import time
import uuid
import jwt
import base64
import json as _json
import logging
from backend.logging_broadcast import ExecutionIdFilter, LogBroadcastHandler

from backend.service_factory import get_service
from backend.routers import db_wf_router
from backend.routers_local import local_wf_router
from backend.routers_visual import visual_router
from backend.routers_logs import logs_router
from backend.routers_runs import runs_router
from backend.dependencies import validate_session_token, get_current_user, supabase
from backend.storage_state_api import router as storage_state_router, public_router as storage_state_public_router
from fastapi import APIRouter

# TODO: change the name to auth
# Create auth router
auth_router = APIRouter(prefix='/auth')

@auth_router.get("/validate", summary="Validate session token")
async def validate_session(session_token: str):
    """Validate a Supabase session token and return user information"""
    try:
        user_id = await validate_session_token(session_token)
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid or expired session token")
        
        return {
            "valid": True,
            "user_id": user_id,
            "message": "Session token is valid"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Session validation failed: {str(e)}")


# Set event loop policy for Windows
if sys.platform == 'win32':
	asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

app = FastAPI(title='Rebrowse Service')

# Redact long session_token values in access logs (keep logs concise yet visible)
class _RedactSessionTokenInAccessLog(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            # Uvicorn access logs usually pass args as a tuple:
            # (client_addr, method, path, http_version, status_code)
            args = record.args
            if isinstance(args, tuple) and len(args) >= 3:
                args_list = list(args)
                args_list[2] = self._redact_session_token(str(args_list[2]))
                record.args = tuple(args_list)
                return True
            # Some versions pass a dict with keys like 'request_line' or 'path'
            if isinstance(args, dict):
                if 'request_line' in args and isinstance(args['request_line'], str):
                    rl = args['request_line']
                    try:
                        method, rest = rl.split(' ', 1)
                        path, httpver = rest.rsplit(' ', 1)
                        path = self._redact_session_token(path)
                        args['request_line'] = f"{method} {path} {httpver}"
                    except Exception:
                        if 'path' in args:
                            args['path'] = self._redact_session_token(str(args['path']))
                elif 'path' in args:
                    args['path'] = self._redact_session_token(str(args['path']))
                record.args = args
                return True
            # Fallback: if structure is unexpected, don't break formatting
            return True
        except Exception:
            return True

    @staticmethod
    def _redact_session_token(message: str) -> str:
        try:
            import re
            # Collapse very long JWT-looking tokens while preserving start/end for identification
            pattern = r'(?P<prefix>session_token=)(?P<token>[A-Za-z0-9._-]+)(?=[^A-Za-z0-9._-]|$)'
            def _shorten(m: re.Match) -> str:
                token = m.group('token')
                if len(token) <= 20:
                    return m.group(0)
                # First 5 of token and last 10 of token, e.g., eyJhb...f7y41HheM6
                return f"{m.group('prefix')}{token[:5]}...{token[-10:]}"
            return re.sub(pattern, _shorten, message)
        except Exception:
            return message

logging.getLogger('uvicorn.access').addFilter(_RedactSessionTokenInAccessLog())

# ─── CORS ────────
origins = [
    "https://app.rebrowse.me",         # production UI
    "https://rebrowse.me",             # production UI (without www)
    "https://www.rebrowse.me",         # production UI (with www)
	"https://api.rebrowse.me", 
    "http://localhost:5173",           # local Vite dev
    "http://localhost:3000",           # React dev server
    "http://localhost:8080",           # Alternative dev server
    "http://127.0.0.1:5173",           # local Vite dev (127.0.0.1)
    "http://127.0.0.1:3000",           # React dev server (127.0.0.1)
    "http://127.0.0.1:8080",           # Alternative dev server (127.0.0.1)
    "chrome-extension://<EXT_ID>",     # Chrome extension
]

# More comprehensive regex patterns for various domains
origin_regex = r"https:\/\/.*\.(vercel\.app|netlify\.app|railway\.app|rebrowse\.me)"   # Various hosting platforms

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins + ([os.getenv('CORS_ALLOWED_EXTENSIONS')] if os.getenv('CORS_ALLOWED_EXTENSIONS') else []),
    allow_origin_regex=origin_regex,
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, PATCH, DELETE, PUT, OPTIONS)
    allow_headers=["*"],
    expose_headers=["*"],  # Expose all headers to frontend
)

# Add CORS debugging middleware
@app.middleware("http")
async def cors_debug_middleware(request: Request, call_next):
    """Debug CORS requests to help identify issues"""
    import logging
    logger = logging.getLogger(__name__)
    
    # Log CORS-related headers
    origin = request.headers.get("origin")
    if origin:
        logger.info(f"CORS request from origin: {origin}")
    
    response = await call_next(request)
    
    # Log CORS response headers
    cors_headers = {k: v for k, v in response.headers.items() if 'access-control' in k.lower()}
    if cors_headers:
        logger.info(f"CORS response headers: {cors_headers}")
    
    return response
#------------------------------------------------

"""Startup logging setup with diagnostics for handler/filter attachment.

We previously swallowed all exceptions here, which could hide issues in prod.
Now we log a warning with details and also log successful attachment state.
"""
try:
    import logging
    from logging.handlers import RotatingFileHandler
    startup_logger = logging.getLogger(__name__)
    log_dir = os.path.join('tmp', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    bu_log_path = os.path.join(log_dir, 'browser_use.log')
    handler = RotatingFileHandler(bu_log_path, maxBytes=5 * 1024 * 1024, backupCount=3)
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] [%(name)s] %(message)s')
    handler.setFormatter(formatter)
    handler.setLevel(logging.INFO)

    # Ensure ExecutionId is present on all records
    root_logger = logging.getLogger()
    # Avoid multiple identical filters on reloads
    added_filter = False
    if not any(isinstance(f, ExecutionIdFilter) for f in root_logger.filters):
        root_logger.addFilter(ExecutionIdFilter())
        added_filter = True

    # Structured broadcast handler for realtime streaming (attached to namespaces)
    broadcast_handler = LogBroadcastHandler(level=logging.INFO)

    attached = {}
    for name in ['browser_use', 'workflow_use']:
        ns_logger = logging.getLogger(name)
        ns_logger.setLevel(logging.INFO)
        # Avoid duplicate handlers if reloaded
        if not any(isinstance(h, RotatingFileHandler) and getattr(h, 'baseFilename', '') == handler.baseFilename for h in ns_logger.handlers):
            ns_logger.addHandler(handler)
        if not any(isinstance(h, LogBroadcastHandler) for h in ns_logger.handlers):
            ns_logger.addHandler(broadcast_handler)
        attached[name] = [type(h).__name__ for h in ns_logger.handlers]

    startup_logger.info(f"Log setup complete. ExecutionIdFilter added={added_filter}. Handlers per logger={attached}")
except Exception as _e:
    try:
        logging.getLogger(__name__).warning(f"Log setup failed: {type(_e).__name__}: {_e}")
    except Exception:
        pass

# CORS preflight handler
@app.options("/{full_path:path}")
async def cors_preflight(full_path: str):
    """Handle CORS preflight requests for all endpoints"""
    return {}

# CORS test endpoint
@app.get("/cors-test")
async def cors_test():
    """Test endpoint to verify CORS is working"""
    return {
        "message": "CORS is working!",
        "timestamp": "2024-01-01T00:00:00Z",
        "status": "success"
    }

# Health check endpoint for Railway
@app.get("/health")
async def health_check():
	"""Health check endpoint for Railway deployment monitoring."""
	try:
		# Basic health checks (without requiring service initialization)
		health_status = {
			"status": "healthy",
			"service": "rebrowse-backend",
			"browser_available": True,  # Browser instances are created dynamically
		}
		
		# Try to get service instance (may fail if Supabase not configured)
		try:
			svc = get_service()
			health_status["llm_available"] = svc.llm_instance is not None
			health_status["tmp_dir_exists"] = svc.tmp_dir.exists()
			health_status["supabase_connected"] = True
		except Exception as e:
			health_status["supabase_connected"] = False
			health_status["supabase_error"] = str(e)
			health_status["llm_available"] = False
			health_status["tmp_dir_exists"] = False
		
		# Check if we can create a simple file (filesystem test)
		if health_status.get("supabase_connected", False):
			test_file = svc.tmp_dir / "health_check.txt"
			try:
				test_file.write_text("health_check")
				test_file.unlink()  # Clean up
				health_status["filesystem_writable"] = True
			except Exception:
				health_status["filesystem_writable"] = False
		else:
			health_status["filesystem_writable"] = False
		
		# Check Playwright browser availability (production critical)
		playwright_chromium_path = "/root/.cache/ms-playwright/chromium-1169/chrome-linux/chrome"
		health_status["playwright_chromium_available"] = os.path.exists(playwright_chromium_path)
		
		# Cookies summary (visibility)
		cookies_enabled = os.getenv('FEATURE_USE_COOKIES', 'true').lower() == 'true'
		cookies_kid = os.getenv('COOKIE_KID', 'n/a')
		cookies_ttl = os.getenv('COOKIE_VERIFY_TTL_HOURS', '24')
		cors_ext = os.getenv('CORS_ALLOWED_EXTENSIONS', 'n/a')
		health_status["cookies"] = {
			"enabled": cookies_enabled,
			"kid": cookies_kid,
			"ttl_hours": cookies_ttl,
			"allowlist": cors_ext,
		}

		# Check if we're in production and warn if Playwright browser is missing
		is_production = os.getenv('RAILWAY_ENVIRONMENT') is not None
		if is_production and not health_status["playwright_chromium_available"]:
			health_status["status"] = "degraded"
			health_status["warning"] = "Playwright Chromium not found - workflow execution may fail"
		
		return health_status
		
	except Exception as e:
		raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

@app.get("/test-browser")
async def test_browser():
	"""Test browser functionality for Railway deployment."""
	import os
	import shutil
	from browser_use.browser.browser import Browser, BrowserProfile
	
	try:
		# Environment info
		env_info = {
			"environment": "production" if os.getenv('RAILWAY_ENVIRONMENT') else "development",
			"display": os.getenv('DISPLAY', 'not set'),
			"railway_env": os.getenv('RAILWAY_ENVIRONMENT', 'not set'),
		}
		
		# Check Playwright browser installation
		playwright_info = {}
		playwright_chromium_path = "/root/.cache/ms-playwright/chromium-1169/chrome-linux/chrome"
		playwright_info["chromium_path"] = playwright_chromium_path
		playwright_info["chromium_exists"] = os.path.exists(playwright_chromium_path)
		
		# List Playwright directory contents
		playwright_dir = "/root/.cache/ms-playwright"
		if os.path.exists(playwright_dir):
			try:
				playwright_info["directory_contents"] = os.listdir(playwright_dir)
			except Exception as e:
				playwright_info["directory_error"] = str(e)
		else:
			playwright_info["directory_exists"] = False
		
		# Check for system Chromium (fallback)
		chromium_paths = [
			'/usr/bin/chromium-browser',
			'/usr/bin/chromium',
			'/usr/bin/google-chrome',
			'/usr/bin/google-chrome-stable',
		]
		
		system_chromium_info = {}
		for path in chromium_paths:
			exists = os.path.exists(path) if path else False
			executable = shutil.which(path) if path else None
			system_chromium_info[path] = {
				"exists": exists,
				"executable": executable is not None,
				"path": executable
			}
		
		# Try to create and test browser using the same logic as WorkflowService
		browser_test = {"status": "unknown", "error": None}
		
		try:
			# Use the same browser creation logic as WorkflowService
			is_production = os.getenv('RAILWAY_ENVIRONMENT') is not None
			
			if is_production:
				# Production configuration - let Playwright handle the executable
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
				test_browser = Browser(browser_profile=profile)
			else:
				# Development configuration
				test_browser = Browser()
			
			# Try to start browser
			await test_browser.start()
			
			# Try to navigate to a simple page
			page = await test_browser.get_current_page()
			await page.goto("data:text/html,<html><body><h1>Browser Test Success</h1></body></html>")
			
			# Get page title
			title = await page.title()
			
			# Close browser
			await test_browser.close()
			
			browser_test = {
				"status": "success",
				"page_title": title,
				"message": "Browser test completed successfully",
				"configuration": "production" if is_production else "development"
			}
			
		except Exception as e:
			browser_test = {
				"status": "failed",
				"error": str(e),
				"message": "Browser test failed - check Playwright installation"
			}
		
		return {
			"environment": env_info,
			"playwright_browser": playwright_info,
			"system_chromium": system_chromium_info,
			"browser_test": browser_test,
			"timestamp": os.popen('date').read().strip()
		}
		
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Browser test failed: {str(e)}")

# Include routers
app.include_router(auth_router)
app.include_router(local_wf_router)
app.include_router(db_wf_router)
app.include_router(visual_router)
app.include_router(logs_router)
app.include_router(runs_router)
app.include_router(storage_state_router)
app.include_router(storage_state_public_router)

# Optional standalone runner
if __name__ == '__main__':
	uvicorn.run('api:app', host='127.0.0.1', port=8000, log_level='info')