"""
Enhanced WebSocket Manager for Visual Streaming

This module provides WebSocket connection management specifically designed
for real-time rrweb event streaming and visual workflow feedback.
"""

import asyncio
import json
import logging
import time
from typing import Dict, Set, Optional, Any, List
from fastapi import WebSocket, WebSocketDisconnect
from dataclasses import dataclass
import orjson

from .visual_streaming import streaming_manager, RRWebEventStreamer

logger = logging.getLogger(__name__)


@dataclass
class WebSocketConnection:
    """Represents a WebSocket connection with metadata"""
    websocket: WebSocket
    session_id: str
    client_id: str
    connected_at: float
    last_ping: float = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'client_id': self.client_id,
            'session_id': self.session_id,
            'connected_at': self.connected_at,
            'last_ping': self.last_ping,
            'connection_duration': time.time() - self.connected_at
        }


class VisualWebSocketManager:
    """Enhanced WebSocket management for visual streaming"""
    
    def __init__(self):
        # Connection tracking
        self.connections: Dict[str, WebSocketConnection] = {}  # client_id -> connection
        self.session_connections: Dict[str, Set[str]] = {}  # session_id -> set of client_ids
        
        # Health monitoring
        self.ping_interval = 30  # seconds
        self.connection_timeout = 60  # seconds
        
        # Statistics
        self.stats = {
            'total_connections': 0,
            'active_connections': 0,
            'total_sessions': 0,
            'messages_sent': 0,
            'messages_failed': 0,
            'bytes_sent': 0
        }
        
        # Background task tracking
        self._background_tasks_started = False
    
    async def handle_client_connection(self, websocket: WebSocket, session_id: str) -> str:
        """Handle new client connection for visual streaming"""
        # Start background tasks if not already started
        if not self._background_tasks_started:
            try:
                asyncio.create_task(self._health_check_loop())
                asyncio.create_task(self._stats_update_loop())
                self._background_tasks_started = True
            except RuntimeError:
                # No event loop running, will start later
                pass
        
        # Generate unique client ID
        client_id = f"{session_id}_{int(time.time() * 1000)}"
        
        try:
            # Accept WebSocket connection
            await websocket.accept()
            
            # Create connection object
            connection = WebSocketConnection(
                websocket=websocket,
                session_id=session_id,
                client_id=client_id,
                connected_at=time.time()
            )
            
            # Register connection
            self.connections[client_id] = connection
            
            # Add to session tracking
            if session_id not in self.session_connections:
                self.session_connections[session_id] = set()
            self.session_connections[session_id].add(client_id)
            
            # Register with streaming manager
            streamer = streaming_manager.get_or_create_streamer(session_id)
            await streamer.add_client(websocket)
            await streamer.start_streaming()
            
            # Update statistics
            self.stats['total_connections'] += 1
            self.stats['active_connections'] = len(self.connections)
            self.stats['total_sessions'] = len(self.session_connections)
            
            logger.info(f"Client {client_id} connected to session {session_id}")
            
            # Send connection confirmation
            await self._send_control_message(websocket, {
                'type': 'connection_established',
                'client_id': client_id,
                'session_id': session_id,
                'timestamp': time.time()
            })
            
            return client_id
            
        except Exception as e:
            logger.error(f"Error handling client connection: {e}")
            raise
    
    async def handle_client_disconnection(self, client_id: str) -> bool:
        """Handle client disconnection"""
        if client_id not in self.connections:
            return False
        
        try:
            connection = self.connections[client_id]
            session_id = connection.session_id
            
            # Remove from connections
            del self.connections[client_id]
            
            # Remove from session tracking
            if session_id in self.session_connections:
                self.session_connections[session_id].discard(client_id)
                
                # If no more clients for this session, clean up
                if not self.session_connections[session_id]:
                    del self.session_connections[session_id]
                    
                    # Remove from streaming manager if no clients
                    streamer = streaming_manager.get_streamer(session_id)
                    if streamer:
                        await streamer.remove_client(connection.websocket)
            
            # Update statistics
            self.stats['active_connections'] = len(self.connections)
            self.stats['total_sessions'] = len(self.session_connections)
            
            logger.info(f"Client {client_id} disconnected from session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error handling client disconnection: {e}")
            return False
    
    async def broadcast_to_session(self, session_id: str, message: Dict[str, Any]) -> int:
        """Broadcast message to all clients in a session"""
        if session_id not in self.session_connections:
            return 0
        
        client_ids = list(self.session_connections[session_id])
        successful_sends = 0
        failed_clients = []
        
        message_bytes = orjson.dumps(message)
        
        for client_id in client_ids:
            if client_id in self.connections:
                try:
                    connection = self.connections[client_id]
                    await connection.websocket.send_bytes(message_bytes)
                    successful_sends += 1
                    
                    # Update statistics
                    self.stats['messages_sent'] += 1
                    self.stats['bytes_sent'] += len(message_bytes)
                    
                except Exception as e:
                    logger.warning(f"Failed to send message to client {client_id}: {e}")
                    failed_clients.append(client_id)
                    self.stats['messages_failed'] += 1
        
        # Clean up failed connections
        for client_id in failed_clients:
            await self.handle_client_disconnection(client_id)
        
        return successful_sends
    
    async def send_to_client(self, client_id: str, message: Dict[str, Any]) -> bool:
        """Send message to specific client"""
        if client_id not in self.connections:
            return False
        
        try:
            connection = self.connections[client_id]
            message_bytes = orjson.dumps(message)
            
            await connection.websocket.send_bytes(message_bytes)
            
            # Update statistics
            self.stats['messages_sent'] += 1
            self.stats['bytes_sent'] += len(message_bytes)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send message to client {client_id}: {e}")
            self.stats['messages_failed'] += 1
            await self.handle_client_disconnection(client_id)
            return False
    
    async def _send_control_message(self, websocket: WebSocket, message: Dict[str, Any]) -> bool:
        """Send control message to WebSocket"""
        try:
            message_bytes = orjson.dumps(message)
            await websocket.send_bytes(message_bytes)
            return True
        except Exception as e:
            logger.error(f"Failed to send control message: {e}")
            return False
    
    async def handle_websocket_loop(self, websocket: WebSocket, client_id: str) -> None:
        """Main WebSocket message handling loop"""
        try:
            while True:
                # Wait for message from client
                try:
                    data = await websocket.receive_text()
                    message = json.loads(data)
                    
                    # Handle different message types
                    await self._handle_client_message(client_id, message)
                    
                except WebSocketDisconnect:
                    logger.info(f"Client {client_id} disconnected")
                    break
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from client {client_id}")
                    continue
                except Exception as e:
                    logger.error(f"Error in WebSocket loop for client {client_id}: {e}")
                    break
        
        finally:
            await self.handle_client_disconnection(client_id)
    
    async def _handle_client_message(self, client_id: str, message: Dict[str, Any]) -> None:
        """Handle incoming message from client"""
        message_type = message.get('type')
        
        if message_type == 'ping':
            # Update last ping time
            if client_id in self.connections:
                self.connections[client_id].last_ping = time.time()
            
            # Send pong response
            await self.send_to_client(client_id, {
                'type': 'pong',
                'timestamp': time.time()
            })
        
        elif message_type == 'get_status':
            # Send status information
            await self.send_to_client(client_id, {
                'type': 'status',
                'data': self.get_connection_status(client_id)
            })

        elif message_type == 'sequence_reset_request':
            # Per-client sequence reset with optional small history replay
            try:
                history_window_seconds = float(message.get('history_window_seconds', 3.0))
            except Exception:
                history_window_seconds = 3.0

            if client_id in self.connections:
                connection = self.connections[client_id]
                session_id = connection.session_id
                streamer = streaming_manager.get_streamer(session_id)
                if streamer and hasattr(streamer, 'mark_sequence_reset_for_client'):
                    try:
                        streamer.mark_sequence_reset_for_client(connection.websocket, history_window_seconds=history_window_seconds)
                    except Exception as e:
                        logger.debug(f"Failed to mark sequence reset state: {e}")

                # Attempt to force a fresh FullSnapshot from recorder (best-effort)
                try:
                    from workflow_use.browser.browser_factory import browser_factory
                    recorder = await browser_factory.get_recorder_for_session(session_id)
                    if recorder and hasattr(recorder, 'force_full_snapshot'):
                        _ = await recorder.force_full_snapshot()
                except Exception as e:
                    logger.debug(f"force_full_snapshot attempt failed or unavailable: {e}")

                # Acknowledge to client
                await self.send_to_client(client_id, {
                    'type': 'sequence_reset_ack',
                    'session_id': session_id,
                    'history_window_seconds': history_window_seconds
                })
        
        else:
            logger.warning(f"Unknown message type from client {client_id}: {message_type}")
    
    async def _health_check_loop(self) -> None:
        """Background health check for connections"""
        while True:
            try:
                current_time = time.time()
                stale_connections = []
                
                for client_id, connection in self.connections.items():
                    # Check for stale connections
                    if (connection.last_ping > 0 and 
                        current_time - connection.last_ping > self.connection_timeout):
                        stale_connections.append(client_id)
                
                # Clean up stale connections
                for client_id in stale_connections:
                    logger.info(f"Removing stale connection: {client_id}")
                    await self.handle_client_disconnection(client_id)
                
                await asyncio.sleep(self.ping_interval)
                
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(10)
    
    async def _stats_update_loop(self) -> None:
        """Background statistics update loop"""
        while True:
            try:
                # Update real-time statistics
                self.stats['active_connections'] = len(self.connections)
                self.stats['total_sessions'] = len(self.session_connections)
                
                await asyncio.sleep(10)  # Update every 10 seconds
                
            except Exception as e:
                logger.error(f"Error in stats update loop: {e}")
                await asyncio.sleep(30)
    
    def get_connection_status(self, client_id: str) -> Dict[str, Any]:
        """Get status for specific connection"""
        if client_id not in self.connections:
            return {'error': 'Connection not found'}
        
        connection = self.connections[client_id]
        return connection.to_dict()
    
    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Get status for all connections in a session"""
        if session_id not in self.session_connections:
            return {'error': 'Session not found'}
        
        client_ids = self.session_connections[session_id]
        connections = [
            self.connections[client_id].to_dict()
            for client_id in client_ids
            if client_id in self.connections
        ]
        
        return {
            'session_id': session_id,
            'client_count': len(connections),
            'connections': connections
        }
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics"""
        return {
            'websocket_stats': self.stats,
            'streaming_stats': streaming_manager.get_all_stats(),
            'active_sessions': list(self.session_connections.keys()),
            'connection_count_by_session': {
                session_id: len(client_ids)
                for session_id, client_ids in self.session_connections.items()
            }
        }


# Global WebSocket manager instance
websocket_manager = VisualWebSocketManager() 