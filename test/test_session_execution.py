#!/usr/bin/env python3
"""
Test script for session-based workflow execution
"""
import asyncio
import json
import requests
import sys
from pathlib import Path

# Add the project root to Python path for robust imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.dependencies import validate_session_token

# Test session token (replace with a valid one)
TEST_SESSION_TOKEN = "eyJhbGciOiJIUzI1NiIsImtpZCI6IjJmOGZjNzJmLWY4YzQtNGY4Zi1hNzE4LTJkNzE4ZjE4ZjE4ZiIsInR5cCI6IkpXVCJ9.eyJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzM3NzU5NzE5LCJpYXQiOjE3Mzc3NTYxMTksImlzcyI6Imh0dHBzOi8vdGVzdC5zdXBhYmFzZS5jbyIsInN1YiI6ImI5M2Q4Y2EzLTVhMWMtNDZkMy05NTcxLTM2YWQ0NGQwOWQ2ZCIsImVtYWlsIjoibm9yaWthLmtpemF3YUBnbWFpbC5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsIjoibm9yaWthLmtpemF3YUBnbWFpbC5jb20iLCJlbWFpbF92ZXJpZmllZCI6ZmFsc2UsInBob25lX3ZlcmlmaWVkIjpmYWxzZSwic3ViIjoiYjkzZDhjYTMtNWExYy00NmQzLTk1NzEtMzZhZDQ0ZDA5ZDZkIn0sInJvbGUiOiJhdXRoZW50aWNhdGVkIiwiYWFsIjoiYWFsMSIsImFtciI6W3sibWV0aG9kIjoicGFzc3dvcmQiLCJ0aW1lc3RhbXAiOjE3Mzc3NTYxMTl9XSwic2Vzc2lvbl9pZCI6IjY5YzY5YzY5LTY5YzYtNDZjNi05YzY5LTY5YzY5YzY5YzY5YyIsImlzX2Fub255bW91cyI6ZmFsc2V9.invalid_signature_for_testing"

TEST_WORKFLOW_ID = "1b472361-29be-452c-b948-11d937097b29"
BASE_URL = "http://127.0.0.1:8000"

async def test_session_validation():
    """Test session token validation"""
    print("Testing session token validation...")
    try:
        user_id = await validate_session_token(TEST_SESSION_TOKEN)
        print(f"✅ Session token valid for user: {user_id}")
        return user_id
    except Exception as e:
        print(f"❌ Session token validation failed: {e}")
        return None

def test_health_check():
    """Test health check endpoint"""
    print("Testing health check...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            health_data = response.json()
            print(f"✅ Health check passed: {health_data}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_workflow_execution():
    """Test workflow execution endpoint"""
    print("Testing workflow execution...")
    try:
        payload = {
            "session_token": TEST_SESSION_TOKEN,
            "inputs": {
                "test_input": "Hello World"
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/workflows/{TEST_WORKFLOW_ID}/execute/session",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Workflow execution started: {result}")
            return result.get("task_id")
        else:
            print(f"❌ Workflow execution failed: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Workflow execution error: {e}")
        return None

async def main():
    """Run all tests"""
    print("🚀 Starting session-based workflow execution tests...\n")
    
    # Test 1: Health check
    health_ok = test_health_check()
    print()
    
    # Test 2: Session validation
    user_id = await test_session_validation()
    print()
    
    # Test 3: Workflow execution (will fail with invalid token, but tests the endpoint)
    task_id = test_workflow_execution()
    print()
    
    print("📋 Test Summary:")
    print(f"  Health Check: {'✅ PASS' if health_ok else '❌ FAIL'}")
    print(f"  Session Validation: {'✅ PASS' if user_id else '❌ FAIL'}")
    print(f"  Workflow Execution: {'✅ PASS' if task_id else '❌ FAIL (expected with invalid token)'}")

if __name__ == "__main__":
    asyncio.run(main()) 