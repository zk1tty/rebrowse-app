#!/Users/norikakizawa/.pyenv/versions/3.12.2/bin/python3
import sys, json, asyncio, threading, os, time, struct, errno
from typing import Optional

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

# --- NEW Named Pipe Paths (must match webui.py) ---
COMMAND_PIPE_PATH_TO_WEBUI = "/tmp/rebrowse_ui_command.pipe"
RESPONSE_PIPE_PATH_FROM_WEBUI = "/tmp/rebrowse_ui_command_response.pipe"

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

# CDP_QUEUE will be created after the asyncio event-loop is running so that it
# is bound to the correct loop.  A thread-safe reference to that loop is also
# stored so that handle_msg (running from a different thread) can enqueue
# events with loop.call_soon_threadsafe(...).
_cdp_queue_loop = None  # type: Optional[asyncio.AbstractEventLoop]
# Create the queue once at the module level. It will be bound to a loop later.
CDP_QUEUE = asyncio.Queue()

# --- Main Script Logic (imports and functions) ---
# Moved playwright import to after early_ready_ping in __main__

def _setup_pipe_writer(force_reopen=False):
    global _pipe_writer_file, HOST_STATUS_PIPE_PATH
    with _pipe_lock:
        if _pipe_writer_file and not _pipe_writer_file.closed and not force_reopen:
            emergency_log(f"[_setup_pipe_writer] Pipe writer already open and valid.")
            return True

        if _pipe_writer_file and not _pipe_writer_file.closed:
            try:
                emergency_log(f"[_setup_pipe_writer] Closing existing pipe writer.")
                _pipe_writer_file.close()
            except Exception as e_close:
                emergency_log(f"[_setup_pipe_writer] Error closing existing pipe: {e_close}")
            _pipe_writer_file = None
        
        if not os.path.exists(HOST_STATUS_PIPE_PATH):
            emergency_log(f"[_setup_pipe_writer] Pipe {HOST_STATUS_PIPE_PATH} does not exist. WebUI reader might not have created it yet.")
            return False # Return False, webui.py is responsible for creating it.
        
        try:
            emergency_log(f"[_setup_pipe_writer] Attempting to os.open pipe {HOST_STATUS_PIPE_PATH} (non-blocking write).")
            fd = os.open(HOST_STATUS_PIPE_PATH, os.O_WRONLY | os.O_NONBLOCK)
            _pipe_writer_file = os.fdopen(fd, 'w')
            emergency_log(f"[_setup_pipe_writer] Successfully opened pipe {HOST_STATUS_PIPE_PATH} for writing (non-blocking).")
            return True
        except FileNotFoundError: # Should be caught by os.path.exists generally
            emergency_log(f"[_setup_pipe_writer] Pipe {HOST_STATUS_PIPE_PATH} not found on os.open attempt.")
            _pipe_writer_file = None
            return False
        except OSError as e:
            if e.errno == 6: # ENXIO
                emergency_log(f"[_setup_pipe_writer] Pipe {HOST_STATUS_PIPE_PATH} has no reader (ENXIO). Will retry later.")
            else:
                emergency_log(f"[_setup_pipe_writer] OSError opening pipe {HOST_STATUS_PIPE_PATH}: {e}")
            _pipe_writer_file = None
            return False
        except Exception as e_unhandled_open:
            emergency_log(f"[_setup_pipe_writer] Unhandled exception opening pipe {HOST_STATUS_PIPE_PATH}: {e_unhandled_open}")
            _pipe_writer_file = None
            return False

