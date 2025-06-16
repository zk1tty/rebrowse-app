#!/usr/bin/env python3
"""
Test JWT token validation locally
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

# Test JWT token (replace with your actual token)
TEST_TOKEN = "eyJhbGciOiJIUzI1NiIsImtpZCI6IjJmOGZjNzJmLWY4YzQtNGY4Zi1hNzE4LTJkNzE4ZjE4ZjE4ZiIsInR5cCI6IkpXVCJ9.eyJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzM3NzU5NzE5LCJpYXQiOjE3Mzc3NTYxMTksImlzcyI6Imh0dHBzOi8vdGVzdC5zdXBhYmFzZS5jbyIsInN1YiI6ImI5M2Q4Y2EzLTVhMWMtNDZkMy05NTcxLTM2YWQ0NGQwOWQ2ZCIsImVtYWlsIjoibm9yaWthLmtpemF3YUBnbWFpbC5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsIjoibm9yaWthLmtpemF3YUBnbWFpbC5jb20iLCJlbWFpbF92ZXJpZmllZCI6ZmFsc2UsInBob25lX3ZlcmlmaWVkIjpmYWxzZSwic3ViIjoiYjkzZDhjYTMtNWExYy00NmQzLTk1NzEtMzZhZDQ0ZDA5ZDZkIn0sInJvbGUiOiJhdXRoZW50aWNhdGVkIiwiYWFsIjoiYWFsMSIsImFtciI6W3sibWV0aG9kIjoicGFzc3dvcmQiLCJ0aW1lc3RhbXAiOjE3Mzc3NTYxMTl9XSwic2Vzc2lvbl9pZCI6IjY5YzY5YzY5LTY5YzYtNDZjNi05YzY5LTY5YzY5YzY5YzY5YyIsImlzX2Fub255bW91cyI6ZmFsc2V9.invalid_signature_for_testing"

def test_jwt_decode():
    """Test JWT token decoding"""
    print("🔍 Testing JWT token decoding...")
    
    try:
        # Decode without verification first
        unverified = jwt.decode(TEST_TOKEN, options={"verify_signature": False})
        print("✅ JWT token decoded successfully (unverified)")
        print(f"📧 Email: {unverified.get('email')}")
        print(f"👤 Subject: {unverified.get('sub')}")
        print(f"⏰ Expires: {time.ctime(unverified.get('exp', 0))}")
        
        # Check if expired
        now = int(time.time())
        exp = unverified.get('exp', 0)
        if exp < now:
            print(f"⚠️  Token expired {(now - exp) // 60} minutes ago")
        else:
            print(f"✅ Token valid for {(exp - now) // 60} more minutes")
        
        return True
        
    except Exception as e:
        print(f"❌ JWT decode failed: {e}")
        return False

def test_jwt_verify():
    """Test JWT token verification with secret"""
    print("🔐 Testing JWT token verification...")
    
    if not JWT_SECRET:
        print("⚠️  JWT_SECRET not found in environment")
        return False
    
    try:
        payload = jwt.decode(TEST_TOKEN, JWT_SECRET, algorithms=["HS256"], options={"verify_aud": False})
        print("✅ JWT signature verified successfully")
        return True
        
    except jwt.InvalidSignatureError:
        print("❌ Invalid JWT signature")
        return False
    except jwt.ExpiredSignatureError:
        print("❌ JWT token expired")
        return False
    except Exception as e:
        print(f"❌ JWT verification failed: {e}")
        return False

def test_api_call():
    """Test API call with JWT token"""
    print("🌐 Testing API call with JWT token...")
    
    try:
        response = requests.post(
            "http://localhost:8000/workflows/",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {TEST_TOKEN}"
            },
            json={"title": "Test Workflow", "json": {"test": "data"}},
            timeout=10
        )
        
        print(f"📡 Response status: {response.status_code}")
        print(f"📄 Response: {response.text[:200]}...")
        
        if response.status_code == 201:
            print("✅ API call successful")
            return True
        elif response.status_code == 401:
            print("❌ Unauthorized - JWT token invalid")
            return False
        else:
            print(f"⚠️  Unexpected status: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to backend - make sure it's running")
        return False
    except Exception as e:
        print(f"❌ API call failed: {e}")
        return False

def main():
    """Run all JWT tests"""
    print("🚀 Starting JWT token tests...\n")
    
    # Test 1: Decode
    decode_ok = test_jwt_decode()
    print()
    
    # Test 2: Verify
    verify_ok = test_jwt_verify()
    print()
    
    # Test 3: API call
    api_ok = test_api_call()
    print()
    
    print("📋 Test Summary:")
    print(f"  JWT Decode: {'✅ PASS' if decode_ok else '❌ FAIL'}")
    print(f"  JWT Verify: {'✅ PASS' if verify_ok else '❌ FAIL'}")
    print(f"  API Call: {'✅ PASS' if api_ok else '❌ FAIL'}")
    
    if all([decode_ok, verify_ok, api_ok]):
        print("\n🎉 All JWT tests passed!")
    else:
        print("\n⚠️  Some tests failed - check configuration")

if __name__ == "__main__":
    main() 