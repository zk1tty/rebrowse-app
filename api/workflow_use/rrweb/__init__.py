"""
RRWeb Browser-Side Module

This module contains browser-side rrweb functionality:
- RRWebRecorder: rrweb injection and event capture
- config: rrweb configuration and settings
"""

# Main classes that will be available for import
from .recorder import RRWebRecorder
from .config import get_recording_options_js, get_cdn_url

__version__ = "1.0.0"
__all__ = ["RRWebRecorder", "get_recording_options_js", "get_cdn_url"]
