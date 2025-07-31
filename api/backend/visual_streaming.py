"""
rrweb Event Streaming System - COMPATIBILITY LAYER

This module now serves as a compatibility layer that imports from the new rrweb modules.
The actual implementation has been moved to:
- backend/rrweb/event_streamer.py (RRWebEventStreamer, StreamingPhase, RRWebEvent)
- backend/rrweb/streamers_manager.py (RRWebStreamersManager)

DEPRECATION NOTICE: Direct imports from this module are deprecated.
Please import from the new locations:
  from backend.rrweb.event_streamer import RRWebEventStreamer, StreamingPhase, RRWebEvent
  from backend.rrweb.streamers_manager import rrweb_streamers_manager
"""

import logging
import warnings
from typing import Dict, List, Optional, Set, Any

# Import from new locations
from .rrweb.event_streamer import (
    StreamingPhase,
    RRWebEvent, 
    RRWebEventStreamer
)
from .rrweb.streamers_manager import (
    RRWebStreamersManager,
    rrweb_streamers_manager
)

logger = logging.getLogger(__name__)

# Issue deprecation warning when this module is imported
warnings.warn(
    "backend.visual_streaming is deprecated. "
    "Please import from backend.rrweb.event_streamer and backend.rrweb.streamers_manager instead.",
    DeprecationWarning,
    stacklevel=2
)

# Compatibility alias - maintain the old name for backward compatibility
VisualStreamingManager = RRWebStreamersManager

# Maintain the old global instance name for backward compatibility  
streaming_manager = rrweb_streamers_manager

logger.info("🔄 visual_streaming.py now serves as compatibility layer for new rrweb modules")

# Export the same symbols as before for backward compatibility
__all__ = [
    'StreamingPhase',
    'RRWebEvent',
    'RRWebEventStreamer', 
    'VisualStreamingManager',  # Deprecated alias
    'RRWebStreamersManager',   # New name
    'streaming_manager',        # Deprecated alias
    'rrweb_streamers_manager'  # New name
] 