def log_to_gradio(message: str):
    global _pipe_writer_file
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    # Construct the log entry that would normally be prefixed by Gradio/logger, but here it's raw for the pipe
    # The message itself is now expected to be a full JSON string from main_async_logic
    # No, keep it as host.py is the one adding the [NativeHost] prefix for the pipe consumers.
    # The actual JSON data is just `message`.
    # However, the current trace file shows `[NativeHost]` prefix from previous versions.
    # Let's assume for now `message` is the raw data (e.g. JSON string) and the receiver adds prefixes if needed.
    # OR, if host.py is to add this prefix, it should be consistent.
    # The current trace file only contains a few lines, one being:
    # [2025-06-06 00:13:04] [NativeHost] Received recording command from extension: START. Attempting to forward to webui.py...
    # This suggests host.py *does* add a prefix + timestamp for some of its log_to_gradio calls.
    # Let's make it consistent: if `message` is already a full JSON, just pass it. 
    # If it's a string message, prefix it.
    
    # Decision: For simplicity and to ensure trace file contains pure JSON lines for events,
    # this function will now assume `message` is the complete string to be written.
    # `main_async_logic` is now responsible for `json.dumps()`ing events.
    # For status messages FROM host.py, they should also be JSON if possible, or clearly distinct strings.

    # emergency_log(f"[log_to_gradio] Attempting to log: '{message[:100]}...'") # Can be too noisy

    if not _pipe_writer_file or _pipe_writer_file.closed:
        emergency_log(f"[log_to_gradio] Pipe writer not available or closed. Attempting to set up.")
        if not _setup_pipe_writer(): 
            emergency_log(f"[log_to_gradio] Failed to setup pipe writer. Message NOT SENT: '{message[:100]}...'")
            return # Message not sent
    
    with _pipe_lock:
        if _pipe_writer_file and not _pipe_writer_file.closed:
            try:
                _pipe_writer_file.write(message + '\n')
                _pipe_writer_file.flush()
            except BlockingIOError as e_block:
                # Non-blocking pipe may be temporarily full (EAGAIN). Retry a few times before giving up.
                retry_count = 0
                max_retries = 5
                wrote = False
                while retry_count < max_retries and not wrote:
                    time.sleep(0.02)  # brief back-off
                    try:
                        _pipe_writer_file.write(message + '\n')
                        _pipe_writer_file.flush()
                        wrote = True
                    except BlockingIOError:
                        retry_count += 1

                if not wrote:
                    emergency_log(f"[log_to_gradio] BlockingIOError (pipe full) after {max_retries} retries. Dropping message: '{message[:100]}...'")
            except BrokenPipeError:
                emergency_log(f"[log_to_gradio] Broken pipe. Message NOT SENT: '{message[:100]}...'. Attempting to reopen on next log.")
                try:
                    _pipe_writer_file.close()
                except Exception:
                    pass
                _pipe_writer_file = None
            except OSError as e:
                if e.errno == errno.EAGAIN:
                    emergency_log(f"[log_to_gradio] EAGAIN when writing to pipe – buffer full. Message dropped: '{message[:100]}...'")
                else:
                    emergency_log(f"[log_to_gradio] OSError writing to pipe: {e}. Message NOT SENT: '{message[:100]}...'")
                try:
                    _pipe_writer_file.close()
                except Exception:
                    pass
                _pipe_writer_file = None
            except Exception as e:
                emergency_log(f"[log_to_gradio] Error writing to pipe: {e}. Message NOT SENT: '{message[:100]}...'")
                try:
                    _pipe_writer_file.close()
                except Exception:
                    pass
                _pipe_writer_file = None
        else:
            emergency_log(f"[log_to_gradio] Pipe still not available after setup attempt. Message NOT SENT: '{message[:100]}...'")


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
            if CDP_QUEUE and _cdp_queue_loop:
                emergency_log(f"handle_msg: scheduling async put to CDP_QUEUE id={id(CDP_QUEUE)}")
                try:
                    fut = asyncio.run_coroutine_threadsafe(CDP_QUEUE.put(msg), _cdp_queue_loop)
                except Exception as e_put:
                    emergency_log(f"handle_msg: run_coroutine_threadsafe failed: {e_put}")
            else:
                emergency_log("handle_msg: CDP_QUEUE not ready yet — dropping CDP msg.")
            # log_to_gradio(f"CDP event enqueued: {msg.get('method', 'UnknownMethod')}")
            emergency_log(f"handle_msg: Successfully put_nowait to CDP_QUEUE (CDP event). Method: '{msg.get('method')}'.")
        except asyncio.QueueFull:
            emergency_log("handle_msg: CDP_QUEUE is full during put_nowait (CDP event).")
        except Exception as e:
            emergency_log(f"handle_msg: Error during put_nowait to CDP_QUEUE (CDP event): {type(e).__name__}: {e}")
    elif msg.get('type') == 'ui_event_to_host':
        ui_payload = msg.get('payload')
        if ui_payload and isinstance(ui_payload, dict): 
            event_type_from_payload = ui_payload.get('type') 
            selector_from_payload = ui_payload.get('selector') 
            emergency_log(f"handle_msg: Received UI event. Type: '{event_type_from_payload}', Selector: '{selector_from_payload}'.")
            if CDP_QUEUE and _cdp_queue_loop:
                emergency_log(f"handle_msg(UI): scheduling async put to CDP_QUEUE id={id(CDP_QUEUE)}")
                try:
                    fut = asyncio.run_coroutine_threadsafe(CDP_QUEUE.put({"source": "ui_event", "data": ui_payload}), _cdp_queue_loop)
                except Exception as e_ui_put:
                    emergency_log(f"handle_msg(UI): run_coroutine_threadsafe failed: {e_ui_put}")
            else:
                emergency_log("handle_msg: CDP_QUEUE not ready yet — dropping UI event.")
            # Immediately log the full UI event JSON to the pipe so it is never lost,
            # even if the main_async_logic loop hasn't processed it yet.
            try:
                log_to_gradio(json.dumps(ui_payload))
            except TypeError as e_json_ui:
                emergency_log(f"handle_msg(UI): Failed to json.dumps ui_payload: {e_json_ui}. Payload snippet: {str(ui_payload)[:200]}")
            emergency_log(f"handle_msg: Successfully put_nowait to CDP_QUEUE (UI event). Type: '{event_type_from_payload}'.")
        else:
            emergency_log(f"handle_msg: Received 'ui_event_to_host' message but payload was missing or not a dict. Payload: {str(ui_payload)[:200]}")
    elif msg.get('type') == 'client_ready_ack':
        emergency_log("handle_msg: Received client_ready_ack from extension – connection confirmed active.")
    elif msg.get('type') == 'extension_ping':
        emergency_log("handle_msg: Received extension_ping – replying with extension_pong.")
        send({'type': 'extension_pong', 'ts': time.time()})
    elif msg.get('type') == 'recording_command':
        command = msg.get('command')
        emergency_log(f"handle_msg: Received recording_command: {command}")
        log_to_gradio(f"Received recording command from extension: {command}. Attempting to forward to webui.py...")
        
        command_to_webui = ""
        if command == 'START':
            command_to_webui = "START_RECORDING"
        elif command == 'STOP':
            command_to_webui = "STOP_RECORDING"
        else:
            emergency_log(f"handle_msg: Unknown recording_command payload: {command}")
            send({
                'type': 'recording_status_update',
                'payload': {'status': 'error', 'message': f"Unknown recording command '{command}' received by host.py"}
            })
            return

        try:
            emergency_log(f"Attempting to write '{command_to_webui}' to {COMMAND_PIPE_PATH_TO_WEBUI}")
            fd = os.open(COMMAND_PIPE_PATH_TO_WEBUI, os.O_WRONLY | os.O_NONBLOCK)
            with os.fdopen(fd, 'w') as pipe_writer:
                pipe_writer.write(command_to_webui + '\n')
                pipe_writer.flush()
            emergency_log(f"Successfully wrote '{command_to_webui}' to {COMMAND_PIPE_PATH_TO_WEBUI}")
            send({
                'type': 'ack', 
                'received_event_type': 'recording_command', 
                'details': f"Command '{command}' relayed to webui.py via pipe."
            })
        except FileNotFoundError:
            err_msg = f"Failed to send command to webui: Pipe {COMMAND_PIPE_PATH_TO_WEBUI} not found. Webui might not be running or pipe not created."
            emergency_log(err_msg)
            log_to_gradio(err_msg)
            send({'type': 'recording_status_update', 'payload': {'status': 'error', 'message': err_msg}})
        except OSError as e:
            if e.errno == 6: 
                 err_msg = f"Failed to send command to webui: No reader on {COMMAND_PIPE_PATH_TO_WEBUI}. Webui might not be listening."
            else:
                 err_msg = f"Failed to send command to webui: OSError writing to {COMMAND_PIPE_PATH_TO_WEBUI}: {e}"
            emergency_log(err_msg)
            log_to_gradio(err_msg)
            send({'type': 'recording_status_update', 'payload': {'status': 'error', 'message': err_msg}})
        except Exception as e_pipe_write:
            err_msg = f"Exception sending command to webui via pipe {COMMAND_PIPE_PATH_TO_WEBUI}: {e_pipe_write}"
            emergency_log(err_msg)
            log_to_gradio(err_msg)
            send({'type': 'recording_status_update', 'payload': {'status': 'error', 'message': err_msg}})
    else:
        emergency_log(f"handle_msg: Unknown or unhandled message type received: '{msg.get('type')}'. Full msg: {str(msg)[:200]}...")

