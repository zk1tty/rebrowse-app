# Manual Testing Guide: Frontend Format Verification

## Overview
This guide helps you manually verify that the Amazon Prime Video workflow issues have been resolved through the backend event format fixes.

## Prerequisites
- Backend server running on `http://localhost:8000`
- Chrome browser with development tools
- Access to Amazon Prime Video (or use test URLs)

## Test Scenarios

### 1. Basic Event Format Test

**Steps:**
1. Start a visual workflow:
   ```bash
   curl -X POST http://localhost:8000/workflows/execute/visual \
     -H "Content-Type: application/json" \
     -d '{
       "name": "test-workflow",
       "inputs": {"url": "https://example.com"},
       "visual_streaming": true,
       "visual_quality": "standard"
     }'
   ```

2. Note the `session_id` from the response

3. Check streaming status:
   ```bash
   curl http://localhost:8000/workflows/visual/{session_id}/status
   ```

4. **Expected Response Format:**
   ```json
   {
     "success": true,
     "session_id": "visual-xxxxx",
     "streaming_active": true,
     "streaming_ready": true,
     "events_processed": 5,
     "events_buffered": 0,
     "connected_clients": 0
   }
   ```

5. **❌ Old Format (Fixed):**
   ```json
   {
     "event_type": 2,
     "event_data": {...},
     "phase": "executing"
   }
   ```

6. **✅ New Format (Current):**
   ```json
   {
     "event": {...},
     "session_id": "visual-xxxxx",
     "sequence_id": 0
   }
   ```

### 2. WebSocket Event Stream Test

**Steps:**
1. Open Chrome Developer Tools → Network tab
2. Connect to WebSocket: `ws://localhost:8000/workflows/visual/{session_id}/stream`
3. Send: `{"type": "client_ready"}`
4. Observe incoming messages

**Expected Event Structure:**
```json
{
  "session_id": "visual-xxxxx",
  "timestamp": 1234567890.123,
  "event": {
    "type": 2,
    "data": {
      "node": {...},
      "initialOffset": {...}
    },
    "timestamp": 1234567890123
  },
  "sequence_id": 0,
  "metadata": {...}
}
```

**❌ Issues to Watch For:**
- Missing `event` field
- `event_data` instead of `event`
- `sequence_id` starting at 1 instead of 0
- Missing `session_id`

### 3. Amazon Prime Video CSP Bypass Test

**Steps:**
1. Start Amazon Prime Video workflow:
   ```bash
   curl -X POST http://localhost:8000/workflows/execute/visual \
     -H "Content-Type: application/json" \
     -d '{
       "name": "amazon-prime-test",
       "inputs": {"url": "https://www.amazon.com/Prime-Video/b?ie=UTF8&node=2676882011"},
       "visual_streaming": true,
       "visual_quality": "standard"
     }'
   ```

2. Wait 10-15 seconds for CSP bypass to take effect

3. Check events are being captured:
   ```bash
   curl http://localhost:8000/workflows/visual/{session_id}/status
   ```

4. **Success Indicators:**
   - `events_processed > 0`
   - `streaming_ready: true`
   - `browser_ready: true`

**❌ CSP Bypass Failed:**
- `events_processed: 0` after 15+ seconds
- Console errors about script injection
- No FullSnapshot events

**✅ CSP Bypass Successful:**
- Multiple events captured (10+ events)
- FullSnapshot events present
- No injection errors

### 4. Frontend Integration Test

**Steps:**
1. Create test HTML file:
   ```html
   <!DOCTYPE html>
   <html>
   <head>
       <script src="https://cdn.jsdelivr.net/npm/rrweb@latest/dist/rrweb.min.js"></script>
   </head>
   <body>
       <div id="viewer"></div>
       <script>
           const ws = new WebSocket('ws://localhost:8000/workflows/visual/{session_id}/stream');
           let replayer = null;
           
           ws.onmessage = function(event) {
               const data = JSON.parse(event.data);
               
               // 🔧 FIXED: Check for 'event' field (not 'event_data')
               if (data.event) {
                   const rrwebEvent = data.event;
                   
                   // Initialize replayer on first FullSnapshot
                   if (rrwebEvent.type === 2 && !replayer) {
                       replayer = new rrweb.Replayer([], {
                           target: document.getElementById('viewer'),
                           liveMode: true
                       });
                       replayer.startLive();
                   }
                   
                   // Add event to replayer
                   if (replayer) {
                       replayer.addEvent(rrwebEvent);
                   }
               }
           };
       </script>
   </body>
   </html>
   ```

2. Open in browser and check console for errors

**❌ Frontend Issues:**
- "No event data found in message"
- "Expected: 0 Got: 1" sequence errors
- "Very few elements detected"
- DOM reconstruction failures

**✅ Frontend Success:**
- Visual content appears in viewer
- Real-time updates working
- No console errors

### 5. Sequence ID Verification

**Steps:**
1. Connect to WebSocket stream
2. Collect first 10 events
3. Check sequence_id values

**Expected Sequence:**
```
Event 1: sequence_id: 0
Event 2: sequence_id: 1
Event 3: sequence_id: 2
...
```

**❌ Sequence Issues:**
- First event has `sequence_id: 1`
- Gaps in sequence (0, 1, 3, 4...)
- Non-incremental sequence

**✅ Sequence Correct:**
- Starts at 0
- Increments by 1
- No gaps

## Success Criteria

### All Tests Pass When:
1. **Event Format**: All events have `event` field (not `event_data`)
2. **Sequence ID**: Starts at 0, increments correctly
3. **CSP Bypass**: Amazon Prime Video captures events successfully
4. **Frontend**: rrweb replayer works without errors
5. **DOM Reconstruction**: FullSnapshot events enable proper rendering

### Known Fixed Issues:
- ❌ ~~"No event data found in message"~~ → ✅ Fixed: `event` field present
- ❌ ~~"Expected: 0 Got: 1"~~ → ✅ Fixed: sequence_id starts at 0
- ❌ ~~"Very few elements detected"~~ → ✅ Fixed: CSP bypass working
- ❌ ~~DOM reconstruction failures~~ → ✅ Fixed: proper FullSnapshot events

## Troubleshooting

### If Tests Still Fail:

1. **Check Backend Logs:**
   ```bash
   tail -f logs/backend.log | grep -E "(event|streaming|visual)"
   ```

2. **Verify Event Structure:**
   ```bash
   # Check if old format is still being used
   curl http://localhost:8000/workflows/visual/{session_id}/status | jq
   ```

3. **Test with Simple URL First:**
   ```bash
   # Use example.com instead of Amazon Prime Video
   curl -X POST http://localhost:8000/workflows/execute/visual \
     -d '{"name": "simple-test", "inputs": {"url": "https://example.com"}, "visual_streaming": true}'
   ```

4. **Check Browser Network Tab:**
   - Look for WebSocket connection
   - Verify message format
   - Check for CSP errors

## Expected Timeline

- **Event Format Fix**: Immediate (should work right away)
- **Sequence ID Fix**: Immediate (first event should be 0)
- **CSP Bypass**: 10-15 seconds (injection + recording start)
- **Frontend Integration**: 2-3 seconds (after FullSnapshot)

## Contact
If any tests fail, provide:
1. Session ID
2. Browser console errors
3. Backend logs
4. WebSocket message samples 