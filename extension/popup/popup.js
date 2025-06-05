document.addEventListener('DOMContentLoaded', () => {
  const startButton = document.getElementById('startButton');
  const stopButton = document.getElementById('stopButton');
  const statusMessage = document.getElementById('statusMessage');

  function handleStatusUpdate(data) {
    if (!data || !data.status) {
      statusMessage.textContent = "Received unknown status update.";
      console.warn("[Rebrowse Popup] handleStatusUpdate received invalid data:", data);
      // Default to a safe, idle state
      startButton.disabled = false;
      stopButton.disabled = true;
      return;
    }

    if (data.status === 'recording_started' || data.status === 'active') {
      startButton.disabled = true;
      stopButton.disabled = false;
      statusMessage.textContent = data.message || "Recording active.";
    } else if (data.status === 'recording_stopped' || data.status === 'idle') {
      startButton.disabled = false;
      stopButton.disabled = true;
      statusMessage.textContent = data.message || "Recording stopped.";
      if (data.filePath) {
        statusMessage.textContent += ` Path: ${data.filePath.split('/').pop()}`; // Show only filename
      }
    } else if (data.status.startsWith('error')) {
      statusMessage.textContent = "Error: " + (data.message || "Unknown error");
      // Reset buttons to a safe state, allowing user to try again
      startButton.disabled = false;
      stopButton.disabled = true;
    } else {
        // Handle any other status as idle for safety
        startButton.disabled = false;
        stopButton.disabled = true;
        statusMessage.textContent = data.message || data.status;
    }
  }

  startButton.addEventListener('click', () => {
    console.log('[Rebrowse Popup] Start Recording button clicked.');
    statusMessage.textContent = 'Starting...';
    // Disable start, enable stop (optimistic update)
    startButton.disabled = true;
    stopButton.disabled = false;
    chrome.runtime.sendMessage({ source: 'popup', action: 'start_recording' }, response => {
      if (chrome.runtime.lastError) {
        console.error('[Rebrowse Popup] Error sending start_recording:', chrome.runtime.lastError.message);
        const errorData = { status: 'error', message: 'Failed to send start command: ' + chrome.runtime.lastError.message };
        handleStatusUpdate(errorData);
      }
    });
  });

  stopButton.addEventListener('click', () => {
    console.log('[Rebrowse Popup] Stop Recording button clicked.');
    statusMessage.textContent = 'Stopping...';
    // Disable stop (optimistic update)
    stopButton.disabled = true;
    chrome.runtime.sendMessage({ source: 'popup', action: 'stop_recording' }, response => {
      if (chrome.runtime.lastError) {
        console.error('[Rebrowse Popup] Error sending stop_recording:', chrome.runtime.lastError.message);
        // If stopping fails, the recording might still be active, so re-enable stop button
        stopButton.disabled = false;
        statusMessage.textContent = 'Error stopping: ' + chrome.runtime.lastError.message;
      }
    });
  });

  // Listen for status updates from background.js
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === 'recording_status') {
      console.log('[Rebrowse Popup] Received live status update:', message.data);
      handleStatusUpdate(message.data);
    }
  });

  // --- Query initial status when popup opens ---
  console.log('[Rebrowse Popup] Requesting initial recording status...');
  chrome.runtime.sendMessage({ source: 'popup', action: 'get_recording_status' }, response => {
    if (chrome.runtime.lastError) {
      console.error('[Rebrowse Popup] Error getting initial status:', chrome.runtime.lastError.message);
      handleStatusUpdate({ status: 'error', message: 'Cannot connect to background service.' });
      return;
    }
    
    if (response && response.type === 'recording_status') {
      console.log('[Rebrowse Popup] Received initial status:', response.data);
      handleStatusUpdate(response.data);
    } else {
      console.warn('[Rebrowse Popup] Got unexpected response for initial status, assuming idle.', response);
      handleStatusUpdate({ status: 'idle', message: 'Ready to record.' });
    }
  });
}); 