async def _listen_command_responses_pipe():
    """Listens on RESPONSE_PIPE_PATH_FROM_WEBUI for JSON responses from webui.py."""
    global RESPONSE_PIPE_PATH_FROM_WEBUI
    emergency_log(f"[_listen_command_responses_pipe] Starting. Response pipe path: {RESPONSE_PIPE_PATH_FROM_WEBUI}")

    # host.py is the reader of this pipe, so it should ensure it exists.
    if not os.path.exists(RESPONSE_PIPE_PATH_FROM_WEBUI):
        try:
            os.mkfifo(RESPONSE_PIPE_PATH_FROM_WEBUI)
            emergency_log(f"[_listen_command_responses_pipe] Created response pipe: {RESPONSE_PIPE_PATH_FROM_WEBUI}")
        except OSError as e:
            emergency_log(f"[_listen_command_responses_pipe] CRITICAL: Failed to create response pipe {RESPONSE_PIPE_PATH_FROM_WEBUI}: {e}. Cannot get command status from webui.")
            log_to_gradio(f"CRITICAL: host.py could not create response pipe {RESPONSE_PIPE_PATH_FROM_WEBUI}. Extension command feedback disabled.")
            await asyncio.Future() # Keep task alive forever so gather doesn't exit.

    emergency_log(f"[_listen_command_responses_pipe] Listener loop started for {RESPONSE_PIPE_PATH_FROM_WEBUI}")
    while True:
        pipe_file_resp = None
        try:
            emergency_log(f"[_listen_command_responses_pipe] Attempting to open response pipe for reading: {RESPONSE_PIPE_PATH_FROM_WEBUI} (blocks until writer)...")
            pipe_file_resp = open(RESPONSE_PIPE_PATH_FROM_WEBUI, 'r') # Blocking open
            emergency_log(f"[_listen_command_responses_pipe] Response pipe opened for reading: {RESPONSE_PIPE_PATH_FROM_WEBUI}")
            
            while True:
                line = pipe_file_resp.readline()
                if not line:
                    emergency_log("[_listen_command_responses_pipe] Writer (webui.py) closed response pipe or EOF. Re-opening...")
                    break 

                response_str = line.strip()
                if response_str:
                    emergency_log(f"[_listen_command_responses_pipe] Received response string: '{response_str}'")
                    try:
                        response_payload = json.loads(response_str)
                        if isinstance(response_payload, dict) and response_payload.get("source") == "extension_command_response":
                            emergency_log(f"[_listen_command_responses_pipe] Parsed response: {response_payload}")
                            send({"type": "recording_status_update", "payload": response_payload})
                            emergency_log(f"Sent recording_status_update to extension with payload: {response_payload.get('status')}")
                        else:
                            emergency_log(f"[_listen_command_responses_pipe] Received valid JSON but not an extension_command_response: {response_str[:200]}")
                    except json.JSONDecodeError as e_json:
                        emergency_log(f"[_listen_command_responses_pipe] JSONDecodeError for response '{response_str[:200]}...': {e_json}")
                    except Exception as e_proc_resp:
                        emergency_log(f"[_listen_command_responses_pipe] Error processing response '{response_str[:200]}...': {e_proc_resp}")
        except FileNotFoundError: # Should not happen if created above, but handle defensively
            emergency_log(f"[_listen_command_responses_pipe] Response pipe {RESPONSE_PIPE_PATH_FROM_WEBUI} not found. Recreating...")
            try:
                if os.path.exists(RESPONSE_PIPE_PATH_FROM_WEBUI): os.remove(RESPONSE_PIPE_PATH_FROM_WEBUI)
                os.mkfifo(RESPONSE_PIPE_PATH_FROM_WEBUI)
                emergency_log(f"[_listen_command_responses_pipe] Recreated response pipe {RESPONSE_PIPE_PATH_FROM_WEBUI}.")
            except OSError as e_mkrpipe:
                emergency_log(f"[_listen_command_responses_pipe] Failed to recreate response pipe: {e_mkrpipe}. Retrying outer loop in 10s.")
                await asyncio.sleep(10)
        except Exception as e_resp_pipe_outer:
            emergency_log(f"[_listen_command_responses_pipe] Unhandled error in response pipe loop: {e_resp_pipe_outer}")
            await asyncio.sleep(5) # Wait before retrying main loop for robustness
        finally:
            if pipe_file_resp:
                try: pipe_file_resp.close()
                except Exception as e_close_resp: emergency_log(f"[_listen_command_responses_pipe] Error closing response pipe: {e_close_resp}")
        
        await asyncio.sleep(1) # Prevent tight loop on continuous error

