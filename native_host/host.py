#!/Users/norikakizawa/.pyenv/versions/3.12.2/bin/python3
import sys, json, asyncio, threading, os, time, struct

# --- Emergency File Logger (for very early issues) ---
EMERGENCY_LOG_FILE = "/tmp/rebrowse_host_emergency.log"
_emergency_log_initialized_time = time.time()

def emergency_log(message):
    try:
        # To avoid massive logs if script restarts very rapidly, cap total log size or entries
        # For now, just basic append
        with open(EMERGENCY_LOG_FILE, "a") as f:
            f.write(f"[{time.strftime("%Y-%m-%d %H:%M:%S")}] {message}\n")
    except Exception:
        pass 

emergency_log("Host script started execution (top of file).")

# --- Global Send Function (used by early_ready_ping) ---
# This must be defined before early_ready_ping can be called.
def send(msg):
    message_json = json.dumps(msg)
    message_bytes = message_json.encode('utf-8')
    # Use explicit little-endian for 4-byte length prefix
    packed_length = struct.pack('<I', len(message_bytes)) 
    
    emergency_log(f"send: Preparing to send. JSON: '{message_json[:100]}...', Bytes len: {len(message_bytes)}, Packed len: {packed_length!r}")
    
    try:
        sys.stdout.buffer.write(packed_length)
        sys.stdout.buffer.write(message_bytes)
        sys.stdout.buffer.flush()
        emergency_log(f"send: Successfully sent message to stdout. First 100 chars: {message_json[:100]}...")
    except Exception as e_send:
        emergency_log(f"send: CRITICAL ERROR writing to stdout: {type(e_send).__name__}: {e_send}")

# --- Early Ready Ping Function ---
def early_ready_ping():
    emergency_log("early_ready_ping: Sending initial status BEFORE playwright import.")
    send({"type": "status", "message": "Native host ready and listening for CDP."})
    emergency_log("early_ready_ping: Initial status sent.")

# --- Configuration for Gradio Logging via Named Pipe (defined after send) ---
HOST_STATUS_PIPE_PATH = "/tmp/rebrowse_host_status.pipe"
_pipe_writer_file = None
_pipe_lock = threading.Lock()

CDP_QUEUE = asyncio.Queue()

# --- Main Script Logic (imports and functions) ---
# Moved playwright import to after early_ready_ping in __main__

def _setup_pipe_writer(force_reopen=False):
    global _pipe_writer_file, HOST_STATUS_PIPE_PATH
    with _pipe_lock:
        if _pipe_writer_file and not _pipe_writer_file.closed and not force_reopen:
            return True

        if _pipe_writer_file and not _pipe_writer_file.closed:
            try:
                _pipe_writer_file.close()
            except Exception as e_close:
                print(f"[HostPipe] Error closing existing pipe: {e_close}", file=sys.stderr)
            _pipe_writer_file = None
        
        if not os.path.exists(HOST_STATUS_PIPE_PATH):
            # print(f"[HostPipe] Pipe {HOST_STATUS_PIPE_PATH} does not exist. Gradio UI may not be ready.", file=sys.stderr)
            # Don't wait or error here, webui.py is responsible for creating it.
            # We will simply fail to open it and can retry later.
            return False
        
        try:
            # Open the FIFO in NON-BLOCKING write-only mode.  If no reader is present we
            # get an OSError with errno=ENXIO instead of blocking the entire main
            # thread, which previously prevented the async loop from ever starting.
            fd = os.open(HOST_STATUS_PIPE_PATH, os.O_WRONLY | os.O_NONBLOCK)
            _pipe_writer_file = os.fdopen(fd, 'w')
            print(f"[HostPipe] Successfully opened pipe {HOST_STATUS_PIPE_PATH} for writing (non-blocking).", file=sys.stderr)
            return True
        except FileNotFoundError:
            # This can happen if webui.py hasn't created the pipe yet.
            # print(f"[HostPipe] Pipe {HOST_STATUS_PIPE_PATH} not found on open attempt.", file=sys.stderr)
            _pipe_writer_file = None
            return False
        except OSError as e:
            # ENXIO (6) means "no reader" – treat as temporary and don't block.
            if e.errno == 6:
                # No reader yet; we'll retry later without killing the host.
                print(f"[HostPipe] Pipe {HOST_STATUS_PIPE_PATH} has no reader yet – will retry later.", file=sys.stderr)
            else:
                print(f"[HostPipe] OSError opening pipe {HOST_STATUS_PIPE_PATH}: {e}", file=sys.stderr)
            _pipe_writer_file = None
            return False

