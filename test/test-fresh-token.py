#!/usr/bin/env python3
"""
Test a fresh JWT token from Chrome extension
"""
import os
import jwt
import requests
import time
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add the project root to Python path for robust imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load .env file from project root
env_path = project_root / '.env'
load_dotenv(dotenv_path=env_path)

JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

print("🚀 Fresh Token Tester")
print("=" * 50)
print("📋 Instructions:")
print("1. Open Chrome extension and sign in if needed")
print("2. Open Chrome DevTools on extension (F12 or right-click -> Inspect)")
print("3. Run the get-fresh-token.js script in Console")
print("4. Copy the JWT token from the output")
print("5. Paste it below when prompted")
print("=" * 50)

# Get token from user with better handling
print("\n🎯 Paste your fresh JWT token here:")
print("   (Press Enter after pasting, then type 'done' and press Enter again)")
print("   Token: ", end="", flush=True)

# Handle potentially very long tokens
token_parts = []
while True:
    try:
        line = input().strip()
        if line.lower() == 'done':
            break
        if line:
            token_parts.append(line)
    except KeyboardInterrupt:
        print("\n❌ Cancelled by user")
        exit(1)
    except Exception as e:
        print(f"\n❌ Input error: {e}")
        exit(1)

token = ''.join(token_parts)

if not token:
    print("❌ No token provided")
    exit(1)

print(f"\n📏 Token length: {len(token)} characters")
print(f"🔍 Token preview: {token[:50]}...{token[-20:] if len(token) > 70 else ''}")

# Basic format check
if not token.count('.') == 2:
    print("❌ Invalid JWT format - should have exactly 2 dots (.)")
    exit(1)

try:
    print("\n🔍 Decoding token (without verification)...")
    # Decode and check expiration
    unverified = jwt.decode(token, options={"verify_signature": False})
    now = int(time.time())
    exp = unverified.get('exp', 0)
    is_expired = exp < now
    
    print(f"📧 User: {unverified.get('email', 'N/A')}")
    print(f"👤 Subject: {unverified.get('sub', 'N/A')}")
    print(f"⏰ Issued at: {time.ctime(unverified.get('iat', 0))}")
    print(f"⏰ Expires at: {time.ctime(exp)}")
    print(f"🚨 Expired: {'❌ YES' if is_expired else '✅ NO'}")
    
    if is_expired:
        print(f"💀 Token expired {(now - exp) // 60} minutes ago")
        print("❌ Please get a fresh token from the extension")
        exit(1)
    else:
        print(f"⏳ Expires in {(exp - now) // 60} minutes")
    
    # Test JWT verification
    print("\n🔐 Testing JWT signature verification...")
    if JWT_SECRET:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"], options={"verify_aud": False})
            print("✅ JWT signature verified successfully")
        except jwt.InvalidSignatureError:
            print("❌ Invalid JWT signature - check JWT_SECRET configuration")
            exit(1)
    else:
        print("⚠️  JWT_SECRET not available, skipping signature verification")
    
    # Test API call
    print("\n🌐 Testing API call to backend...")
    print("📡 Making POST request to /workflows/...")
    
    try:
        response = requests.post(
            "http://localhost:8000/workflows/",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}"
            },
            json={"title": "Test Workflow", "json": {"test": "data"}},
            timeout=10
        )
        
        print(f"📡 Response status: {response.status_code}")
        print(f"📄 Response headers: {dict(response.headers)}")
        print(f"📄 Response body: {response.text[:500]}{'...' if len(response.text) > 500 else ''}")
        
        if response.status_code == 201:
            print("🎉 SUCCESS! Authentication working!")
        elif response.status_code == 401:
            print("❌ Still getting 401 - check backend JWT configuration")
        elif response.status_code == 422:
            print("⚠️  Validation error - check request format")
        else:
            print(f"⚠️  Unexpected status code: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to backend - make sure it's running on localhost:8000")
    except requests.exceptions.Timeout:
        print("❌ Request timed out - backend might be slow or unresponsive")
    except Exception as e:
        print(f"❌ Request error: {e}")
        
except jwt.DecodeError as e:
    print(f"❌ Cannot decode JWT token: {e}")
    print("💡 Make sure you copied the complete token")
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    import traceback
    print("🔍 Full traceback:")
    traceback.print_exc()

print("\n" + "=" * 50) 