async def main_async_logic():
    emergency_log("main_async_logic started.")
    emergency_log(f"main_async_logic using CDP_QUEUE id={id(CDP_QUEUE)}")
    try:
        while True:
            try:
                msg_wrapper = await asyncio.wait_for(CDP_QUEUE.get(), timeout=1.0)
                emergency_log(f"main_async_logic: Retrieved item from CDP_QUEUE: keys={list(msg_wrapper.keys()) if isinstance(msg_wrapper, dict) else type(msg_wrapper)}")

                if msg_wrapper.get("source") == "ui_event":
                    actual_msg = msg_wrapper.get("data") 
                    event_type = actual_msg.get('type', 'Unknown UI Event')
                    
                    # Emergency log can remain detailed for debugging host.py itself
                    log_line_parts_for_emergency = [
                        f"Processing UI event from CDP_QUEUE: Type: {event_type}",
                        f"URL: '{actual_msg.get('url','N/A')[:70]}'",
                        f"Selector: '{actual_msg.get('selector', 'N/A')}'"
                    ]
                    if event_type == 'keydown': log_line_parts_for_emergency.append(f"Key: '{actual_msg.get('key','N/A')}'")
                    elif event_type == 'mousedown': 
                        log_line_parts_for_emergency.append(f"Button: {actual_msg.get('button','N/A')} @ ({actual_msg.get('x','N/A')},{actual_msg.get('y','N/A')})")
                        text_content = actual_msg.get('text')
                        if text_content: log_line_parts_for_emergency.append(f"Text: '{str(text_content)[:50]}'")
                    elif event_type == 'clipboard_copy':
                        text_content = actual_msg.get('text')
                        if text_content: log_line_parts_for_emergency.append(f"CopiedText: '{str(text_content)[:50]}...'")
                    emergency_log(", ".join(log_line_parts_for_emergency))
                    
                    # For log_to_gradio (which feeds the pipe and thus the trace file),
                    # send the entire UI event object as a JSON string.
                    try:
                        ui_event_json_str = json.dumps(actual_msg) # actual_msg is the full UI event payload
                        log_to_gradio(ui_event_json_str) # <<< THIS IS THE LINE FOR THE TRACE FILE
                    except TypeError as e_json_dump:
                        emergency_log(f"ERROR: Could not dump UI event to JSON: {e_json_dump}. Event: {str(actual_msg)[:200]}")
                        log_to_gradio(f'{{"error": "json_dump_failed_ui_event", "event_type": "{event_type}", "original_payload_snippet": "{str(actual_msg)[:100].replace("\"", "\\\"")}"}}')

                    send({'type': 'ack', 'received_event_type': 'ui_event', 'details': event_type})
                
                else: # Assuming it's a direct CDP event from the extension
                    actual_msg = msg_wrapper # actual_msg is the full CDP message here
                    cdp_method = actual_msg.get('method', 'Unknown CDP Method')
                    
                    # USER STORY: Filter out noisy CDP events from the trace file.
                    if cdp_method.startswith('Network.') or cdp_method.startswith('Runtime.'):
                        emergency_log(f"main_async_logic: Skipping noisy CDP event for trace file: {cdp_method}")
                    else:
                        emergency_log(f"main_async_logic: Processing direct CDP event from CDP_QUEUE: {cdp_method}")
                        try:
                            cdp_event_json_str = json.dumps(actual_msg)
                            log_to_gradio(cdp_event_json_str) # <<< THIS IS THE LINE FOR THE TRACE FILE
                        except TypeError as e_json_dump_cdp:
                            emergency_log(f"ERROR: Could not dump CDP event to JSON: {e_json_dump_cdp}. Event: {str(actual_msg)[:200]}")
                            log_to_gradio(f'{{"error": "json_dump_failed_cdp_event", "method": "{cdp_method}", "original_payload_snippet": "{str(actual_msg)[:100].replace("\"", "\\\"")}"}}')

                    send({'type': 'ack', 'received_event_type': 'cdp_event', 'details': cdp_method})
                
                CDP_QUEUE.task_done()
            except asyncio.TimeoutError:
                pass 
            except Exception as e_loop: 
                 emergency_log(f"main_async_logic: Exception in get/process loop: {type(e_loop).__name__}: {e_loop}")
                 # Escape quotes in error message for JSON compatibility
                 escaped_error_details = str(e_loop).replace("\"", "\\\"")
                 log_to_gradio(f'{{"error": "host_processing_loop_exception", "details": "{escaped_error_details}"}}')
                 await asyncio.sleep(1) 

    except asyncio.CancelledError:
        emergency_log("main_async_logic: asyncio.CancelledError caught.")
        log_to_gradio("Native host main_async_logic was cancelled.")
        raise 
    except Exception as e_main_logic:
        emergency_log(f"main_async_logic: Exception caught: {type(e_main_logic).__name__}: {e_main_logic}")
        escaped_e_main_logic = str(e_main_logic).replace("\"", "\\\"")
        log_to_gradio(f"Native host main_async_logic CRITICAL error: {escaped_e_main_logic}")
    finally:
        emergency_log("main_async_logic finished (entered finally block).")

