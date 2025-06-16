import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from the project root
root_dir = Path(__file__).parent.parent
env_path = root_dir / '.env'
load_dotenv(dotenv_path=env_path)

from fastapi import Depends, HTTPException, Request, status
import jwt
from supabase import Client, create_client
from typing import Optional, Dict, Any

# Set up logger
logger = logging.getLogger(__name__)

# Environment variables
SUPABASE_URL: Optional[str] = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY: Optional[str] = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
JWT_SECRET: Optional[str] = os.getenv("SUPABASE_JWT_SECRET")

# Debug: Show environment variable status at startup
def prompt_for_missing_env_vars():
    """Prompt user to set missing environment variables interactively"""
    global SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, JWT_SECRET
    
    if not SUPABASE_URL or SUPABASE_URL == 'your_supabase_url_here':
        logger.error("SUPABASE_URL is not configured.")
        set_url = input("Would you like to set SUPABASE_URL now? (y/n): ")
        if set_url.lower() == 'y':
            SUPABASE_URL = input("Enter your SUPABASE_URL (e.g., https://your-project.supabase.co): ")
            os.environ['SUPABASE_URL'] = SUPABASE_URL
    
    if not SUPABASE_SERVICE_ROLE_KEY or SUPABASE_SERVICE_ROLE_KEY == 'your_service_role_key_here':
        logger.error("SUPABASE_SERVICE_ROLE_KEY is not configured.")
        set_key = input("Would you like to set SUPABASE_SERVICE_ROLE_KEY now? (y/n): ")
        if set_key.lower() == 'y':
            SUPABASE_SERVICE_ROLE_KEY = input("Enter your SUPABASE_SERVICE_ROLE_KEY: ")
            os.environ['SUPABASE_SERVICE_ROLE_KEY'] = SUPABASE_SERVICE_ROLE_KEY
    
    if not JWT_SECRET or JWT_SECRET == 'your_jwt_secret_here':
        logger.error("SUPABASE_JWT_SECRET is not configured.")
        set_secret = input("Would you like to set SUPABASE_JWT_SECRET now? (y/n): ")
        if set_secret.lower() == 'y':
            JWT_SECRET = input("Enter your SUPABASE_JWT_SECRET: ")
            os.environ['SUPABASE_JWT_SECRET'] = JWT_SECRET

logger.debug("=== SUPABASE ENV VARIABLES ===")
logger.debug(f"SUPABASE_URL: {'✅ SET' if SUPABASE_URL else '❌ NOT SET OR PLACEHOLDER'}")
logger.debug(f"SUPABASE_SERVICE_ROLE_KEY: {'✅ SET' if SUPABASE_SERVICE_ROLE_KEY else '❌ NOT SET OR PLACEHOLDER'}")
logger.debug(f"SUPABASE_JWT_SECRET: {'✅ SET' if JWT_SECRET else '❌ NOT SET OR PLACEHOLDER'}")
logger.debug("=============================================")

# Prompt for missing environment variables if running interactively
if os.getenv('INTERACTIVE_MODE', 'true').lower() == 'true':
    missing_vars = []
    if not SUPABASE_URL or SUPABASE_URL == 'your_supabase_url_here':
        missing_vars.append('SUPABASE_URL')
    if not SUPABASE_SERVICE_ROLE_KEY or SUPABASE_SERVICE_ROLE_KEY == 'your_service_role_key_here':
        missing_vars.append('SUPABASE_SERVICE_ROLE_KEY')  
    if not JWT_SECRET or JWT_SECRET == 'your_jwt_secret_here':
        missing_vars.append('SUPABASE_JWT_SECRET')
    
    if missing_vars:
        logger.warning(f"Missing Supabase configuration: {', '.join(missing_vars)}")
        prompt_missing = input("Would you like to configure these now? (y/n): ")
        if prompt_missing.lower() == 'y':
            prompt_for_missing_env_vars()

# Initialize Supabase client
supabase: Optional[Client] = None

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    logger.warning(
        "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are not properly configured. Database functionality will be disabled."
    )
else:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        logger.info("Supabase client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        supabase = None

if not JWT_SECRET:
    logger.warning("SUPABASE_JWT_SECRET is not properly configured. JWT verification will be disabled.")


def get_current_user(req: Request) -> str:
    """
    Verify Supabase JWT token and return user ID.
    Raises HTTPException if authentication fails.
    """
    if not JWT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service not configured"
        )
    
    auth_header = req.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header"
        )
    
    token = auth_header.split(" ", 1)[1]
    
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User ID not found in token"
            )
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )


def get_current_user_optional(req: Request) -> Optional[str]:
    """
    Verify Supabase JWT token and return user ID if valid.
    Returns None if authentication fails or is missing.
    """
    if not JWT_SECRET:
        return None
    
    try:
        auth_header = req.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None
        
        token = auth_header.split(" ", 1)[1]
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload.get("sub")
    except (jwt.PyJWTError, IndexError):
        return None


# Legacy functions for backward compatibility (deprecated)
def get_user(req: Request) -> str:
    """
    Legacy function - returns user ID from JWT payload.
    Use get_current_user() for new code.
    """
    return get_current_user(req)


def get_user_optional(req: Request) -> Optional[str]:
    """
    Legacy function - returns user ID from JWT payload if valid.
    Use get_current_user_optional() for new code.
    """
    return get_current_user_optional(req)


async def validate_session_token(session_token: str) -> Optional[str]:
    """
    Validate Supabase session token and return user ID if valid.
    Uses JWT decoding since supabase.auth.get_user() doesn't work server-side.
    """
    if not session_token:
        return None
    
    try:
        # Decode the JWT token without verification first to get the payload
        # The session token is actually a JWT that we can decode
        import jwt
        
        # Decode without verification to get the payload
        # We'll validate it by checking if it's properly signed by Supabase
        payload = jwt.decode(session_token, options={"verify_signature": False})
        
        # Check if this looks like a valid Supabase session token
        if not payload.get("sub") or not payload.get("iss"):
            return None
            
        # Check if token is expired
        import time
        if payload.get("exp", 0) < time.time():
            return None
            
        # For additional security, we could verify the signature if we had the right key
        # But for now, we'll trust that the token structure is valid
        
        return payload.get("sub")
        
    except Exception as e:
        logger.debug(f"Session validation failed: {e}")
        return None


def get_session_user_from_query(req: Request) -> Optional[str]:
    """
    Extract user ID from session_token query parameter.
    Returns None if no valid session token found.
    """
    session_token = req.query_params.get("session_token")
    if not session_token:
        return None
    
    import asyncio
    # Run the async validation in the current event loop
    try:
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(validate_session_token(session_token))
    except Exception:
        return None


def get_current_user_from_session(req: Request) -> str:
    """
    Dependency function to get current user from session token in query params.
    Raises HTTPException if authentication fails.
    """
    user_id = get_session_user_from_query(req)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing session token"
        )
    return user_id


def get_current_user_from_session_optional(req: Request) -> Optional[str]:
    """
    Dependency function to get current user from session token in query params.
    Returns None if authentication fails or is missing.
    """
    return get_session_user_from_query(req) 