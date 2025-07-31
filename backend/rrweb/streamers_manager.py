#!/usr/bin/env python3
"""
RRWeb Streamers Manager: Multi-session orchestration and lifecycle management

This module contains the manager class extracted from backend/visual_streaming.py:
- RRWebStreamersManager: Manages multiple RRWebEventStreamer instances

Key responsibilities:
- Create and manage multiple RRWebEventStreamer instances (one per session)
- Session lifecycle management
- Cleanup of inactive sessions
- Global session statistics aggregation

What it DOESN'T do:
- Browser management
- rrweb injection
- Direct event capture from browser
- WebSocket client management (delegated to individual streamers)
"""

import asyncio
import logging
import time
from typing import Dict, Optional, Any

# Import the event streamer class
from .event_streamer import RRWebEventStreamer

logger = logging.getLogger(__name__)


class RRWebStreamersManager:
    """
    Multi-session orchestration and lifecycle management
    
    This class manages multiple RRWebEventStreamer instances for different sessions.
    Each session gets its own dedicated streamer instance.
    """
    
    def __init__(self):
        """Initialize the streamers manager"""
        self.streamers: Dict[str, RRWebEventStreamer] = {}
        self.cleanup_interval = 300  # 5 minutes
        self._cleanup_task_started = False
        logger.info("RRWebStreamersManager initialized")
    
    def get_or_create_streamer(self, session_id: str) -> RRWebEventStreamer:
        """
        Get existing streamer or create new one
        
        Args:
            session_id: Session identifier
            
        Returns:
            RRWebEventStreamer instance for the session
        """
        # Start cleanup task if not already started
        if not self._cleanup_task_started:
            try:
                asyncio.create_task(self._cleanup_inactive_sessions())
                self._cleanup_task_started = True
                logger.info("Started background cleanup task")
            except RuntimeError:
                # No event loop running, will start later
                logger.debug("No event loop running, cleanup task will start later")
                pass
        
        if session_id not in self.streamers:
            self.streamers[session_id] = RRWebEventStreamer(session_id)
            logger.info(f"Created new streamer for session {session_id}")
        else:
            logger.debug(f"Returning existing streamer for session {session_id}")
        
        return self.streamers[session_id]
    
    def get_streamer(self, session_id: str) -> Optional[RRWebEventStreamer]:
        """
        Get existing streamer
        
        Args:
            session_id: Session identifier
            
        Returns:
            RRWebEventStreamer instance or None if not found
        """
        return self.streamers.get(session_id)
    
    async def remove_streamer(self, session_id: str) -> bool:
        """
        Remove and cleanup streamer
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if streamer was removed, False if not found
        """
        if session_id in self.streamers:
            streamer = self.streamers[session_id]
            
            # Gracefully shutdown the streamer
            try:
                await streamer.graceful_shutdown()
                logger.info(f"Gracefully shutdown streamer for session {session_id}")
            except Exception as e:
                logger.warning(f"Error during graceful shutdown for session {session_id}: {e}")
                # Fallback to regular stop
                await streamer.stop_streaming()
            
            # Remove from manager
            del self.streamers[session_id]
            logger.info(f"Removed streamer for session {session_id}")
            return True
        else:
            logger.debug(f"No streamer found for session {session_id}")
            return False
    
    def get_all_stats(self) -> Dict[str, Any]:
        """
        Get statistics for all active streamers
        
        Returns:
            Dictionary with session statistics
        """
        return {
            'total_sessions': len(self.streamers),
            'active_sessions': list(self.streamers.keys()),
            'cleanup_interval': self.cleanup_interval,
            'cleanup_task_started': self._cleanup_task_started,
            'sessions': {
                session_id: streamer.get_stats()
                for session_id, streamer in self.streamers.items()
            }
        }
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """
        Get summary statistics across all sessions
        
        Returns:
            Aggregated statistics summary
        """
        total_events = 0
        total_clients = 0
        active_streamers = 0
        ready_streamers = 0
        
        for streamer in self.streamers.values():
            stats = streamer.get_stats()
            total_events += stats.get('total_events', 0)
            total_clients += stats.get('connected_clients', 0)
            
            if stats.get('streaming_active', False):
                active_streamers += 1
            
            if stats.get('truly_ready', False):
                ready_streamers += 1
        
        return {
            'total_sessions': len(self.streamers),
            'active_streamers': active_streamers,
            'ready_streamers': ready_streamers,
            'total_events': total_events,
            'total_clients': total_clients,
            'cleanup_interval': self.cleanup_interval
        }
    
    async def cleanup_all_sessions(self) -> int:
        """
        Clean up all active sessions
        
        Returns:
            Number of sessions cleaned up
        """
        session_ids = list(self.streamers.keys())
        cleaned_count = 0
        
        for session_id in session_ids:
            try:
                success = await self.remove_streamer(session_id)
                if success:
                    cleaned_count += 1
            except Exception as e:
                logger.error(f"Error cleaning up session {session_id}: {e}")
        
        logger.info(f"Cleaned up {cleaned_count} of {len(session_ids)} sessions")
        return cleaned_count
    
    async def _cleanup_inactive_sessions(self) -> None:
        """Periodically cleanup inactive sessions"""
        logger.info("Starting background cleanup task")
        
        while True:
            try:
                current_time = time.time()
                inactive_sessions = []
                
                for session_id, streamer in self.streamers.items():
                    # Check if session should be cleaned up
                    should_cleanup = False
                    
                    # No connected clients and no recent activity
                    if (len(streamer.connected_clients) == 0 and 
                        current_time - streamer.stats['last_event_time'] > self.cleanup_interval):
                        should_cleanup = True
                        logger.debug(f"Session {session_id} marked for cleanup: no clients and no recent activity")
                    
                    # Streaming not active for extended period
                    elif (not streamer.streaming_active and 
                          current_time - streamer.stats.get('last_event_time', 0) > self.cleanup_interval * 2):
                        should_cleanup = True
                        logger.debug(f"Session {session_id} marked for cleanup: streaming inactive")
                    
                    if should_cleanup:
                        inactive_sessions.append(session_id)
                
                # Cleanup inactive sessions
                cleaned_count = 0
                for session_id in inactive_sessions:
                    try:
                        success = await self.remove_streamer(session_id)
                        if success:
                            cleaned_count += 1
                    except Exception as e:
                        logger.error(f"Error cleaning up inactive session {session_id}: {e}")
                
                if cleaned_count > 0:
                    logger.info(f"Cleaned up {cleaned_count} inactive sessions")
                
                # Wait before next cleanup cycle
                await asyncio.sleep(self.cleanup_interval)
                
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
                await asyncio.sleep(60)  # Wait before retrying
    
    def get_session_count(self) -> int:
        """Get total number of active sessions"""
        return len(self.streamers)
    
    def list_session_ids(self) -> list[str]:
        """Get list of all active session IDs"""
        return list(self.streamers.keys())
    
    async def broadcast_to_all_sessions(self, message: Dict[str, Any]) -> int:
        """
        Broadcast a message to all active sessions
        
        Args:
            message: Message to broadcast
            
        Returns:
            Number of sessions that received the message
        """
        successful_broadcasts = 0
        
        for session_id, streamer in self.streamers.items():
            try:
                # Create a fake RRWebEvent for broadcasting with FIXED format
                from .event_streamer import RRWebEvent
                
                broadcast_event = RRWebEvent(
                    session_id=session_id,
                    timestamp=time.time(),
                    event=message,  # FIXED: Use 'event' field consistently
                    sequence_id=0
                    # REMOVED: event_type (redundant)
                    # REMOVED: phase (workflow metadata)
                )
                
                clients_reached = await streamer.broadcast_event(broadcast_event)
                if clients_reached > 0:
                    successful_broadcasts += 1
                    
            except Exception as e:
                logger.error(f"Error broadcasting to session {session_id}: {e}")
        
        logger.info(f"Broadcasted message to {successful_broadcasts} sessions")
        return successful_broadcasts


# Global streamers manager instance
# This replaces the global streaming_manager from visual_streaming.py
rrweb_streamers_manager = RRWebStreamersManager()

logger.info("Global rrweb_streamers_manager instance created")
