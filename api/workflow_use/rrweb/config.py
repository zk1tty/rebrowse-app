"""
rrweb Recording Configuration

Centralized configuration for rrweb visual recording and streaming.
This file contains all the settings for recording options, batching,
and performance optimization.
"""

from typing import Dict, Any

# 🎯 STEP 3: Simplified CDN loading (from official tests pattern)
SIMPLE_CDN_URL = "https://cdn.jsdelivr.net/npm/rrweb@latest/dist/rrweb.min.js"

# rrweb Recording Options (fixed for navigation event capture)
ESSENTIAL_OPTIONS = {
    # 🎯 PERFORMANCE NOTE: Animated elements (like screensavers) will generate 
    # many mutation events as expected. To reduce events for animated elements:
    # 1. Use "ignoreClass": "rr-ignore" on animated containers
    # 2. Use "blockClass": "rr-block" to completely block recording  
    # 3. Consider custom hooks to filter specific element IDs
    # Current config: ~300 events from screensaver animation is normal behavior

    # 🎯 OFFICIAL CORE OPTIONS (from rrweb guide)
    "packFn": "rrweb.pack",              # Enable compression
    
    # 🎯 OFFICIAL PRIVACY OPTIONS
    "blockClass": "rr-block",
    "ignoreClass": "rr-ignore", 
    "maskTextClass": "rr-mask",
    "maskAllInputs": False,              # Official default: false
    
    # 🎯 CRITICAL CSP BYPASS OPTIONS FOR COMPLEX SPAS
    "inlineStylesheet": True,            # CRITICAL - fixes CSS serialization in iframe
    "collectFonts": True,                # Inline fonts to prevent CORS/CSP issues
    "inlineImages": True,                # Inline images to prevent CORS/CSP issues
    
    # 🎯 ENHANCED FOR COMPLEX SPAS (Amazon, Netflix, etc.)
    "recordCrossOriginIframes": True,    # Complex sites use many iframes
    "slimDOMOptions": {                  # MINIMAL filtering for complex SPAs
        "comment": True,                 # Remove comments only
        "headFavicon": True,             # Remove favicons only
        # KEEP ALL META TAGS: Essential for SPA routing and state management
        # KEEP ALL SCRIPTS: Essential for proper DOM reconstruction
        # KEEP ALL STYLES: Essential for visual accuracy
    },
    
    # 🎯 CRITICAL FIX: Navigation Event Capture
    "recordCanvas": True,                # Capture canvas elements (streaming sites use these)
    # REMOVED: recordAfter setting - this was preventing navigation FullSnapshots!
    
    # 🎯 ENHANCED NAVIGATION TRACKING
    "recordNetwork": True,              # Track network requests (critical for SPAs)
    "recordLog": True,                  # Track console logs for debugging
    
    # 🎯 SPA-SPECIFIC OPTIMIZATIONS (CONSERVATIVE)
    "mousemove": False,                  # Reduce noise events
    "mouseInteraction": {               # Capture essential interactions only
        "MouseUp": False,
        "MouseDown": False,
        "Click": True,                   # Essential for SPA interactions
        "ContextMenu": False,
        "DblClick": True,                # May trigger SPA navigation
        "Focus": True,                   # Important for form interactions
        "Blur": True,                    # Important for form interactions
        "TouchStart": False,
        "TouchMove": False,
        "TouchEnd": False
    },
    
    # 🎯 CONTENT SECURITY IMPROVEMENTS
    "dataURLOptions": {                 # Handle data URLs properly
        "type": "base64",
        "quality": 0.8                   # Higher quality for better reproduction
    },
    
    # 🎯 ENHANCED ERROR HANDLING
    "errorHandler": True,               # Let rrweb handle errors gracefully
    "plugins": [],                      # No plugins for maximum compatibility
    
    # 🎯 CONSERVATIVE TIMING TO PREVENT EVENT STORMS
    "sampling": {
        "scroll": 250,                  # Reduce scroll event frequency (more conservative)
        "mousemove": 100,               # Reduce mousemove frequency (if enabled)
        "mouseInteraction": 50,         # Reduce interaction sampling (more conservative)
        "input": 100                    # Reduce input event frequency (more conservative)
    }
}

def get_recording_options_js() -> str:
    """Generate simplified JavaScript object for essential rrweb options"""
    options = ESSENTIAL_OPTIONS.copy()
    
    # Convert Python boolean to JavaScript
    def py_to_js(obj):
        if isinstance(obj, bool):
            return "true" if obj else "false"
        elif isinstance(obj, dict):
            items = [f'"{k}": {py_to_js(v)}' for k, v in obj.items()]
            return "{" + ", ".join(items) + "}"
        elif isinstance(obj, str):
            return f'"{obj}"'
        else:
            return str(obj)
    
    # Build the JavaScript object
    js_options = []
    for key, value in options.items():
        if key == "packFn":
            js_options.append(f"{key}: {value}")  # Don't quote function name
        else:
            js_options.append(f"{key}: {py_to_js(value)}")
    
    return "{" + ", ".join(js_options) + "}"

def get_cdn_url() -> str:
    """Get simplified CDN URL (Step 3: no fallback complexity)"""
    return SIMPLE_CDN_URL

__all__ = [
    'SIMPLE_CDN_URL',
    'ESSENTIAL_OPTIONS', 
    'get_recording_options_js',
    'get_cdn_url'
] 