def log_to_gradio(message: str):
    global _pipe_writer_file
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    full_message = f"[{timestamp}] [NativeHost] {message}"
    # print(f"Attempting to log to Gradio: {full_message}", file=sys.stderr) # For host-side debug

    if not _pipe_writer_file or _pipe_writer_file.closed:
        if not _setup_pipe_writer(): # Attempt to open/reopen
            # print(f"[HostPipe] Failed to setup pipe writer. Cannot send: {full_message}", file=sys.stderr)
            return
    
    with _pipe_lock:
        if _pipe_writer_file and not _pipe_writer_file.closed:
            try:
                _pipe_writer_file.write(full_message + '\n')
                _pipe_writer_file.flush()
            except BrokenPipeError:
                print(f"[HostPipe] Broken pipe. webui.py may have closed. Attempting to reopen on next log.", file=sys.stderr)
                _pipe_writer_file.close() # Close our end
                _pipe_writer_file = None
                _setup_pipe_writer(force_reopen=True) # Try to reopen immediately for next message
            except Exception as e:
                print(f"[HostPipe] Error writing to pipe: {e}. Message: {full_message}", file=sys.stderr)
                # Consider closing and reopening on any write error
                try: _pipe_writer_file.close() 
                except: pass
                _pipe_writer_file = None
        # else:
            # print(f"[HostPipe] Pipe not available for writing: {full_message}", file=sys.stderr)


def recv_loop():
    emergency_log("recv_loop: Thread started, configured to read length-prefixed messages.")
    while True: # Keep trying to read messages as long as stdin is open
        try:
            # Read the 4-byte length prefix
            raw_length = sys.stdin.buffer.read(4)
            if not raw_length:
                emergency_log("recv_loop: EOF reached or stdin closed (no length received). Breaking loop.")
                break # stdin closed or no more data
            
            # The Chrome native-messaging spec uses little-endian for the 4-byte length field.
            # Use '<I' explicitly to avoid any ambiguity on non-x86 or ARM architectures.
            message_length = struct.unpack('<I', raw_length)[0]
            emergency_log(f"recv_loop: Received message length: {message_length}")

            # Read the message content.  sys.stdin.read(n) can legitimately return fewer
            # than n bytes on some platforms; keep reading until we have everything or
            # hit EOF.
            bytes_remaining = message_length
            chunks = []
            while bytes_remaining > 0:
                chunk = sys.stdin.buffer.read(bytes_remaining)
                if not chunk:  # EOF before we received the full payload – give up.
                    emergency_log(f"recv_loop: EOF encountered with {bytes_remaining} bytes still expected – message truncated. Aborting read loop.")
                    return
                chunks.append(chunk)
                bytes_remaining -= len(chunk)

            message_json = b"".join(chunks).decode('utf-8', errors='replace')
            emergency_log(f"recv_loop: Received message JSON (first 200 chars): '{message_json[:200]}...'")
            
            data = json.loads(message_json)
            emergency_log(f"recv_loop: Parsed JSON. Type: '{data.get('type')}', Details: '{str(data.get('message', data.get('method')))}'.")
            handle_msg(data)

        except struct.error as e_struct:
            emergency_log(f"recv_loop: struct.error unpacking length (stdin likely closed abruptly or bad data): {e_struct}. Breaking loop.")
            break
        except EOFError:
            emergency_log("recv_loop: EOFError encountered (stdin closed). Breaking loop.")
            break
        except KeyboardInterrupt: # Should not happen in this thread typically
            emergency_log("recv_loop: KeyboardInterrupt. Breaking loop.")
            break
        except Exception as e:
            emergency_log(f"recv_loop: Exception reading/processing message: {type(e).__name__}: {e}. Continuing to try and read if possible.")
            if isinstance(e, (json.JSONDecodeError)): 
                emergency_log(f"recv_loop: JSONDecodeError - message might be corrupt. Skipping to next read attempt.")
                continue 
            else: 
                emergency_log(f"recv_loop: Unhandled exception type during read, breaking loop: {type(e).__name__}")
                break
                
    emergency_log("recv_loop: Exited main read loop.")

