#!/usr/bin/env python3
"""
End-to-End Test: Manual Workflow Execution with Visual Streaming

This test verifies:
1. Session creation during manual workflow execution
2. rrweb event transmission and recording
3. Visual streaming status and readiness
4. Complete workflow lifecycle
"""

import asyncio
import aiohttp
import json
import time
import websockets
from pathlib import Path

# Configuration
BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"
SESSION_TOKEN = "eyJhbGciOiJIUzI1NiIsImtpZCI6IklKclRKS29xc0Z6ZmxUVWMiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJodHRwczovL2RtZ3Rzc2VxcXNpeXV1emhkeG5uLnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiJiOTNkOGNhMy01YTFjLTQ2ZDMtOTU3MS0zNmFkNDRkMDlkNmQiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzUwODE3Nzk3LCJpYXQiOjE3NTA3ODE3OTcsImVtYWlsIjoibm9yaWthQDB4Y2VyYmVydXMuaW8iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6Imdvb2dsZSIsInByb3ZpZGVycyI6WyJnb29nbGUiXX0sInVzZXJfbWV0YWRhdGEiOnsiYXZhdGFyX3VybCI6Imh0dHBzOi8vbGgzLmdvb2dsZXVzZXJjb250ZW50LmNvbS9hL0FDZzhvY0xpOXlmMTRLSVBTUXl0RWV1eXhTdWZadTN5TEtXS3FjS3JGT0FoNm5aNVZCdzB5alk9czk2LWMiLCJjdXN0b21fY2xhaW1zIjp7ImhkIjoiMHhjZXJiZXJ1cy5pbyJ9LCJlbWFpbCI6Im5vcmlrYUAweGNlcmJlcnVzLmlvIiwiZW1haWxfdmVyaWZpZWQiOnRydWUsImZ1bGxfbmFtZSI6Ik5vcmlrYSBLaXphd2EiLCJpc3MiOiJodHRwczovL2FjY291bnRzLmdvb2dsZS5jb20iLCJuYW1lIjoiTm9yaWthIEtpemF3YSIsInBob25lX3ZlcmlmaWVkIjpmYWxzZSwicGljdHVyZSI6Imh0dHBzOi8vbGgzLmdvb2dsZXVzZXJjb250ZW50LmNvbS9hL0FDZzhvY0xpOXlmMTRLSVBTUXl0RWV1eXhTdWZadTN5TEtXS3FjS3JGT0FoNm5aNVZCdzB5alk9czk2LWMiLCJwcm92aWRlcl9pZCI6IjExMTQwNDkzNjAzNzQ3MDU4MjQ2MSIsInN1YiI6IjExMTQwNDkzNjAzNzQ3MDU4MjQ2MSJ9LCJyb2xlIjoiYXV0aGVudGljYXRlZCIsImFhbCI6ImFhbDEiLCJhbXIiOlt7Im1ldGhvZCI6Im9hdXRoIiwidGltZXN0YW1wIjoxNzUwMTI0NTM2fV0sInNlc3Npb25faWQiOiJjNjgzZjY3YS0wODllLTQ0MDUtOWE3OC0xODQxOGIyNTA2NzMiLCJpc19hbm9ueW1vdXMiOmZhbHNlfQ.59oZ6VwjCtKgUw0qO6wVjOjud--Jc1-1G16SahIFL0k"

# Test workflow with more interactive steps
TEST_WORKFLOW = {
    "name": "E2E Visual Streaming Test",
    "version": "1.0",
    "description": "End-to-end test workflow for visual streaming with rrweb events",
    "workflow_analysis": "This workflow tests visual streaming by navigating to a page and performing interactions.",
    "steps": [
        {
            "type": "navigation",
            "url": "https://example.com",
            "description": "Navigate to example.com to generate rrweb events",
            "timestamp": None,
            "tabId": None,
            "output": None
        }
    ],
    "input_schema": []
}

