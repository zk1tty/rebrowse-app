import time
import logging
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from .views import (
    VisualStreamingStatusResponse,
    VisualStreamingSessionInfo,
    VisualStreamingSessionsResponse,
    EnhancedVisualStreamingSessionsResponse,
)
from .execution_history_service import get_execution_history_service
from .dependencies import supabase

logger = logging.getLogger(__name__)

# Visual streaming router with dedicated API prefix
visual_router = APIRouter(prefix='/workflows/visual')


@visual_router.websocket("/{session_id}/stream")
async def visual_streaming_websocket(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for rrweb visual streaming"""
    try:
        # SESSION ID NORMALIZATION (same logic as status endpoint)
        original_session_id = session_id
        if not session_id.startswith("visual-"):
            try:
                import uuid
                uuid.UUID(session_id)  # Validate UUID format
                session_id = f"visual-{session_id}"
                logger.info(f"WebSocket: Normalized session ID from '{original_session_id}' to '{session_id}'")
            except ValueError:
                await websocket.accept()
                await websocket.send_json({
                    "error": f"Invalid session ID format: {original_session_id}",
                    "type": "error"
                })
                await websocket.close()
                return
        
        # Import visual streaming components
        try:
            from backend.visual_streaming import streaming_manager
            from backend.websocket_manager import websocket_manager
        except ImportError:
            await websocket.accept()
            await websocket.send_json({
                "error": "Visual streaming components not available",
                "type": "error"
            })
            await websocket.close()
            return
        
        try:
            # Get or create streamer for session (using normalized session_id)
            streamer = streaming_manager.get_or_create_streamer(session_id)
            
            # Connect client to WebSocket manager (this will handle websocket.accept())
            client_id = await websocket_manager.handle_client_connection(websocket, session_id)
            # NOTE: Do not pre-send buffered events; client will request sequence reset
            
            # Keep connection alive and handle messages
            while True:
                try:
                    # Wait for messages from client
                    message = await websocket.receive_json()
                    
                    # Handle different message types
                    message_type = message.get("type", "unknown")
                    
                    if message_type == "ping":
                        await websocket.send_json({"type": "pong", "timestamp": time.time()})
                    elif message_type == "client_ready":
                        await websocket.send_json({
                            "type": "status", 
                            "message": "Client connected to visual stream",
                            "session_id": session_id
                        })
                    elif message_type == "sequence_reset_request":
                        # Per-client sequence reset: mark state and try to force a fresh FullSnapshot
                        try:
                            hist = float(message.get("history_window_seconds", 3.0))
                        except Exception:
                            hist = 3.0
                        # Mark reset for this websocket
                        if hasattr(streamer, 'mark_sequence_reset_for_client'):
                            streamer.mark_sequence_reset_for_client(websocket, history_window_seconds=hist)
                        # Try to force a fresh FullSnapshot from the running recorder
                        try:
                            from workflow_use.browser.browser_factory import browser_factory
                            recorder = await browser_factory.get_recorder_for_session(session_id)
                            if recorder and hasattr(recorder, 'force_full_snapshot'):
                                _ = await recorder.force_full_snapshot()
                        except Exception as _e:
                            logger.debug(f"force_full_snapshot attempt failed or unavailable: {_e}")
                        # Acknowledge request
                        await websocket.send_json({
                            "type": "sequence_reset_ack",
                            "session_id": session_id,
                            "history_window_seconds": hist
                        })
                    else:
                        # Log unknown message types
                        logger.warning(f"Unknown message type from client {client_id}: {message_type}")
                        
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logger.error(f"Error in visual streaming WebSocket: {e}")
                    break
                    
        finally:
            # Cleanup client connection
            await websocket_manager.handle_client_disconnection(client_id)
            
    except Exception as e:
        logger.error(f"Error in visual streaming WebSocket setup: {e}")
        try:
            await websocket.send_json({"error": str(e), "type": "error"})
            await websocket.close()
        except:
            pass


@visual_router.get("/{session_id}/status", response_model=VisualStreamingStatusResponse)
async def get_visual_streaming_status(session_id: str):
    """Get status of visual streaming session with readiness check"""
    try:
        # Normalize session ID
        original_session_id = session_id
        if not session_id.startswith("visual-"):
            try:
                import uuid
                uuid.UUID(session_id)
                session_id = f"visual-{session_id}"
                logger.info(f"Normalized session ID from '{original_session_id}' to '{session_id}'")
            except ValueError:
                logger.error(f"Invalid session ID format: '{original_session_id}' - must be UUID or visual-UUID format")
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid session ID format: '{original_session_id}'. Must be a valid UUID or 'visual-<UUID>' format."
                )
        else:
            uuid_part = session_id[7:]
            try:
                import uuid
                uuid.UUID(uuid_part)
            except ValueError:
                logger.error(f"Invalid UUID in session ID: '{session_id}' - UUID part '{uuid_part}' is invalid")
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid session ID format: '{session_id}'. The UUID part '{uuid_part}' is not valid."
                )
        
        # Import components
        try:
            from backend.visual_streaming import streaming_manager
            from backend.websocket_manager import websocket_manager
        except ImportError:
            raise HTTPException(status_code=503, detail="Visual streaming components not available")
        
        # Get streamer
        streamer = streaming_manager.get_streamer(session_id)
        if not streamer:
            logger.warning(f"Session not found: '{session_id}' (original: '{original_session_id}')")
            return VisualStreamingStatusResponse(
                success=False,
                session_id=session_id,
                streaming_active=False,
                streaming_ready=False,
                browser_ready=False,
                events_processed=0,
                events_buffered=0,
                connected_clients=0,
                error=f"Session not found: '{session_id}'"
            )
        
        stats = streamer.get_stats()
        session_status = websocket_manager.get_session_status(session_id)
        connected_clients = session_status.get('client_count', 0) if 'error' not in session_status else 0
        streaming_active = stats.get('streaming_active', False)
        events_processed = stats.get('total_events', 0)
        browser_ready = stats.get('browser_ready', False)
        streaming_ready = (streaming_active and events_processed > 0 and (browser_ready or events_processed >= 3))
        last_event_time = stats.get('last_event_time')
        last_event_time = str(last_event_time) if last_event_time else None

        return VisualStreamingStatusResponse(
            success=True,
            session_id=session_id,
            streaming_active=streaming_active,
            streaming_ready=streaming_ready,
            browser_ready=browser_ready,
            events_processed=events_processed,
            events_buffered=stats.get('buffer_size', 0),
            last_event_time=last_event_time,
            connected_clients=connected_clients,
            stream_url=f"/workflows/visual/{session_id}/stream",
            viewer_url=f"/workflows/visual/{session_id}/viewer",
            quality=stats.get('quality', 'standard')
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting visual streaming status for '{original_session_id}': {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@visual_router.get("/{session_id}/viewer")
async def get_visual_streaming_viewer(session_id: str):
    """Get HTML viewer for visual streaming session"""
    try:
        try:
            from backend.visual_streaming import streaming_manager
        except ImportError:
            raise HTTPException(status_code=503, detail="Visual streaming components not available")
        
        streamer = streaming_manager.get_streamer(session_id)
        if not streamer:
            raise HTTPException(status_code=404, detail="Visual streaming session not found")
        
        from fastapi.responses import HTMLResponse
        
        viewer_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Visual Workflow Viewer - {session_id}</title>
            <script src="https://cdn.jsdelivr.net/npm/rrweb@latest/dist/rrweb.min.js"></script>
            <style>
                html, body {{ height: 100%; }}
                body {{ margin: 0; padding: 12px; font-family: Arial, sans-serif; box-sizing: border-box; }}
                #viewer {{ position: relative; width: 100%; height: calc(100vh - 80px); border: 1px solid #ccc; overflow: hidden; background: #fff; }}
                #replayer-root {{ position: absolute; top: 0; left: 0; transform-origin: top left; }}
                #status {{ padding: 10px; background: #f5f5f5; margin-bottom: 10px; }}
                .connected {{ color: green; }}
                .disconnected {{ color: red; }}
            </style>
        </head>
        <body>
            <div id="status">
                <strong>Session:</strong> {session_id} | 
                <strong>Status:</strong> <span id="connection-status" class="disconnected">Connecting...</span> |
                <strong>Events:</strong> <span id="event-count">0</span>
            </div>
            <div id="viewer"><div id="replayer-root"></div></div>
            
            <script>
                const sessionId = '{session_id}';
                const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
                const wsUrl = `${{scheme}}://${{location.host}}/workflows/visual/${{sessionId}}/stream`;
                let replayer = null;
                let eventCount = 0;
                let metaWidth = null;
                let metaHeight = null;
                const viewerEl = document.getElementById('viewer');
                const rootEl = document.getElementById('replayer-root');
                function applyScale() {{
                    if (!metaWidth || !metaHeight) return;
                    const vw = viewerEl.clientWidth;
                    const vh = viewerEl.clientHeight;
                    const scale = Math.min(vw / metaWidth, vh / metaHeight);
                    rootEl.style.width = metaWidth + 'px';
                    rootEl.style.height = metaHeight + 'px';
                    rootEl.style.transform = `scale(${scale})`;
                }}
                window.addEventListener('resize', applyScale);
                
                function initReplayer() {{
                    replayer = new rrweb.Replayer([], {{
                        target: rootEl,
                        mouseTail: false,
                        useVirtualDom: false,
                        liveMode: true,
                        skipInactive: false,
                        speed: 1,
                        blockClass: 'rr-block',
                        ignoreClass: 'rr-ignore',
                        UNSAFE_replayCanvas: true,
                        unpackFn: rrweb.unpack,
                        insertStyleRules: [
                            '.rr-block {{ visibility: hidden !important; }}',
                            '.rr-ignore {{ pointer-events: none !important; }}',
                            'iframe {{ pointer-events: auto !important; }}',
                            '[data-rrweb-id] {{ position: relative !important; }}'
                        ],
                        plugins: [ {{ onBuild: (node) => node }} ]
                    }});
                    replayer.startLive();
                }}
                
                function connect() {{
                    const ws = new WebSocket(wsUrl);
                    ws.onopen = function() {{
                        document.getElementById('connection-status').textContent = 'Connected';
                        document.getElementById('connection-status').className = 'connected';
                        ws.send(JSON.stringify({{type: 'sequence_reset_request'}}));
                    }};
                    ws.onmessage = function(event) {{
                        let data;
                        try {{ data = JSON.parse(event.data); }} catch (e) {{ return; }}
                        let rrwebEvent = data.event ? data.event : (data.type !== undefined ? data : null);
                        if (!rrwebEvent || typeof rrwebEvent.type !== 'number') return;
                        if (rrwebEvent.type === 2 && !replayer) initReplayer();
                        if (rrwebEvent.type === 4) {{
                            // Meta event carries width/height
                            const d = rrwebEvent.data || {{}};
                            if (typeof d.width === 'number' && typeof d.height === 'number') {{
                                metaWidth = d.width; metaHeight = d.height; applyScale();
                            }}
                        }}
                        if (replayer && typeof replayer.addEvent === 'function') {{
                            try {{ replayer.addEvent(rrwebEvent); eventCount++; }} catch (_) {{}}
                        }}
                    }};
                    ws.onclose = function() {{ setTimeout(connect, 3000); }};
                }}
                connect();
            </script>
        </body>
        </html>
        """
        
        return HTMLResponse(content=viewer_html)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving visual streaming viewer: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@visual_router.get("/sessions", response_model=VisualStreamingSessionsResponse)
async def list_visual_streaming_sessions():
    """List all active visual streaming sessions"""
    try:
        try:
            from backend.visual_streaming import streaming_manager
            from backend.websocket_manager import websocket_manager
        except ImportError:
            raise HTTPException(status_code=503, detail="Visual streaming components not available")
        
        all_stats = streaming_manager.get_all_stats()
        sessions = {}
        total_events = 0
        active_count = 0
        
        for session_id, stats in all_stats.get('sessions', {}).items():
            session_status = websocket_manager.get_session_status(session_id)
            connected_clients = session_status.get('client_count', 0) if 'error' not in session_status else 0
            is_active = stats.get('streaming_active', False)
            if is_active:
                active_count += 1
            events_processed = stats.get('total_events', 0)
            total_events += events_processed
            last_event_time = stats.get('last_event_time')
            if last_event_time is not None and last_event_time > 0:
                last_event_time = float(last_event_time)
            else:
                last_event_time = None
            sessions[session_id] = VisualStreamingSessionInfo(
                session_id=session_id,
                streaming_active=is_active,
                events_processed=events_processed,
                events_buffered=stats.get('buffer_size', 0),
                connected_clients=connected_clients,
                created_at=stats.get('created_at', time.time()),
                last_event_time=last_event_time,
                quality=stats.get('quality', 'standard'),
                stream_url=f"/workflows/visual/{session_id}/stream",
                viewer_url=f"/workflows/visual/{session_id}/viewer"
            )
        
        return VisualStreamingSessionsResponse(
            success=True,
            sessions=sessions,
            total_sessions=len(sessions),
            active_sessions=active_count,
            total_events_processed=total_events,
            message=f"Found {len(sessions)} visual streaming sessions ({active_count} active)"
        )
    except Exception as e:
        logger.error(f"Error listing visual streaming sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@visual_router.get("/sessions/enhanced", response_model=EnhancedVisualStreamingSessionsResponse)
async def get_enhanced_visual_streaming_sessions(session_token: str):
    """Get all visual streaming sessions with execution history context"""
    try:
        if not supabase:
            raise HTTPException(status_code=503, detail="Database not configured")
        
        try:
            from backend.visual_streaming import streaming_manager
            from backend.websocket_manager import websocket_manager
        except ImportError:
            raise HTTPException(status_code=503, detail="Visual streaming components not available")
        
        execution_service = get_execution_history_service(supabase)
        all_sessions = streaming_manager.get_all_stats()
        active_executions = execution_service.get_active_executions()
        
        enhanced_sessions = {}
        total_events_processed = 0
        active_sessions = 0
        total_executions_with_streaming = 0
        active_executions_count = 0
        
        for session_id, session_stats in all_sessions.get('sessions', {}).items():
            session_status = websocket_manager.get_session_status(session_id)
            connected_clients = session_status.get('client_count', 0) if 'error' not in session_status else 0
            execution_info = None
            execution_id = None
            for exec_id, exec_data in active_executions.items():
                if exec_data.get("session_id") == session_id:
                    execution_info = exec_data
                    execution_id = exec_id
                    break
            enhanced_sessions[session_id] = {
                'session_id': session_id,
                'streaming_active': session_stats.get('streaming_active', False),
                'events_processed': session_stats.get('total_events', 0),
                'events_buffered': session_stats.get('buffer_size', 0),
                'connected_clients': connected_clients,
                'created_at': session_stats.get('created_at', time.time()),
                'last_event_time': session_stats.get('last_event_time'),
                'workflow_name': execution_info.get('workflow_name') if execution_info else None,
                'workflow_id': execution_info.get('workflow_id') if execution_info else None,
                'execution_id': execution_id,
                'quality': session_stats.get('quality', 'standard'),
                'stream_url': f"/workflows/visual/{session_id}/stream",
                'viewer_url': f"/workflows/visual/{session_id}/viewer",
                'execution_status': execution_info.get('status') if execution_info else None,
                'execution_progress': None,
                'user_id': execution_info.get('user_id') if execution_info else None
            }
            total_events_processed += session_stats.get('total_events', 0)
            if session_stats.get('streaming_active', False):
                active_sessions += 1
            if execution_info and execution_info.get('visual_streaming_enabled'):
                total_executions_with_streaming += 1
            if execution_info and execution_info.get('status') == 'running':
                active_executions_count += 1
        
        from .views import EnhancedVisualStreamingSessionsResponse
        return EnhancedVisualStreamingSessionsResponse(
            success=True,
            sessions=enhanced_sessions,
            total_sessions=len(enhanced_sessions),
            active_sessions=active_sessions,
            total_events_processed=total_events_processed,
            total_executions_with_streaming=total_executions_with_streaming,
            active_executions=active_executions_count,
            completed_executions_today=0,
            message=f"Retrieved {len(enhanced_sessions)} enhanced visual streaming sessions"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting enhanced visual streaming sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


