# Chrome extension -- Rebrowse

## Tech architecture
- overall
![Screenshot 2025-06-02 at 11 30 39 PM](https://github.com/user-attachments/assets/0480f653-7c48-4069-9c18-88a5c59cc984)

### UI arc

1. Chrome Extension UI (e.g., popup.html):
  - Primary Role: Quick, in-context actions related to the active browser tab.
  - Functionality:
    - "Start Recording" button: Sends a message to background.js, which in turn will send a native message to host.py to initiate recording for the active tab.
    - "Stop Recording" button: Similarly, tells host.py via background.js to stop recording and save the trace.
  - Status: Could show very basic status like "Recording" / "Idle" / "Error". This status would likely be pushed from host.py back to background.js and then to the popup.

2. Gradio UI (webui.py):
  - Primary Role: More comprehensive trace management, replay functionality, detailed status display, and configuration.
  - Functionality:
    - Trace Management: Listing, selecting trace files (as you currently have).
    - Replay: Initiating and controlling the replay of selected traces (as you currently have).
    - Detailed Status/Logs: Displaying logs and status updates originating from host.py (e.g., "Connected to browser," "CDP event received," "Recording started/stopped," errors from the native host). This is a key part of our minimal release.
    - Configuration: (Future) Settings related to recording, replay, etc.

### Process Sequence  

1. Triggering a trace from Gradio and replaying
  - NamePipe: a Streaming method of inter-process communication (IPC) that allows processes to communicate through a shared memory buffer.
    `host.py`(one-writer) adn `webui.py`(one-reader) is connected with namepipe.
  - multi-thread: we’ll graduate to Unix-domain sockets or a message broker for multi-reader or cross-machine delivery.
  - Note: The chosen path /tmp/rebrowse_host_status.pipe is common for temporary pipes on Unix-like systems (Linux, macOS). on Windows, pywin32 library or a different IPC mechanism like sockets. 
![Screenshot 2025-06-03 at 6 54 50 PM](https://github.com/user-attachments/assets/39c0f0a3-1680-4c69-a827-531b32384da6)

  | Step                     | Detail        |                                                                                                                                                                                                    
  | ------------------------ | ------------------------ |
  | 1. Gradio action         | The “Replay” button in `webui.py` calls an async function that writes a JSON command to the **FIFO** or hits a tiny HTTP endpoint exposed by `host.py`.                                                                                                                                                                                                          |
  | 2. Native host picks tab | Because the extension already sent the active `tabId` when it started recording, `host.py` can resolve “same tab” by that ID or ask `background.js` for the current active tab if none recorded.                                                                                                                                                                 |
  | 3. Native-message bridge | `host.py` sends `{cmd:"replay", trace:<array_of_steps>, tabId}` via `stdout`.  `background.js` receives it in `chrome.runtime.onMessageExternal`.                                                                                                                                                                                                                |
  | 4. Replay driver         | The **simplest path** is for `background.js` to loop over the JSONL entries and translate each into a CDP call with `chrome.debugger.sendCommand`— ⚠️no Playwright needed for replay.  If you already have a Playwright “replayer” written, run it inside `host.py` *connected to the same Chrome instance* (`chromium.connect_over_cdp("http://localhost:9222")`). |
  | 5. Status back-flow      | After each step, `background.js` posts `{"phase":"replay","step":n}` back to `host.py`, which writes “Replay 35 %” into the FIFO, so Gradio’s textbox autoscrolls.        |                                                                                                                  
## Shipping layout
| Artifact                      | File(s)                                                    | How user gets it                                                                                                                                                                                                                                                                                                |
| ----------------------------- | ---------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Chrome Extension**       | `rebrowse_ext.zip` → Web Store                             | • Contains `manifest.json`, `background.js`, `content.js`, icons, popup.<br>• Lists permission `"nativeMessaging"` and host name `"com.rebrowse.host"`.                                                                                                                                                         |
| **2. Native Host bundle**     | **macOS `.pkg` installer** <br>*(or `.dmg` drag-and-drop)* | • Installs `rebrowse_native` self-contained binary (PyInstaller/Nuitka) to `/usr/local/bin/`.<br>• Drops `com.rebrowse.host.json` into the NativeMessagingHosts folder, pointing at that binary.<br>• Optionally adds a LaunchAgent so the binary runs head-less at login (hosting Gradio on `localhost:7860`). |
| *(optional)* Thin menubar app | `RebrowseTray.app`                                         | Bundled inside the same `.pkg`; just UI glue that talks to `localhost:7860`.                                                                                                                                                                                                                                    |
## Functionalities must-stay at local
- Yes—cloud can own storage, scheduling, analytics, auth.
- No—real-time browser control still needs a local process (or all-JS code in the extension) because of Chrome security boundaries.
- Path forward: shrink host.py to a minimal relay, migrate everything else to your cloud dashboard, and revisit an all-extension architecture once your replay/record logic is fully ported to TypeScript.

| Need                                                     | Why cloud can’t replace it                                                                                                              |
| -------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| **CDP commands** (`Input.dispatchKeyEvent`, `DOM.click`) | Chrome blocks remote WebSockets from the public Internet; only a process on `127.0.0.1` that owns the debugging port can drive the tab. |
| **Native file dialogs / clipboard**                      | Clipboard / file-picker APIs are exposed only to extensions or native apps, not to remote origins.                                      |
| **Low-latency event feedback**                           | 20-50 ms round-trip over localhost vs. 200 + ms to the nearest PoP; user-perceived lag matters for live overlays, type-ahead, etc.      |