async def run_async_main_with_listeners():
    """Start CDP processing and response-pipe listener in the current event loop."""

    # The loop is already running (async function), just grab it.
    loop = asyncio.get_running_loop()

    # Expose loop globally for the recv_thread to use safely.
    global _cdp_queue_loop
    # Bind the module-level queue to the now-running event loop.
    CDP_QUEUE._loop = loop
    _cdp_queue_loop = loop
    emergency_log(f"CDP_QUEUE (id={id(CDP_QUEUE)}) bound to loop={loop}")

    emergency_log("run_async_main_with_listeners: Starting main_async_logic and _listen_command_responses_pipe tasks.")

    main_cdp_task = asyncio.create_task(main_async_logic())
    response_listener_task = asyncio.create_task(_listen_command_responses_pipe())

    try:
        await asyncio.gather(main_cdp_task, response_listener_task)
    except Exception as e_gather:
        emergency_log(f"run_async_main_with_listeners: asyncio.gather threw an exception: {e_gather}")
        raise
    finally:
        emergency_log("run_async_main_with_listeners: asyncio.gather completed or was cancelled.")
        for task in (main_cdp_task, response_listener_task):
            if not task.done():
                task.cancel()
        await asyncio.sleep(0.1) # Let cancellations propagate

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
        emergency_log("Attempting to call run_async_main_with_listeners().")
        log_to_gradio("Attempting to start main async logic and command response listener...")
        # asyncio.run(main_async_logic()) # Old way
        asyncio.run(run_async_main_with_listeners()) # New way to include response listener
        emergency_log("run_async_main_with_listeners() completed without error.")
    except KeyboardInterrupt:
        emergency_log("KeyboardInterrupt caught in __main__.")
        # print("Native host shutting down...") # To Chrome stdio
        log_to_gradio("Native host shutting down (KeyboardInterrupt).")
    except Exception as e:
        emergency_log(f"Exception caught in __main__ after run_async_main_with_listeners: {type(e).__name__}: {e}")
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