def handle_msg(msg):
    emergency_log(f"handle_msg: Received msg. Type: '{msg.get('type')}', Method: '{msg.get('method')}'.")
    if msg.get('type') == 'cdp': # Use .get for safer access
        try:
            CDP_QUEUE.put_nowait(msg) # This is synchronous call from a thread
            log_to_gradio(f"CDP event enqueued: {msg.get('method', 'UnknownMethod')}")
            emergency_log(f"handle_msg: Successfully put_nowait to CDP_QUEUE (CDP event). Method: '{msg.get('method')}'.")
        except asyncio.QueueFull:
            emergency_log("handle_msg: CDP_QUEUE is full during put_nowait (CDP event).")
            # send({'type': 'error', 'error': 'CDP_QUEUE is full'})
        except Exception as e:
            emergency_log(f"handle_msg: Error during put_nowait to CDP_QUEUE (CDP event): {type(e).__name__}: {e}")
            # send({'type': 'error', 'error': f'Error adding to CDP_QUEUE: {str(e)}'})
    elif msg.get('type') == 'ui_event_to_host':
        ui_payload = msg.get('payload')
        if ui_payload and isinstance(ui_payload, dict): # Check if payload exists and is a dictionary
            event_type_from_payload = ui_payload.get('type') # Get type early for logging
            selector_from_payload = ui_payload.get('selector') # Get selector early for logging
            emergency_log(f"handle_msg: Received UI event. Type: '{event_type_from_payload}', Selector: '{selector_from_payload}'.")
            try:
                CDP_QUEUE.put_nowait({"source": "ui_event", "data": ui_payload})
                log_to_gradio(f"UI event enqueued: {event_type_from_payload}")
                emergency_log(f"handle_msg: Successfully put_nowait to CDP_QUEUE (UI event). Type: '{event_type_from_payload}'.")
            except asyncio.QueueFull:
                emergency_log("handle_msg: CDP_QUEUE is full during put_nowait (UI event).")
            except Exception as e:
                emergency_log(f"handle_msg: Error during put_nowait to CDP_QUEUE (UI event): {type(e).__name__}: {e}")
        else:
            emergency_log(f"handle_msg: Received 'ui_event_to_host' message but payload was missing or not a dict. Payload: {str(ui_payload)[:200]}")
    elif msg.get('type') == 'client_ready_ack':
        # Simply log; no further action needed, but acknowledge reception.
        emergency_log("handle_msg: Received client_ready_ack from extension – connection confirmed active.")
    elif msg.get('type') == 'extension_ping':
        # Reply with a pong so the extension knows we are still alive.
        emergency_log("handle_msg: Received extension_ping – replying with extension_pong.")
        send({'type': 'extension_pong', 'ts': time.time()})
    else:
        emergency_log(f"handle_msg: Unknown or unhandled message type received: '{msg.get('type')}'. Full msg: {str(msg)[:200]}...")

async def main_async_logic():
    emergency_log("main_async_logic started.")
    # The initial send is now done by early_ready_ping before this logic runs.
    # log_to_gradio("Native host main_async_logic started. Waiting for CDP messages...")
    # send({"type": "status", "message": "Native host ready and listening for CDP."})
    # emergency_log("main_async_logic: Sent initial 'ready' status to Chrome.") # This log is now redundant here
    try:
        while True:
            emergency_log("main_async_logic: Top of while True loop.")
            try:
                msg_wrapper = await asyncio.wait_for(CDP_QUEUE.get(), timeout=1.0) # Wait for 1 sec

                if msg_wrapper.get("source") == "ui_event":
                    actual_msg = msg_wrapper.get("data")
                    event_type = actual_msg.get('type', 'Unknown UI Event')
                    selector = actual_msg.get('selector', 'N/A')
                    key_pressed = actual_msg.get('key', 'N/A') # For keydown
                    button_clicked = actual_msg.get('button', 'N/A') # For mousedown (0,1,2)
                    x_coord = actual_msg.get('x', 'N/A') # For mousedown
                    y_coord = actual_msg.get('y', 'N/A') # For mousedown
                    text_content = actual_msg.get('text', 'N/A') # For mousedown or copy

                    log_line_parts = [
                        f"Got UI event from CDP_QUEUE: Type: {event_type}",
                        f"Selector: '{selector}'"
                    ]
                    if event_type == 'keydown':
                        log_line_parts.append(f"Key: '{key_pressed}'")
                    elif event_type == 'mousedown':
                        log_line_parts.append(f"Button: {button_clicked} @ ({x_coord},{y_coord})")
                        if text_content and text_content != 'N/A':
                             log_line_parts.append(f"Text: '{text_content[:50]}'") # Log first 50 chars of text
                    elif event_type == 'clipboard_copy' and text_content and text_content != 'N/A':
                        log_line_parts.append(f"CopiedText: '{text_content[:50]}...'")
                    
                    emergency_log(", ".join(log_line_parts))
                    log_to_gradio(", ".join(log_line_parts)) # Also send more detail to Gradio
                    
                    send({'type': 'ack', 'received_event_type': 'ui_event', 'details': event_type}) # Ack back to extension
                else: # Assuming it's a direct CDP event
                    actual_msg = msg_wrapper # The whole message is the CDP event
                    cdp_method = actual_msg.get('method', 'Unknown CDP Method')
                    emergency_log(f"main_async_logic: Got CDP event from CDP_QUEUE: {cdp_method}")
                    log_to_gradio(f"Processing CDP message: {cdp_method}")
                    send({'type': 'ack', 'received_event_type': 'cdp_event', 'details': cdp_method})
                
                CDP_QUEUE.task_done()
                # Here you would dispatch to Playwright or your recording logic based on msg_wrapper content
            except asyncio.TimeoutError:
                emergency_log("main_async_logic: Timeout waiting for CDP_QUEUE.get(), queue still empty. Looping.")
                # send({"type": "heartbeat", "message": "Host alive, queue empty"}) # Optional: send heartbeat to extension
                pass # Just loop again if queue is empty
            except Exception as e_loop: # Catch other errors in main processing loop
                 emergency_log(f"main_async_logic: Exception in get/process loop: {type(e_loop).__name__}: {e_loop}")
                 log_to_gradio(f"Error in main_async_logic loop: {e_loop}")
                 await asyncio.sleep(1) # prevent tight loop on continuous error if get() itself errors somehow

    except asyncio.CancelledError:
        emergency_log("main_async_logic: asyncio.CancelledError caught.")
        log_to_gradio("Native host main_async_logic was cancelled.")
        raise 
    except Exception as e_main_logic:
        emergency_log(f"main_async_logic: Exception caught: {type(e_main_logic).__name__}: {e_main_logic}")
        log_to_gradio(f"Native host main_async_logic CRITICAL error: {e_main_logic}")
        # Optionally re-raise or sys.exit depending on desired behavior post-error
    finally:
        emergency_log("main_async_logic finished (entered finally block).")


