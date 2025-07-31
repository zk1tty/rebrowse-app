"""
RRWeb Backend-Side Module

This module contains backend-side rrweb functionality:
- RRWebEventStreamer: Per-session event streaming and WebSocket management
- RRWebStreamersManager: Multi-session orchestration and lifecycle management
- StreamingPhase: Enum for streaming phase management
- RRWebEvent: Structured rrweb event dataclass
"""

# Main classes that will be available for import
from .event_streamer import RRWebEventStreamer, StreamingPhase, RRWebEvent
from .streamers_manager import RRWebStreamersManager, rrweb_streamers_manager

__version__ = "1.0.0"
__all__ = [
    "RRWebEventStreamer", 
    "RRWebStreamersManager", 
    "rrweb_streamers_manager",
    "StreamingPhase", 
    "RRWebEvent"
]