class RRWebEventMonitor:
    """Monitor and collect rrweb events from WebSocket connection"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.events = []
        self.connected = False
        self.ws = None
    
    async def connect_and_monitor(self, duration: int = 30):
        """Connect to WebSocket and monitor rrweb events"""
        stream_url = f"{WS_URL}/workflows/visual/{self.session_id}/stream"
        
        try:
            print(f"🔌 Connecting to WebSocket: {stream_url}")
            async with websockets.connect(stream_url) as websocket:
                self.ws = websocket
                self.connected = True
                print(f"✅ Connected to rrweb stream for session: {self.session_id}")
                
                # Monitor events for specified duration
                start_time = time.time()
                while time.time() - start_time < duration:
                    try:
                        # Wait for message with timeout
                        message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        event_data = json.loads(message)
                        self.events.append({
                            'timestamp': time.time(),
                            'data': event_data
                        })
                        print(f"📡 Received rrweb event: {event_data.get('event', {}).get('type', 'unknown')} at {time.time()}")
                        
                    except asyncio.TimeoutError:
                        # No message received, continue monitoring
                        continue
                    except websockets.exceptions.ConnectionClosed:
                        print("🔌 WebSocket connection closed")
                        break
                    except Exception as e:
                        print(f"❌ Error receiving message: {e}")
                        break
                        
        except Exception as e:
            print(f"❌ Failed to connect to WebSocket: {e}")
            self.connected = False
    
    def get_event_summary(self):
        """Get summary of collected events"""
        if not self.events:
            return {"total_events": 0, "event_types": [], "duration": 0}
        
        event_types = {}
        for event in self.events:
            event_type = event['data'].get('event', {}).get('type', 'unknown')
            event_types[event_type] = event_types.get(event_type, 0) + 1
        
        duration = self.events[-1]['timestamp'] - self.events[0]['timestamp'] if len(self.events) > 1 else 0
        
        return {
            "total_events": len(self.events),
            "event_types": event_types,
            "duration": duration,
            "first_event": self.events[0]['timestamp'] if self.events else None,
            "last_event": self.events[-1]['timestamp'] if self.events else None
        }

async def get_existing_workflow(session):
    """Get an existing workflow for E2E testing"""
    headers = {"Authorization": f"Bearer {SESSION_TOKEN}"}
    
    async with session.get(f"{BASE_URL}/workflows", headers=headers) as resp:
        if resp.status == 200:
            workflows = await resp.json()
            if workflows:
                # Use the first available workflow
                workflow = workflows[0]
                workflow_id = workflow.get('id')
                workflow_name = workflow.get('name')
                print(f"✅ Using existing workflow: {workflow_name} ({workflow_id})")
                return workflow_id
            else:
                raise Exception("No workflows available")
        else:
            error_text = await resp.text()
            raise Exception(f"Failed to get workflows: {resp.status} - {error_text}")

async def create_test_workflow(session):
    """Create a test workflow for E2E testing"""
    # First try to use an existing workflow
    try:
        return await get_existing_workflow(session)
    except Exception as e:
        print(f"⚠️ Could not use existing workflow ({e}), trying to create new one...")
    
    # If no existing workflow, try to create one
    headers = {"Authorization": f"Bearer {SESSION_TOKEN}"}
    params = {"session_token": SESSION_TOKEN}
    
    async with session.post(f"{BASE_URL}/workflows", headers=headers, params=params, json=TEST_WORKFLOW) as resp:
        if resp.status == 201:
            workflow_data = await resp.json()
            workflow_id = workflow_data.get('id')
            print(f"✅ Created test workflow: {workflow_id}")
            return workflow_id
        else:
            error_text = await resp.text()
            raise Exception(f"Failed to create workflow: {resp.status} - {error_text}")

async def start_manual_execution(session, workflow_id):
    """Start manual workflow execution with visual streaming"""
    headers = {"Authorization": f"Bearer {SESSION_TOKEN}"}
    
    execution_payload = {
        "session_token": SESSION_TOKEN,
        "visual_streaming": True,
        "visual_quality": "standard",
        "visual_events_buffer": 1000,
        "inputs": {}
    }
    
    print(f"🚀 Starting manual execution for workflow: {workflow_id}")
    async with session.post(
        f"{BASE_URL}/workflows/{workflow_id}/execute/session", 
        headers=headers, 
        json=execution_payload
    ) as resp:
        if resp.status == 200:
            response_data = await resp.json()
            print(f"✅ Manual execution started successfully!")
            print(f"   📊 Response: {json.dumps(response_data, indent=2)}")
            return response_data
        else:
            error_text = await resp.text()
            raise Exception(f"Failed to start execution: {resp.status} - {error_text}")

async def monitor_session_status(session, session_id, max_attempts=20):
    """Monitor session status and streaming readiness"""
    headers = {"Authorization": f"Bearer {SESSION_TOKEN}"}
    
    for attempt in range(1, max_attempts + 1):
        print(f"🔍 Attempt {attempt}/{max_attempts} - Checking session status...")
        
        # Check visual streaming status
        async with session.get(f"{BASE_URL}/workflows/visual/{session_id}/status", headers=headers) as resp:
            if resp.status == 200:
                status_data = await resp.json()
                print(f"   📊 Visual Status: {json.dumps(status_data, indent=2)}")
                
                streaming_ready = status_data.get('streaming_ready', False)
                streaming_active = status_data.get('streaming_active', False)
                browser_ready = status_data.get('browser_ready', False)
                events_processed = status_data.get('events_processed', 0)
                
                print(f"   🔧 Streaming Ready: {streaming_ready}")
                print(f"   🔧 Streaming Active: {streaming_active}")
                print(f"   🔧 Browser Ready: {browser_ready}")
                print(f"   🔧 Events Processed: {events_processed}")
                
                if streaming_ready and browser_ready:
                    print(f"   ✅ Session is ready for streaming!")
                    return True
                    
            else:
                print(f"   ❌ Failed to get visual status: {resp.status}")
        
        await asyncio.sleep(2)
    
    print(f"   ❌ Session did not become ready within {max_attempts} attempts")
    return False

async def test_end_to_end_manual_execution():
    """Run comprehensive end-to-end test"""
    print("🧪 Starting End-to-End Manual Workflow Execution Test")
    print("=" * 70)
    
    async with aiohttp.ClientSession() as session:
        try:
            # Step 1: Create test workflow
            print("\n📝 Step 1: Creating test workflow...")
            workflow_id = await create_test_workflow(session)
            
            # Step 2: Start manual execution with visual streaming
            print("\n🚀 Step 2: Starting manual execution with visual streaming...")
            execution_response = await start_manual_execution(session, workflow_id)
            
            session_id = execution_response.get('session_id')
            task_id = execution_response.get('task_id')
            
            if not session_id:
                raise Exception("No session_id returned from execution")
            
            print(f"   🔗 Session ID: {session_id}")
            print(f"   🔗 Task ID: {task_id}")
            
            # Step 3: Start rrweb event monitoring in background
            print(f"\n📡 Step 3: Starting rrweb event monitoring...")
            event_monitor = RRWebEventMonitor(session_id)
            
            # Start monitoring in background
            monitor_task = asyncio.create_task(event_monitor.connect_and_monitor(duration=15))
            
            # Give WebSocket a moment to connect
            await asyncio.sleep(2)
            
            # Step 4: Monitor session status
            print(f"\n👀 Step 4: Monitoring session status...")
            session_ready = await monitor_session_status(session, session_id, max_attempts=10)
            
            # Step 5: Wait for workflow completion and event collection
            print(f"\n⏳ Step 5: Waiting for workflow completion and event collection...")
            await asyncio.sleep(10)  # Give workflow time to complete
            
            # Step 6: Stop monitoring and collect results
            print(f"\n📊 Step 6: Collecting results...")
            if not monitor_task.done():
                monitor_task.cancel()
                try:
                    await monitor_task
                except asyncio.CancelledError:
                    pass
            
            # Get event summary
            event_summary = event_monitor.get_event_summary()
            print(f"   📈 Event Summary: {json.dumps(event_summary, indent=2)}")
            
            # Step 7: Final status check
            print(f"\n🏁 Step 7: Final status check...")
            await monitor_session_status(session, session_id, max_attempts=1)
            
            # Step 8: Results analysis
            print(f"\n📋 Step 8: Results Analysis")
            print("=" * 50)
            
            success_criteria = {
                "session_created": session_id is not None,
                "execution_started": execution_response.get('success', False),
                "visual_streaming_enabled": execution_response.get('visual_streaming_enabled', False),
                "websocket_connected": event_monitor.connected,
                "events_received": event_summary['total_events'] > 0,
                "session_ready": session_ready
            }
            
            print("✅ Success Criteria:")
            for criterion, result in success_criteria.items():
                status = "✅ PASS" if result else "❌ FAIL"
                print(f"   {criterion}: {status}")
            
            overall_success = all(success_criteria.values())
            print(f"\n🎯 Overall Test Result: {'✅ SUCCESS' if overall_success else '❌ FAILURE'}")
            
            if event_summary['total_events'] > 0:
                print(f"\n📡 RRWeb Events Details:")
                print(f"   Total Events: {event_summary['total_events']}")
                print(f"   Event Types: {event_summary['event_types']}")
                print(f"   Duration: {event_summary['duration']:.2f} seconds")
            
            return overall_success
            
        except Exception as e:
            print(f"\n❌ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    print("🚀 End-to-End Manual Workflow Execution Test")
    print("Testing session creation and rrweb event transmission...")
    print()
    
    success = asyncio.run(test_end_to_end_manual_execution())
    
    print("\n" + "=" * 70)
    if success:
        print("🎉 END-TO-END TEST COMPLETED SUCCESSFULLY!")
        print("✅ Session creation and rrweb event transmission working properly")
    else:
        print("💥 END-TO-END TEST FAILED!")
        print("❌ Issues detected in session creation or event transmission")
    print("=" * 70) 