# This is the main synchronous function that will run the asyncio event loop.
# It replaces the `asyncio.run(main())` if `main` itself becomes a sync orchestrator.
# For now, sticking to the provided `asyncio.run(main_async_logic())` with `main_async_logic` defined.
def run_async_main(): 
    asyncio.run(main_async_logic())    

if __name__ == '__main__':
    emergency_log("__main__ block entered.")
    
    # Send the ready ping immediately, before any heavy imports or other setup.
    early_ready_ping()

    emergency_log("Attempting to import playwright.sync_api...")
    try:
        from playwright.sync_api import sync_playwright
        emergency_log("Successfully imported playwright.sync_api (after early ping).")
    except ImportError as e_import:
        emergency_log(f"CRITICAL: Failed to import playwright.sync_api (after early ping): {e_import}")
        sys.exit(1) 
    except Exception as e_gen_import:
        emergency_log(f"CRITICAL: Generic error importing playwright (after early ping): {e_gen_import}")
        sys.exit(1)

    # Start the stdin listener thread
    recv_thread = threading.Thread(target=recv_loop) # daemon=False by default
    # recv_thread.daemon = False # Explicitly ensuring it's not a daemon
    recv_thread.start()
    emergency_log("recv_loop thread created and configured (non-daemon).")
    # print("Native host recv_loop thread started.") # This goes to Chrome, might be lost
    emergency_log("Native host recv_loop thread started (this goes to emergency log).")
    log_to_gradio("Native host recv_loop thread started.")
    emergency_log("recv_loop thread started (according to main thread).")

    # Run the main async logic
    # This will block until main_async_logic() completes or is cancelled.
    try:
        emergency_log("Attempting to call run_async_main().")
        log_to_gradio("Attempting to start main_async_logic...")
        run_async_main()
        emergency_log("run_async_main() completed without error (this means main_async_logic returned normally).")
    except KeyboardInterrupt:
        emergency_log("KeyboardInterrupt caught in __main__.")
        # print("Native host shutting down...") # To Chrome stdio
        log_to_gradio("Native host shutting down (KeyboardInterrupt).")
    except Exception as e:
        emergency_log(f"Exception caught in __main__ after run_async_main: {type(e).__name__}: {e}")
        # print(f"Native host encountered an error: {e}") # To Chrome stdio
        log_to_gradio(f"Native host CRITICAL error: {e}")
        send({'type': 'error', 'error': f'Main loop crashed: {str(e)}'})
    finally:
        emergency_log("Main try block finished, entering finally in __main__.")
        # print("Native host exited.") # To Chrome stdio
        emergency_log("Native host exited (this goes to emergency log).")
        log_to_gradio("Native host exited.")
        if _pipe_writer_file and not _pipe_writer_file.closed:
            with _pipe_lock:
                _pipe_writer_file.close()
                _pipe_writer_file = None
                # print("[HostPipe] Closed pipe on exit.", file=sys.stderr) # To host stderr
                emergency_log("[HostPipe] Closed pipe on exit in __main__.")
        emergency_log("__main__ block finished execution.") 