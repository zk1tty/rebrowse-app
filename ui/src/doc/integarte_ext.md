# Chrome Extension Integration

## New Workflow Processing Flow

```
Extension Upload → Processing Page → Final Workflow Page
     ↓               ↓                    ↓
POST /upload    Poll /status         GET /workflows/{id}
Returns job_id  Shows progress       Shows final workflow
(Instant)       (Real-time)          (Complete)
```

## Chrome Extension Usage

### Option 1: Direct API Call (Recommended)
```javascript
// In your Chrome extension content script or popup
async function uploadRecording(recordingData) {
  try {
    // Upload the recording
    const response = await fetch('/workflows/upload', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(recordingData)
    });
    
    const { job_id } = await response.json();
    
    // Navigate to processing page
    const processingUrl = `/wf/processing/${job_id}`;
    
    // Open in new tab
    await chrome.tabs.create({
      url: `https://app.rebrowse.me${processingUrl}`,
      active: true
    });
    
    return job_id;
  } catch (error) {
    console.error('Upload failed:', error);
    throw error;
  }
}
```

### Option 2: Using Utility Functions
```javascript
// Import the utility function (if bundling with the frontend)
import { uploadAndNavigateToProcessing } from './utils/extensionHelpers';

// Use in extension
async function handleRecordingComplete(recordingData) {
  try {
    const jobId = await uploadAndNavigateToProcessing(recordingData);
    console.log('Upload started with job ID:', jobId);
  } catch (error) {
    console.error('Upload failed:', error);
  }
}
```

## Frontend Processing Flow

### 1. Processing Page (`/wf/processing/{job_id}`)
- Shows upload progress with real-time polling
- Displays estimated time remaining
- Automatically redirects when complete

### 2. Final Workflow Page (`/wf/{workflow_id}`)
- Shows the completed workflow
- Allows editing and execution
- Public access (no authentication required)

## API Endpoints

### Upload Endpoint
```
POST /workflows/upload
Content-Type: application/json

{
  "recording_data": { ... },
  "metadata": { ... }
}

Response:
{
  "job_id": "uuid-here"
}
```

### Status Endpoint
```
GET /workflows/upload/{job_id}/status

Response:
{
  "status": "pending|processing|completed|failed",
  "progress": 75,
  "estimated_remaining_seconds": 30,
  "workflow_id": "uuid-here", // only when completed
  "error": "error message"     // only when failed
}
```

## URL Structure

- `/` - Gallery (public workflows)
- `/wf/processing/{job_id}` - Processing page with progress
- `/wf/{workflow_id}` - Final workflow view
- `/workflows/{name}` - Legacy private workflow access (authenticated) 