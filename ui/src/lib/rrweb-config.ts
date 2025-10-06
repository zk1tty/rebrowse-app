/**
 * 🎬 RRWeb Configuration - Centralized Settings for Visual Streaming
 * 
 * - WorkflowVisualizer settings (API, reconnection, buffering)
 * - RRWeb Replayer settings (the only config actually used)
 * 
 * ⚠️ IMPORTANT: Changes to RRWeb settings can significantly impact:
 * - Media playback stability (AbortError prevention)
 * - DOM reconstruction accuracy 
 * - Performance and memory usage
 * - Live streaming smoothness
 */

import { createCssProtectionPlugin, createCssErrorHandler, patchRRWebCssProcessing } from './rrwebCssProtection';

/**
 * 🔧 WorkflowVisualizer Configuration
 * Core settings for the WorkflowVisualizer class behavior
 */
export const WORKFLOW_VISUALIZER_CONFIG = {
  // API settings
  apiBase: '',                       // Base API path (empty for relative URLs)
  
  // Connection reliability (simplified - no auto-reconnect complexity)
  autoReconnect: false,              // Simplified - no auto-reconnect
  reconnectInterval: 3000,           // 3 seconds between reconnection attempts
  maxReconnectAttempts: 3,           // Maximum reconnection attempts
  
  // Streaming settings
  bufferSize: 1000,                  // Event buffer size (larger for better performance)
  quality: 'standard',               // Default quality setting
} as const;

/**
 * 🧪 MINIMAL TEST CONFIG - Exactly matches official RRWeb test
 * Use this for debugging animation issues - only essential settings
 */
export const RRWEB_MINIMAL_TEST_CONFIG = {
  liveMode: true,                    // ✅ ONLY setting from official test
  pauseAnimation: false,             // ✅ Critical for animations
  speed: 1,                          // ✅ Normal speed
} as const;

/**
 * 🎭 RRWeb Configuration - SINGLE SOURCE OF TRUTH
 * All settings passed directly to RRWeb Replayer constructor
 * ✅ UPDATED: Matches fix strategy for sandbox issue resolution + CSS overflow protection
 */
export const RRWEB_CONFIG = {
  // 🔴 CORE STREAMING SETTINGS
  liveMode: true,                    // ✅ Required for live streaming - prevents finish events
  UNSAFE_replayCanvas: true,         // ✅ Required for canvas content replay
  useVirtualDom: false,              // ✅ CRITICAL: Prevent sandbox issues
  
  // 🚨 CSS PROTECTION: Prevent CSS regex overflow errors (Amazon Prime Video fix)
  dataURLOptions: {
    type: 'base64',                  // ✅ Use base64 encoding for large CSS to avoid regex issues
    quality: 0.6                     // ✅ Reduce quality for large images to prevent memory issues
  },
  
  // 🔧 ERROR HANDLING (Enhanced for CSS processing errors)
  onError: createCssErrorHandler(),
  
  // 🛠️ PLUGINS: Enhanced CSS protection system
  plugins: [createCssProtectionPlugin()],
  
  // 🎯 DOM RECONSTRUCTION SETTINGS (Must match backend recording config)
  blockClass: 'rr-block',            // ✅ Block elements with this class (including media elements)
  ignoreClass: 'rr-ignore',          // ✅ Ignore elements with this class  
  maskTextClass: 'rr-mask',          // ✅ Mask text in elements with this class
  
  // 🎨 RENDERING SETTINGS (Must match backend recording config)
  recordCanvas: true,                // ✅ CRITICAL: Must match backend setting
  collectFonts: false,               // ✅ CRITICAL: Must match backend setting
  
  // 🎵 MEDIA STABILITY SETTINGS (Prevents AbortError crashes)
  pauseAnimation: false,             // ✅ Don't pause animations - keep them running in live mode
  skipInactive: false,               // ✅ CRITICAL: Don't skip animation frames (per backend requirements)
  inactivePeriodThreshold: 60000,
  triggerFocus: false,               // ✅ Avoid focus events that trigger media play/pause
  
  // 🎬 ANIMATION OPTIMIZATION (Keeps animations smooth during live streaming)
  mouseTail: false,                  // ✅ Disable mouse tail to reduce animation conflicts
  
  // 🎥 SIMPLIFIED MEDIA HANDLING - Only target media elements, leave animations alone
  insertStyleRules: [
    // Disable ONLY media elements - don't touch other animations
    'video, audio { pointer-events: none !important; autoplay: false !important; opacity: 0.1 !important; }',
    'video[autoplay], audio[autoplay] { autoplay: false !important; }', 
    // Hide problematic media iframes
    'iframe[src*="youtube"], iframe[src*="vimeo"], [data-testid*="video"] { opacity: 0.1 !important; pointer-events: none !important; }',
    // 🎨 CSS OVERFLOW PROTECTION: Hide elements that commonly cause CSS regex issues
    'style[data-emotion], style[data-styled], [class*="emotion-"], [class*="styled-"] { display: none !important; }',
    // Simplify complex CSS-in-JS generated content
    '[style*="data:image/svg+xml"] { background-image: none !important; }'
  ],
  
  // ⚡ PERFORMANCE SETTINGS
  speed: 1,                          // ✅ Normal playback speed for live streaming
  loadTimeout: 10000,                // ✅ 10s timeout for media elements to load
  showWarning: false                 // ✅ Suppress warnings to reduce console noise
} as const;

/**
 * 🏗️ Helper function to get complete replayer config
 * Combines container with RRWeb settings
 * ✅ UPDATED: Includes runtime unpackFn setup and target override
 */
export const getRRWebReplayerConfig = (container: HTMLElement, useMinimalConfig = false, rrwebInstance?: any) => {
  if (useMinimalConfig) {
    // 🧪 MINIMAL TEST MODE - Only essential settings to test animations
    console.log('🧪 [Config] Using MINIMAL test config for animation testing');
    return {
      target: container,  // ✅ Use 'target' instead of 'root' (matches fix strategy)
      ...RRWEB_MINIMAL_TEST_CONFIG
    };
  }  
  // Create config with runtime values
  const config: any = {
    target: container,  // ✅ Use 'target' instead of 'root' (matches fix strategy)
    ...RRWEB_CONFIG
  };
  
  // ✅ Set unpackFn at runtime if rrweb instance is available
  if (rrwebInstance?.unpack) {
    config.unpackFn = rrwebInstance.unpack;
  } else {
    console.log('⚠️ [Config] No rrweb.unpack available - will use default unpacking');
  }
  
  return config;
};

/**
 * 🔧 Helper function to get WorkflowVisualizer config with optional overrides
 * Allows customization while maintaining centralized defaults
 */
export const getWorkflowVisualizerConfig = (overrides: Partial<typeof WORKFLOW_VISUALIZER_CONFIG> = {}) => ({
  ...WORKFLOW_VISUALIZER_CONFIG,
  ...overrides
});

// Re-export CSS protection functions for backward compatibility
export { patchRRWebCssProcessing }; 