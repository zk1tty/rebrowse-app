import { API_ENDPOINTS } from '@/lib/constants';
import { getRRWebReplayerConfig, WORKFLOW_VISUALIZER_CONFIG } from '@/lib/rrweb-config';
import { patchRRWebCssProcessing } from '@/lib/rrwebCssProtection';

// Simple RRWeb event type (no complex viewport management)
type RRWebEvent = any;

// ✅ BACKEND EVENT STRUCTURE: Match exact backend format
// Backend sends exactly: {"session_id": "abc123", "timestamp": 1234567890, "event": {...}, "sequence_id": 0}
interface RRWebEventMessage {
  session_id: string;
  timestamp: number;
  event: RRWebEvent;
  sequence_id: number;
}

// 📋 VALIDATION CONSTANTS: For structure validation
const REQUIRED_BACKEND_FIELDS = ['session_id', 'timestamp', 'event', 'sequence_id'] as const;
const REQUIRED_RRWEB_EVENT_FIELDS = ['type', 'timestamp'] as const;

interface WorkflowVisualizerConfig {
  apiBase: string;
  autoReconnect: boolean;
  reconnectInterval: number;
  maxReconnectAttempts: number;
  bufferSize: number;
  quality: string;
}

interface WorkflowVisualizerCallbacks {
  onConnect: (sessionId: string) => void;
  onDisconnect: (event: CloseEvent) => void;
  onEvent: (data: any) => void;
  onError: (error: Error) => void;
}

interface WorkflowVisualizerState {
  isConnected: boolean;
  sessionId: string | null;
  websocket: WebSocket | null;
  replayer: any;
}

interface WorkflowVisualizerStats {
  eventsReceived: number;
  bytesReceived: number;
  startTime: number | null;
}

export class WorkflowVisualizer {
  private config: WorkflowVisualizerConfig;
  private state: WorkflowVisualizerState;
  private callbacks: WorkflowVisualizerCallbacks;
  private stats: WorkflowVisualizerStats;
  private playerContainer: HTMLElement | null = null;
  private rrwebCode: string | null = null; // Cached rrweb source code
  private rrwebCSS: string | null = null; // Cached rrweb CSS

  // Step 4: Simplified constructor - official rrweb stream pattern
  constructor(options: Partial<WorkflowVisualizerCallbacks> = {}) {
    // Use centralized configuration from rrweb-config.ts
    this.config = { ...WORKFLOW_VISUALIZER_CONFIG };
    
    this.state = {
      isConnected: false,
      sessionId: null,
      websocket: null,
      replayer: null
    };
    
    this.callbacks = {
      onConnect: options.onConnect || (() => {}),
      onDisconnect: options.onDisconnect || (() => {}),
      onEvent: options.onEvent || (() => {}),
      onError: options.onError || (() => {})
    };
    
    this.stats = {
      eventsReceived: 0,
      bytesReceived: 0,
      startTime: null
    };
  }



  async startWorkflow(workflowName: string, inputs: any = {}, options: any = {}): Promise<any> {
    try {
      // Remove verbose logging - keep only essential info
      const requestBody = {
        inputs: inputs,
        session_token: options.sessionToken,
        mode: options.mode || 'cloud-run',
        visual: true,
        visual_streaming: true,
        visual_quality: options.quality || this.config.quality,
        visual_events_buffer: options.bufferSize || this.config.bufferSize
      };

      const response = await fetch(API_ENDPOINTS.EXECUTE_WORKFLOW(workflowName), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody)
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      const sessionId = result.session_id || result.task_id;

      if (!sessionId) {
        throw new Error('No session ID received from server');
      }

      // Connect to WebSocket stream
      await this.connectToStream(sessionId);

    } catch (error) {
      console.error('❌ [WorkflowVisualizer] Failed to start workflow:', error);
      throw error;
    }
  }

  async connectToStream(sessionId: string): Promise<void> {
    const wsUrl = API_ENDPOINTS.VISUAL_STREAM_WS(sessionId);
    
    this.state.websocket = new WebSocket(wsUrl);
    this.state.isConnected = false;

    this.state.websocket.onopen = () => {
      this.state.isConnected = true;
      this.callbacks.onConnect(sessionId);
    };

    this.state.websocket.onmessage = (event) => {
      this.handleMessage(event);
    };

    this.state.websocket.onclose = (event) => {
      this.state.isConnected = false;
      // Only log if it's not a clean close
      if (!event.wasClean) {
        console.warn('⚠️ [WorkflowVisualizer] WebSocket closed unexpectedly:', event.code);
      }
      this.callbacks.onDisconnect(event);
    };

    this.state.websocket.onerror = (error) => {
      console.error('❌ [WorkflowVisualizer] WebSocket error:', error);
      this.callbacks.onError(new Error('WebSocket connection failed'));
    };
  }

  async initializePlayer(iframe: HTMLIFrameElement): Promise<void> {
    if (!iframe) {
      console.error('❌ [WorkflowVisualizer] Invalid iframe provided to initializePlayer');
      throw new Error('Invalid iframe provided to initializePlayer');
    }
    
    // Reset duplicate event tracking for new session
    this.lastEventTimestamp = 0;
    this.duplicateEventCount = 0;
    
    // 🔄 Clear cached rrweb code to ensure we fetch the correct version
    this.rrwebCode = null;
    this.rrwebCSS = null;
    
    this.playerContainer = iframe;
    
    try {
      // Step 1: Main Context Fetch - official RRWeb pattern
      await this.fetchRRWebCode();
      
      // Step 2: Re-fetch iframe reference in case React re-rendered during async operation
      const currentIframe = (window as any).debugIframeRef;
      
      if (!currentIframe) {
        console.error('❌ [WorkflowVisualizer] Iframe reference lost during async operation');
        throw new Error('Iframe reference lost during async operation');
      }
      
      // Use the current iframe reference
      this.playerContainer = currentIframe;
      
      // Step 3: Wait for replayer to be fully created before resolving
      await this.injectRRWebIntoIframe(currentIframe);
      
    } catch (error) {
      console.error('❌ [WorkflowVisualizer] Failed to initialize player:', error);
      this.callbacks.onError(error as Error);
      throw error;
    }
  }

  // Step 2: Simplified message handling - official rrweb stream pattern
  private async handleMessage(event: MessageEvent): Promise<void> {
    try {
      let data: any;
      
      // Handle both text and binary data formats
      if (event.data instanceof Blob) {
        // Convert Blob to text first, then parse as JSON
        const text = await event.data.text();
        data = JSON.parse(text);
      } else if (typeof event.data === 'string') {
        // Direct JSON parsing for text data
        data = JSON.parse(event.data);
      } else {
        throw new Error('Unsupported message data type');
      }
      
      // ✅ Backend EVENT VALIDATION: Validate exact rrweb structure, or ws message structure
      if (this.isRRWebEventMessage(data)) {
        // Validate event sequence
        this.validateEventSequence(data.sequence_id);
        
        // Update statistics
        this.stats.eventsReceived++;
        this.stats.bytesReceived += JSON.stringify(data).length;
        
        // Process the validated rrweb event
        const rrwebEvent = data.event;
        if (rrwebEvent && typeof rrwebEvent.type === 'number') {
          try {
            this.addEventDirectly(rrwebEvent);
          } catch (replayError) {
            console.warn('⚠️ [WorkflowVisualizer] RRWeb replay error (continuing):', replayError);
          }
        } else {
          console.warn('⚠️ [WorkflowVisualizer] Invalid rrweb event format');
        }
      } else if (data.type === 'connection_established') {
        // Handle WebSocket connection establishment
        this.handleConnectionEstablished(data);
      } else if (data.type === 'error') {
        this.handleBackendError(data);
      } else if (data.type === 'status') {
        this.handleBackendStatus(data);
      } else {
        // Log unknown message structure for debugging
        this.logStructureValidation(data);
      }
      
      this.callbacks.onEvent(data);
      
    } catch (error) {
      console.error('❌ [WorkflowVisualizer] Failed to handle message:', error);
      this.handleMessageError(error as Error, event.data);
    }
  }

  // 🔗 CONNECTION ESTABLISHMENT: Handle WebSocket connection confirmation
  private handleConnectionEstablished(data: any): void {
    const { client_id, session_id, timestamp } = data;
    
    console.debug('🔗 [WorkflowVisualizer] WebSocket connection established - \nClient ID:', client_id, '\nSession ID:', session_id, '\nTimestamp:', new Date(timestamp * 1000).toISOString());
    
    // Update session ID if not already set
    if (!this.state.sessionId && session_id) {
      this.state.sessionId = session_id;
    }
    
    // Start statistics tracking
    if (!this.stats.startTime) {
      this.stats.startTime = Date.now();
    }
    
    // Notify that connection is ready for events
    this.callbacks.onEvent({
      type: 'connection_ready',
      sessionId: session_id,
      clientId: client_id
    });
  }

  // 🚨 BACKEND ERROR HANDLING: Handle new backend error types
  private handleBackendError(data: any): void {
    const errorType = data.error_type || 'unknown';
    const errorMessage = data.error || data.message || 'Unknown backend error';
    
    console.error('❌ [Backend Error]', errorType + ':', errorMessage);
    this.callbacks.onError(new Error(`Backend Error (${errorType}): ${errorMessage}`));
  }

  // 📊 BACKEND STATUS HANDLING: Handle new backend status messages
  private handleBackendStatus(data: any): void {
    // Only log critical status changes
    const statusType = data.type;
    const status = data.status || data.success;
    
    if (statusType === 'recording_status' && !status) {
      console.warn('⚠️ [Backend] Recording stopped unexpectedly');
    }
    
    this.callbacks.onEvent(data);
  }

  // 🔧 ERROR RECOVERY: Enhanced error recovery mechanisms
  private handleMessageError(error: Error, messageData: any): void {
    const errorMessage = error.message || 'Unknown error';
    
    // Categorize error types for appropriate recovery
    if (errorMessage.includes('JSON')) {
      console.error('📋 [Parse Error] Invalid JSON in message');
      console.log('🔧 [Recovery] Attempting to skip malformed message');
      
    } else if (errorMessage.includes('sequence')) {
      console.error('🔢 [Sequence Error] Event sequence problem');
      console.log('🔧 [Recovery] Requesting sequence reset');
      this.requestSequenceReset();
      
    } else if (errorMessage.includes('timeout')) {
      console.error('⏱️ [Timeout Error] Message processing timeout');
      console.log('🔧 [Recovery] Adjusting timeout settings');
      
    } else {
      console.error('❓ [Unknown Error] Unhandled message error');
    }
    
    // Always notify the error callback
    this.callbacks.onError(error);
  }

  // 🔄 SEQUENCE RESET: Request sequence reset from backend
  private requestSequenceReset(): void {
    if (this.state.websocket && this.state.websocket.readyState === WebSocket.OPEN) {
      const resetRequest = {
        type: 'sequence_reset_request',
        session_id: this.state.sessionId,
        timestamp: Date.now()
      };
      
      console.log('🔄 [Sequence Reset] Requesting sequence reset from backend');
      this.state.websocket.send(JSON.stringify(resetRequest));
      
      // Reset local sequence tracking
      this.expectedSequenceId = 0;
      this.sequenceErrors = 0;
    }
  }

  // Step 4: Simplified statistics - official rrweb stream pattern
  getStatistics(): any {
    const duration = this.stats.startTime ? (Date.now() - this.stats.startTime) / 1000 : 0;
    
    return {
      totalEvents: this.stats.eventsReceived,
      eventsPerSecond: duration > 0 ? Math.round(this.stats.eventsReceived / duration) : 0,
      eventsReceived: this.stats.eventsReceived,
      bytesReceived: this.stats.bytesReceived
    };
  }

  getConnectionState(): { isConnected: boolean; sessionId: string | null } {
    return {
      isConnected: this.state.isConnected,
      sessionId: this.state.sessionId
    };
  }

  // Step 4: Simplified disconnect - official rrweb stream pattern
  disconnect(): void {
    this.state.isConnected = false;
    
    if (this.state.websocket) {
      this.state.websocket.close();
      this.state.websocket = null;
    }
    
    this.state.replayer = null;
    
    // Reset duplicate event tracking
    this.lastEventTimestamp = 0;
    this.duplicateEventCount = 0;
    console.log('🔄 [WorkflowVisualizer] Reset event tracking on disconnect');
  }



  // Official rrweb live mode pattern - simple event addition with duplicate filtering
  private lastEventTimestamp: number = 0;
  private duplicateEventCount: number = 0;
  
  // 🔧 ADDED: Animation event tracking
  private animationEventCount: number = 0;
  private totalEventCount: number = 0;
  
  private addEventDirectly(event: any): void {
    // 🔧 FIX: Only process events AFTER startLive() has been called
    if (this.state.replayer && !(this.state.replayer as any).__startLiveCalled) {
      if (event.type === 2 && typeof this.state.replayer.startLive === 'function') {

        this.state.replayer.startLive();
        (this.state.replayer as any).__startLiveCalled = true;
        
        // Continue to process this full snapshot event below
      } else {
        // Skip ALL events until we get the full snapshot - don't add to replayer
        console.log('⏭️ [WorkflowVisualizer] Skipping event before full snapshot:', { type: event.type });
        return; // Exit completely - don't process this event
      }
    }

    // Only reach here if startLive() has been called
    console.debug('🎯 [WorkflowVisualizer] Adding event to live replayer:', JSON.stringify({ 
      type: event.type, 
      timestamp: event.timestamp,
      hasData: !!event.data,
      dataKeys: event.data ? Object.keys(event.data) : []
    }));
    
    // Use event directly - CSS protection is handled by patchRRWebCssProcessing
    let protectedEvent = event;
    
    // 🔧 ADDED: Animation event debugging (per backend requirements)
    this.debugAnimationEvents(protectedEvent);
    
    // 🔧 ADDED: Track event counts for diagnostics
    this.totalEventCount++;
    if (protectedEvent.type === 3 && protectedEvent.data?.source === 0) {
      this.animationEventCount++;
    }

    // Skip duplicate events
    if (protectedEvent.timestamp && protectedEvent.timestamp === this.lastEventTimestamp) {
      this.duplicateEventCount++;
      if (this.duplicateEventCount > 5) {
        console.warn('⚠️ [WorkflowVisualizer] Multiple duplicate events detected');
      }
      return;
    }
    this.lastEventTimestamp = protectedEvent.timestamp || 0;

    // Add event directly - CSS protection is handled by patchRRWebCssProcessing
    try {
      if (this.state.replayer && typeof this.state.replayer.addEvent === 'function') {
        this.state.replayer.addEvent(protectedEvent);
      } else {
        console.warn('⚠️ [WorkflowVisualizer] Replayer not ready for events');
      }
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      
      // CSS errors are handled by patchRRWebCssProcessing
      if (errorMsg.includes('Regular expression too large') || 
          errorMsg.includes('adaptCssForReplay') ||
          errorMsg.includes('Invalid regular expression') ||
          errorMsg.includes('Pattern too large') ||
          errorMsg.includes('Regex overflow') ||
          errorMsg.includes('SyntaxError: Invalid regular expression')) {
        return; // Skip this event - protection already applied
      }
      
      console.warn('⚠️ [WorkflowVisualizer] Event processing error (continuing):', error);
    }

    // Update statistics
    this.stats.eventsReceived++;
    this.stats.bytesReceived += JSON.stringify(protectedEvent).length;
  }



  // 🔧 ADDED: Animation event debugging method (per backend requirements)
  private debugAnimationEvents(rrwebEvent: any): void {
    if (rrwebEvent.type === 3) {  // IncrementalSnapshot
      const source = rrwebEvent.data?.source;
      if (source === 0) {  // Mutation events (animations)
        console.debug('🎬 Animation event received:', JSON.stringify({
          type: rrwebEvent.type,
          source: source,
          mutations: rrwebEvent.data?.mutations?.length || 0,
          timestamp: rrwebEvent.timestamp
        }));
        
        // More detailed mutation logging
        if (rrwebEvent.data?.mutations?.length > 0) {
          console.debug('🎬 Animation mutation:', JSON.stringify({
            mutations: rrwebEvent.data.mutations.length,
            types: rrwebEvent.data.mutations.map((m: any) => m.type).slice(0, 5) // First 5 mutation types
          }));
        }
      } else {
        // Log all incremental events to see what we're getting
        console.debug('🔍 Incremental event (source=' + source + '):', JSON.stringify({
          type: rrwebEvent.type,
          source: source,
          dataKeys: Object.keys(rrwebEvent.data || {}),
          timestamp: rrwebEvent.timestamp
        }));
      }
    }
  }

  // 🔢 SEQUENCE VALIDATION: Support for backend sequence IDs
  private expectedSequenceId: number = 0;
  private sequenceErrors: number = 0;
  
  private validateEventSequence(sequenceId: number): void {
    if (sequenceId !== this.expectedSequenceId) {
      this.sequenceErrors++;
      if (this.sequenceErrors > 5) {
        console.error('❌ [Sequence] Too many sequence errors - event ordering may be corrupted');
        this.callbacks.onError(new Error('Event sequence corruption detected'));
      }
    }
    this.expectedSequenceId = sequenceId + 1;
  }

  // ✅ BACKEND EVENT VALIDATION: Type guard for backend event structure
  private isRRWebEventMessage(data: any): data is RRWebEventMessage {
    // Validate exact backend structure: {session_id, timestamp, event, sequence_id}
    const isValid = (
      typeof data === 'object' &&
      data !== null &&
      typeof data.session_id === 'string' &&
      typeof data.timestamp === 'number' &&
      typeof data.sequence_id === 'number' &&
      data.event !== undefined &&
      typeof data.event === 'object'
    );
    
    if (isValid) {
      // Additional validation for rrweb event structure
      const hasRRWebEventStructure = (
        typeof data.event.type === 'number' &&
        typeof data.event.timestamp === 'number'
      );
      
      if (!hasRRWebEventStructure) {
        console.warn('⚠️ [Event Validation] Valid backend structure but invalid rrweb event format');
        console.log('🔍 [Event Keys]:', Object.keys(data.event || {}));
        return false;
      }
    }
    
    return isValid;
  }

  // 📋 STRUCTURE VALIDATION: Log unknown message structures for debugging
  private logStructureValidation(data: any): void {
    console.warn('⚠️ [Event Validation] Unknown message structure received');
    console.log('🔍 [Message Type]:', typeof data);
    console.log('🔍 [Message Keys]:', data && typeof data === 'object' ? Object.keys(data) : 'N/A');
    console.log('🔍 [Message Data]:', data);
  }



  // 🔧 ADDED: Replayer reinitialize method (per backend requirements)
  private reinitializeReplayer(): void {
    try {
      console.log('🔄 [WorkflowVisualizer] Starting replayer reinitialization...');
      
      // Clear current replayer
      this.state.replayer = null;
      
      // Reset startLive flag
      const iframe = this.playerContainer as HTMLIFrameElement;
      if (iframe && iframe.contentDocument) {
        // Try to reinitialize by calling createRRWebReplayer again
        this.createRRWebReplayer(iframe).then(() => {
          console.log('✅ [WorkflowVisualizer] Replayer reinitialized successfully');
        }).catch((error) => {
          console.error('❌ [WorkflowVisualizer] Failed to reinitialize replayer:', error);
        });
      } else {
        console.error('❌ [WorkflowVisualizer] Cannot reinitialize - iframe not available');
      }
    } catch (error) {
      console.error('❌ [WorkflowVisualizer] Error during replayer reinitialization:', error);
    }
  }

  // Setup RRWeb event listeners for debugging and monitoring
  private setupReplayerEventListeners(): void {
    if (!this.state.replayer) {
      console.error('❌ [WorkflowVisualizer] Cannot setup event listeners - no replayer instance');
      return;
    }

    // Critical events for debugging insertBefore errors
    this.state.replayer.on('fullsnapshot-rebuilded', (event: any) => {
      console.debug('📸 [RRWeb Event] Full snapshot rebuilded:', {
        timestamp: event.timestamp,
        type: event.type
      });
      
      // 🔍 DEBUG: Log what page is actually being recorded
      try {
        const iframe = this.playerContainer as HTMLIFrameElement;
        const iframeDoc = iframe?.contentDocument;
        if (iframeDoc) {
          const pageTitle = iframeDoc.title;
          const pageUrl = (iframe.contentWindow as any)?.location?.href;
          console.log('🌐 [Recorded Page]:', { title: pageTitle, url: pageUrl });
          
          // Quick element count to see if it's a real page or minimal content
          const elementCount = iframeDoc.querySelectorAll('*').length;
          console.log('📊 [DOM Size]:', elementCount, 'elements');
          
          // if (elementCount < 20) {
          //   console.warn('⚠️ [MINIMAL CONTENT] Very few elements detected - may not be capturing intended page');
          // }
        }
      } catch (error) {
        console.warn('Could not analyze recorded page:', error);
      }
      
      // 🔍 DEBUG: Check for animations after DOM reconstruction
      setTimeout(() => {
        try {
          const iframe = this.playerContainer as HTMLIFrameElement;
          const iframeDoc = iframe?.contentDocument;
          if (iframeDoc) {            
            // Check for ALL types of animations
            const allElements = iframeDoc.querySelectorAll('*');
            let animatedElements = 0;
            let globeElements = 0;
            let canvasElements = 0;
            let videoElements = 0;
            let svgElements = 0;
            let transformElements = 0;
            const elementTypes = new Map();
            
            allElements.forEach((el: Element) => {
              // Count element types
              const tagName = el.tagName.toLowerCase();
              elementTypes.set(tagName, (elementTypes.get(tagName) || 0) + 1);
              
              const computedStyle = (iframe.contentWindow as any)?.getComputedStyle(el);
              if (computedStyle) {
                const animationName = computedStyle.animationName;
                const animationPlayState = computedStyle.animationPlayState;
                const transform = computedStyle.transform;
                
                // CSS Animations
                if (animationName && animationName !== 'none') {
                  animatedElements++;
                  console.log('🎭 [CSS Animation] Found:', {
                    tagName: el.tagName,
                    className: el.className,
                    animationName,
                    animationPlayState,
                  });
                }
                
                // CSS Transforms (could be animated via JS)
                if (transform && transform !== 'none') {
                  transformElements++;
                  console.log('🔄 [Transform] Found:', {
                    tagName: el.tagName,
                    className: el.className,
                    transform: transform.substring(0, 50) + '...'
                  });
                }
                
                // Canvas elements (common for screensavers)
                if (tagName === 'canvas') {
                  canvasElements++;
                  console.log('🎨 [Canvas] Found:', {
                    width: (el as HTMLCanvasElement).width,
                    height: (el as HTMLCanvasElement).height,
                    className: el.className,
                    id: el.id
                  });
                }
                
                // Video elements
                if (tagName === 'video') {
                  videoElements++;
                  console.log('🎥 [Video] Found:', {
                    src: (el as HTMLVideoElement).src,
                    autoplay: (el as HTMLVideoElement).autoplay,
                    className: el.className
                  });
                }
                
                // SVG elements
                if (tagName === 'svg' || el.namespaceURI === 'http://www.w3.org/2000/svg') {
                  svgElements++;
                  console.log('🖼️ [SVG] Found:', {
                    tagName: el.tagName,
                    className: el.className,
                    viewBox: el.getAttribute('viewBox')
                  });
                }
                
                // Look for screensaver/globe-related elements (broader search)
                const className = (el.className || '').toString().toLowerCase();
                const id = (el.id || '').toLowerCase();
                
                if (className.includes('screen') || className.includes('saver') || 
                    className.includes('globe') || className.includes('spin') || 
                    className.includes('rotate') || className.includes('orbit') ||
                    id.includes('screen') || id.includes('globe') ||
                    tagName === 'canvas') {
                  globeElements++;
                  console.log('🌍 [Screensaver Element] Found:', {
                    tagName: el.tagName,
                    className: el.className,
                    id: el.id,
                    animationName,
                    transform: transform !== 'none' ? transform.substring(0, 30) + '...' : 'none'
                  });
                }
              }
            });
                        
            // 🔍 DEBUG: Show page content to understand what's being recorded
            const bodyElement = iframeDoc.body;
            const htmlContent = bodyElement ? bodyElement.innerHTML.substring(0, 500) : 'No body found';
            console.debug('📄 [Page Content Sample]:', htmlContent);
            
            const pageTitle = iframeDoc.title || 'No title';
            const pageUrl = (iframe.contentWindow as any)?.location?.href || 'No URL';
            console.debug('📋 [Page Info]:', { title: pageTitle, url: pageUrl });
            
            console.debug('🎬 [Animation Summary]:', {
              totalElements: allElements.length,
              cssAnimatedElements: animatedElements,
              transformElements,
              canvasElements,
              videoElements, 
              svgElements,
              screensaverElements: globeElements
            });
            
            // TODO: What is this 
            // 🚨 CRITICAL: If no screensaver content, this is a recording issue!
            if (globeElements === 0 && allElements.length < 20) {
              console.warn('🚨 [RECORDING ISSUE] Screensaver content missing from recorded events!');
            }
          }
        } catch (error) {
          console.warn('⚠️ [Animation DEBUG] Could not analyze animations:', error);
        }
      }, 100);
    });

    this.state.replayer.on('event-cast', (event: any) => {
      console.debug('🎬 [RRWeb Event] Event cast:', {
        type: event.type,
        timestamp: event.timestamp
      });
      
      // 🔧 ENHANCED: Track animation events in cast listener (per backend requirements)
      if (event.type === 3 && event.data?.source === 0) {
        console.debug('🎬 Animation event cast:', JSON.stringify({
          source: event.data.source,
          mutations: event.data.mutations?.length || 0
        }));
      }
    });

    // CSS loading events (could relate to DOM timing issues)
    this.state.replayer.on('load-stylesheet-start', () => {
      console.log('🎨 [RRWeb Event] Started loading stylesheets');
    });

    this.state.replayer.on('load-stylesheet-end', () => {
      console.log('🎨 [RRWeb Event] Finished loading stylesheets');
    });

    // State tracking events
    this.state.replayer.on('start', () => {
      console.log('▶️ [RRWeb Event] Replayer started');
    });

    this.state.replayer.on('pause', () => {
      console.log('⏸️ [RRWeb Event] Replayer paused');
    });

    this.state.replayer.on('finish', () => {
      console.log('🏁 [RRWeb Event] Replayer finished');
    });

    // Viewport changes in iframe
    this.state.replayer.on('resize', (payload: any) => {
      console.log('📐 [RRWeb Event] Viewport resized:', payload);
    });

    // Error-related events
    this.state.replayer.on('skip-start', (payload: any) => {
      console.log('⏭️ [RRWeb Event] Started skipping inactive time:', payload);
    });

    this.state.replayer.on('skip-end', (payload: any) => {
      console.log('⏭️ [RRWeb Event] Finished skipping inactive time:', payload);
    });
  }

  // Step 1: Main Context Fetch - Official RRWeb Pattern (Puppeteer approach)
  private async fetchRRWebCode(): Promise<void> {
    // If already cached, no need to fetch again
    if (this.rrwebCode && this.rrwebCSS) {
      console.log('✅ [WorkflowVisualizer] Using cached rrweb code and CSS');
      return;
    }
    try {
      // Try jsdelivr.net first (best CORS support) - using specific version 2.0.0-alpha.14
      try {
        const [jsResponse, cssResponse] = await Promise.all([
          fetch('https://cdn.jsdelivr.net/npm/rrweb@2.0.0-alpha.14/dist/rrweb.js'),
          fetch('https://cdn.jsdelivr.net/npm/rrweb@2.0.0-alpha.14/dist/rrweb.css')
        ]);
        
        if (!jsResponse.ok || !cssResponse.ok) {
          throw new Error(`CDN fetch failed: JS ${jsResponse.status}, CSS ${cssResponse.status}`);
        }

        this.rrwebCode = await jsResponse.text();
        this.rrwebCSS = await cssResponse.text();
          
      } catch {
        console.warn('⚠️ [WorkflowVisualizer] jsdelivr.net failed, trying unpkg.com fallback...');
        
        // Fallback to unpkg.com with same specific version
        const [jsResponse, cssResponse] = await Promise.all([
          fetch('https://unpkg.com/rrweb@2.0.0-alpha.14/dist/rrweb.js'),
          fetch('https://unpkg.com/rrweb@2.0.0-alpha.14/dist/rrweb.css')
        ]);
        
        if (!jsResponse.ok || !cssResponse.ok) {
          throw new Error(`Fallback CDN fetch failed: JS ${jsResponse.status}, CSS ${cssResponse.status}`);
        }

        this.rrwebCode = await jsResponse.text();
        this.rrwebCSS = await cssResponse.text();
        
        console.log(`✅ [WorkflowVisualizer] unpkg.com rrweb@2.0.0-alpha.14 fallback used (JS: ${Math.round(this.rrwebCode.length / 1024)} KB, CSS: ${Math.round(this.rrwebCSS.length / 1024)} KB)`);
      }
      
    } catch (error) {
      const errorMessage = `Failed to fetch rrweb from all CDNs: ${error}`;
      console.error('❌ [WorkflowVisualizer]', errorMessage);
      throw new Error(errorMessage);
    }

    // Validate fetched code
    if (!this.rrwebCode || this.rrwebCode.length < 1000) {
      throw new Error('Fetched rrweb code appears to be invalid or too small');
    }

    // Check if it contains expected rrweb signatures
    if (!this.rrwebCode.includes('rrweb') || !this.rrwebCode.includes('Replayer')) {
      throw new Error('Fetched code does not appear to be valid rrweb library');
    }

    // Validate CSS
    if (!this.rrwebCSS || this.rrwebCSS.length < 100) {
      throw new Error('Fetched rrweb CSS appears to be invalid or too small');
    }
  }

  // STEP 2: Wait for DOM attachment FIRST, then contentWindow
  private async waitForIframeWindow(iframe: HTMLIFrameElement): Promise<Window | null> {
    return new Promise((resolve, reject) => {
      let attempts = 0;
      const maxAttempts = 200; // 4 seconds at 20ms intervals
      
      const timeout = setTimeout(() => {
        reject(new Error(`Iframe not ready after ${attempts} attempts`));
      }, 4000);

      const checkDomAndWindow = () => {
        attempts++;
        const inDOM = document.contains(iframe);
        
        if (inDOM) {
          const contentWindow = iframe.contentWindow;
          if (contentWindow) {
            console.log(`✅ [WorkflowVisualizer] Iframe ready (attempt ${attempts})`);
            clearTimeout(timeout);
            resolve(contentWindow);
            return;
          }
        }

        if (attempts < maxAttempts) {
          setTimeout(checkDomAndWindow, 20);
        }
      };

      // Also try load event
      iframe.addEventListener('load', () => {
        if (document.contains(iframe)) {
          const contentWindow = iframe.contentWindow;
          if (contentWindow) {
            clearTimeout(timeout);
            resolve(contentWindow);
          }
        }
      }, { once: true });

      setTimeout(checkDomAndWindow, 50);
    });
  }

    private async injectRRWebIntoIframe(iframe: HTMLIFrameElement): Promise<void> {
    try {      
      // Wait for iframe window to be available
      let iframeWindow = await this.waitForIframeWindow(iframe);
      
      // STEP 4: Forced iframe initialization if normal method fails
      if (!iframeWindow) {
        console.log('🔍 [Step 4] Attempting forced iframe initialization...');
        
        // Try different src values
        const originalSrc = iframe.src;
        console.log('  - Original src:', originalSrc);
        
        // Try data URL
        iframe.src = 'data:text/html,<!DOCTYPE html><html><head></head><body></body></html>';
        await new Promise(resolve => setTimeout(resolve, 200));
        console.log('  - After data URL, contentWindow:', iframe.contentWindow);
        
        if (!iframe.contentWindow) {
          // Try javascript: URL
          iframe.src = 'javascript:void(0)';
          await new Promise(resolve => setTimeout(resolve, 200));
          console.log('  - After javascript URL, contentWindow:', iframe.contentWindow);
        }
        
        if (!iframe.contentWindow) {
          // Try removing and re-adding to DOM
          const parent = iframe.parentElement;
          if (parent) {
            console.log('  - Trying DOM re-attachment...');
            parent.removeChild(iframe);
            await new Promise(resolve => setTimeout(resolve, 50));
            iframe.src = 'about:blank';
            parent.appendChild(iframe);
            await new Promise(resolve => setTimeout(resolve, 200));
            console.log('  - After DOM re-attachment, contentWindow:', iframe.contentWindow);
          }
        }
        
        iframeWindow = iframe.contentWindow;
        if (!iframeWindow) {
          throw new Error('All iframe initialization methods failed');
        }
        
        console.log('✅ [Step 4] Forced initialization successful!');
      }

      console.log('🚀 [WorkflowVisualizer] Injecting RRWeb into iframe...');

      // Step 2: Puppeteer Pattern - Execute injection code INSIDE iframe context
      if (!this.rrwebCode || !this.rrwebCSS) {
        throw new Error('RRWeb code and CSS not available - fetchRRWebCode must be called first');
      }
      
      // Official Puppeteer pattern adapted for browser - execute INSIDE iframe
      const injectionScript = `
        (function(rrwebCode, rrwebCSS) {          
          // Add global media error handling inside iframe context
          
          // Override console.error to catch RRWeb media errors
          const originalConsoleError = console.error;
          console.error = function(...args) {
            const errorMsg = args.join(' ');
            if (errorMsg.includes('media playback error') || 
                errorMsg.includes('AbortError') ||
                errorMsg.includes('play() request was interrupted')) {
              console.warn('🎵 [IframeContext] Caught media error in iframe:', errorMsg);
              return; // Don't log the error
            }
            // Log other errors normally
            originalConsoleError.apply(console, args);
          };
          
          // Global error handler for unhandled errors in iframe
          window.addEventListener('error', function(event) {
            if (event.message && (
              event.message.includes('AbortError') ||
              event.message.includes('media playback error') ||
              event.message.includes('play() request was interrupted')
            )) {
              console.warn('🎵 [IframeContext] Caught global media error:', event.message);
              event.preventDefault();
              event.stopPropagation();
              return false;
            }
          });
          
          // Promise rejection handler for media errors
          window.addEventListener('unhandledrejection', function(event) {
            if (event.reason && typeof event.reason === 'object') {
              const errorMsg = event.reason.message || String(event.reason);
              if (errorMsg.includes('AbortError') || 
                  errorMsg.includes('media playback error') ||
                  errorMsg.includes('play() request was interrupted')) {
                console.warn('🎵 [IframeContext] Caught unhandled media promise rejection:', errorMsg);
                event.preventDefault();
                return false;
              }
            }
          });
                    
          // Helper to protect a single media element (defined first for reuse)
          function protectSingleMediaElement(element) {
            const originalPlay = element.play;
            const originalPause = element.pause;
            let playPromise = null;
            let isPlaying = false;
            
            element.play = function() {
              try {
                if (isPlaying || playPromise) {
                  console.log('🎵 [IframeContext] Skipping redundant play() on media element');
                  return Promise.resolve();
                }
                
                isPlaying = true;
                playPromise = originalPlay.call(this);
                
                if (playPromise && typeof playPromise.then === 'function') {
                  return playPromise.then(() => {
                    playPromise = null;
                    return;
                  }).catch((error) => {
                    playPromise = null;
                    isPlaying = false;
                    if (error.name === 'AbortError' || error.message.includes('interrupted')) {
                      console.warn('🎵 [IframeContext] Media play() aborted - handled gracefully');
                      return Promise.resolve();
                    }
                    throw error;
                  });
                }
                
                return playPromise || Promise.resolve();
              } catch (error) {
                isPlaying = false;
                playPromise = null;
                if (error.name === 'AbortError' || error.message.includes('interrupted')) {
                  console.warn('🎵 [IframeContext] Media play() error handled:', error.message);
                  return Promise.resolve();
                }
                throw error;
              }
            };
            
            element.pause = function() {
              try {
                if (playPromise) {
                  playPromise.then(() => {
                    originalPause.call(this);
                    isPlaying = false;
                  }).catch(() => {
                    isPlaying = false;
                  });
                } else {
                  originalPause.call(this);
                  isPlaying = false;
                }
              } catch (error) {
                console.warn('🎵 [IframeContext] Media pause() error handled:', error.message);
                isPlaying = false;
              }
            };
          }
          
          // Additional protection: Override media element methods to prevent rapid play/pause cycles
          function protectMediaElements() {
            const originalCreateElement = document.createElement;
            document.createElement = function(tagName) {
              const element = originalCreateElement.call(document, tagName);
              
                             // Protect video and audio elements from rapid play/pause cycles
               if (tagName.toLowerCase() === 'video' || tagName.toLowerCase() === 'audio') {
                 protectSingleMediaElement(element);
               }
              
              return element;
            };
          }
           
           // Protect existing media elements in the DOM
           function protectExistingMediaElements() {
             const mediaElements = document.querySelectorAll('video, audio');
             mediaElements.forEach(protectSingleMediaElement);
           }
           
           // Watch for dynamically added media elements (during RRWeb reconstruction)
           function setupMediaObserver() {
             const observer = new MutationObserver((mutations) => {
               mutations.forEach((mutation) => {
                 mutation.addedNodes.forEach((node) => {
                   if (node.nodeType === 1) { // Element node
                     const element = node;
                     // Check if it's a media element
                     if (element.tagName === 'VIDEO' || element.tagName === 'AUDIO') {
                       protectSingleMediaElement(element);
                     }
                     // Check for media elements within added element
                     const mediaChildren = element.querySelectorAll && element.querySelectorAll('video, audio');
                     if (mediaChildren && mediaChildren.length > 0) {
                       mediaChildren.forEach(protectSingleMediaElement);
                     }
                   }
                 });
               });
             });
             
             observer.observe(document.body || document.documentElement, {
               childList: true,
               subtree: true
             });             
           }
           
           
           // Apply media protection after DOM is ready
           if (document.readyState === 'loading') {
             document.addEventListener('DOMContentLoaded', () => {
               protectMediaElements();
               protectExistingMediaElements();
               setupMediaObserver();
             });
           } else {
             protectMediaElements();
             protectExistingMediaElements();
             setupMediaObserver();
           }
          
          function loadCSS(cssCode) {            
            // Official RRWeb CSS injection pattern
            const styleEl = document.createElement('style');
            styleEl.type = 'text/css';
            styleEl.innerHTML = cssCode;
            
            if (document.head) {
              document.head.appendChild(styleEl);
            } else {
              // Fallback for timing issues
              requestAnimationFrame(() => {
                if (document.head) {
                  document.head.appendChild(styleEl);
                } else {
                  document.documentElement.appendChild(styleEl);
                }
              });
            }
            
            return styleEl;
          }
          
          function loadScript(code) {
            const s = document.createElement('script');
            s.type = 'text/javascript';
            s.innerHTML = code;
            
            if (document.head) {
              document.head.append(s);
            } else {
              // Puppeteer's requestAnimationFrame fallback for timing
              requestAnimationFrame(() => {
                if (document.head) {
                  document.head.append(s);
                } else {
                  document.documentElement.appendChild(s);
                }
              });
            }
          }
          
          // Load CSS first, then JavaScript
          loadCSS(rrwebCSS);
          loadScript(rrwebCode);
          
          // Return success indicator
          return 'css_and_js_injection_started';
        })(${JSON.stringify(this.rrwebCode)}, ${JSON.stringify(this.rrwebCSS)});
      `;

      // Execute injection script inside iframe context (Puppeteer pattern)
      (iframeWindow as any).eval(injectionScript);
      
      // Small delay to allow script execution to complete
      await new Promise(resolve => setTimeout(resolve, 100));
      
      // Check if rrweb is now available
      if ((iframeWindow as any).rrweb) {
        console.log('✅ [WorkflowVisualizer] RRWeb loaded into iframe successfully');
        await this.createRRWebReplayer(iframe);
      } else {
        throw new Error('RRWeb injection failed - rrweb not available');
      }
      
    } catch (error) {
      console.error('❌ [WorkflowVisualizer] Failed to inject rrweb using Puppeteer pattern:', error);
      this.callbacks.onError(error as Error);
    }
  }

  private async createRRWebReplayer(iframe: HTMLIFrameElement): Promise<void> {
    try {
      const iframeWindow = iframe.contentWindow;
      const iframeDoc = iframe.contentDocument;
      
      console.debug('🎬 [WorkflowVisualizer] Creating replayer...');
      
      if (!iframeWindow || !(iframeWindow as any).rrweb) {
        throw new Error('rrweb not available in iframe');
      }

      // Create simple container for rrweb (official pattern)
      const replayerContainer = iframeDoc?.createElement('div');
      if (replayerContainer && iframeDoc && iframeDoc.body) {
        replayerContainer.id = 'rrweb-replayer-container';
        replayerContainer.style.cssText = 'width: 100%; height: 100%; position: absolute; top: 0; left: 0;';
        iframeDoc.body.appendChild(replayerContainer);
      } else {
        throw new Error('Cannot create replayer container - iframe document or body not available');
      }

      // ✅ UPDATED: Use fix strategy configuration with proper rrweb instance
      const useMinimalConfig = false; // Use full config with sandbox fixes
      const rrwebInstance = (iframeWindow as any).rrweb;
      const replayerConfig = getRRWebReplayerConfig(replayerContainer, useMinimalConfig, rrwebInstance);
      
      this.state.replayer = new rrwebInstance.Replayer([], replayerConfig);

      // Add flag to track if startLive() has been called (for our fix)
      (this.state.replayer as any).__startLiveCalled = false;

      // 🚨 CRITICAL: Patch rrweb's internal CSS processing to prevent regex overflow
      patchRRWebCssProcessing(this.state.replayer, iframeWindow);
      console.log('✅ [CSS Protection] rrweb internal CSS processing patched');
      
      // Detect actual loaded version
      const versionCheck = (iframeWindow as any).eval(`
        (function() {
          try {
            const lib = window.rrweb;
            
            // Try multiple approaches to find version information
            let detectedVersion = 'unknown';
            
            // Method 1: Check if there's a version property
            if (lib.version) {
              detectedVersion = lib.version;
            } 
            // Method 2: Look in the source code with more flexible patterns
            else {
              const codeStr = lib.toString();
              
              // Try various patterns (more flexible)
              const patterns = [
                /2\\.0\\.0-alpha\\.\\d+/g,           // Direct version pattern
                /alpha\\.\\d+/g,                      // Just alpha.XX
                /"2\\.0\\.0[^"]*"/g,                 // Quoted version
                /'2\\.0\\.0[^']*'/g,                 // Single quoted version
                /version[:\\s="']*2\\.0\\.0[^"'\\s]*/gi, // Version key
                /\\d+\\.\\d+\\.\\d+-alpha\\.\\d+/g   // Generic semver with alpha
              ];
              
              for (const pattern of patterns) {
                const matches = codeStr.match(pattern);
                if (matches && matches.length > 0) {
                  detectedVersion = matches[0].replace(/['"]/g, ''); // Remove quotes
                  break;
                }
              }
              
              // Method 3: Check for specific alpha.14 indicators
              if (detectedVersion === 'unknown') {
                if (codeStr.includes('alpha.14') || codeStr.includes('alpha-14')) {
                  detectedVersion = '2.0.0-alpha.14';
                } else if (codeStr.includes('alpha.')) {
                  const alphaMatch = codeStr.match(/alpha\\.(\\d+)/);
                  if (alphaMatch) {
                    detectedVersion = '2.0.0-alpha.' + alphaMatch[1];
                  }
                }
              }
            }
            
            // Check capabilities
            const hasLiveMode = lib.Replayer && typeof lib.Replayer.prototype.startLive === 'function';
            const hasFinishEvent = lib.Replayer && typeof lib.Replayer.prototype.on === 'function';
            
            // Get all live-related methods
            const liveMethods = lib.Replayer ? 
              Object.getOwnPropertyNames(lib.Replayer.prototype).filter(m => 
                m.toLowerCase().includes('live') || 
                m.toLowerCase().includes('finish')
              ) : [];
            
            // Method 4: If still unknown, try to estimate from capabilities
            if (detectedVersion === 'unknown' && hasLiveMode) {
              detectedVersion = '2.0.0-alpha.x (has startLive)';
            }
            
            return {
              detectedVersion,
              hasLiveMode,
              hasFinishEvent,
              liveMethods,
              replayerMethods: lib.Replayer ? Object.getOwnPropertyNames(lib.Replayer.prototype).length : 0,
              codeSize: lib.toString().length
            };
          } catch (e) {
            return { error: e.message };
          }
        })()
      `);
      
      console.debug('🔍 [DEBUG] Version detection result:', versionCheck);
      
      if (!versionCheck.hasLiveMode) {
        console.error('❌ [DEBUG] startLive() method not available - this version does not support live mode!');
      } else {
        console.log('✅ [DEBUG] startLive() method available - live mode supported!');
      }

      // 🔧 SANDBOX FIX: Monitor for RRWeb's internal iframe creation and fix sandbox
      const fixSandboxPermissions = () => {
        try {
          const iframeDoc = iframe.contentDocument;
          if (!iframeDoc) return false;
          
          const rrwebIframe = iframeDoc.querySelector('iframe[sandbox]');
          if (rrwebIframe) {
            const currentSandbox = rrwebIframe.getAttribute('sandbox');
            console.log('🔧 [SANDBOX FIX] Found RRWeb internal iframe, current sandbox:', currentSandbox);
            
            // Add allow-scripts to existing sandbox permissions
            if (!currentSandbox?.includes('allow-scripts')) {
              rrwebIframe.setAttribute('sandbox', 'allow-same-origin allow-scripts allow-forms');
              console.log('✅ [SANDBOX FIX] Updated sandbox permissions to allow scripts');
              return true;
            } else {
              console.log('✅ [SANDBOX FIX] Scripts already allowed in sandbox');
              return true;
            }
          }
          return false;
        } catch (error) {
          console.warn('⚠️ [SANDBOX FIX] Could not modify iframe sandbox:', error);
          return false;
        }
      };

            // 🔧 AGGRESSIVE SANDBOX FIX: Try multiple approaches
      const attemptSandboxFix = (attempt: number) => {
        if (attempt > 10) {
          console.warn('⚠️ [SANDBOX FIX] Max attempts reached, sandbox may still be restrictive');
          return;
        }
        
        setTimeout(() => {
          if (!fixSandboxPermissions()) {
            console.log(`🔍 [SANDBOX FIX] Attempt ${attempt}: No sandboxed iframe found yet...`);
            attemptSandboxFix(attempt + 1);
          }
        }, attempt * 50); // Increasing delay: 50ms, 100ms, 150ms...
      };
      
      // Start immediate fix attempts
      attemptSandboxFix(1);
      
      // Also set up mutation observer for new iframes
      setTimeout(() => {
        const iframeDoc = iframe.contentDocument;
        if (iframeDoc) {
          const observer = new MutationObserver((mutations) => {
            for (const mutation of mutations) {
              if (mutation.type === 'childList') {
                for (const addedNode of mutation.addedNodes) {
                  if (addedNode.nodeType === 1) {
                    const element = addedNode as Element;
                    if (element.tagName === 'IFRAME') {
                      console.log('🔧 [SANDBOX FIX] New iframe detected via observer, checking sandbox...');
                      fixSandboxPermissions();
                    }
                  }
                }
              }
            }
          });
          
          observer.observe(iframeDoc.body || iframeDoc.documentElement, {
            childList: true,
            subtree: true
          });
          
          // Cleanup observer after 10 seconds
          setTimeout(() => observer.disconnect(), 10000);
        }
      }, 50);

      // Add event listeners for debugging and monitoring
      this.setupReplayerEventListeners();
      
      // Step 3: Add error boundary for CSS insertion and media playback issues
      if (typeof (iframeWindow as any).addEventListener === 'function') {
        (iframeWindow as any).addEventListener('error', (event: ErrorEvent) => {
          if (event.message && event.message.includes('insertBefore')) {
            console.warn('🔧 [WorkflowVisualizer] Caught DOM insertBefore error in iframe:', event.message);
            // Don't propagate - let rrweb continue processing other events
            event.preventDefault();
            return false;
          }
          
          // Handle media playback errors (AbortError from rapid play/pause cycles)
          if (event.message && (
            event.message.includes('AbortError') || 
            event.message.includes('play() request was interrupted') ||
            event.message.includes('media playback error')
          )) {
            console.warn('🎵 [WorkflowVisualizer] Caught media playback error in iframe:', event.message);
            // Don't propagate - this is expected with live streaming + media
            event.preventDefault();
            return false;
          }
        });
        
        // Also catch unhandled promise rejections for media errors
        (iframeWindow as any).addEventListener('unhandledrejection', (event: PromiseRejectionEvent) => {
          if (event.reason && typeof event.reason === 'object') {
            const errorMsg = event.reason.message || String(event.reason);
            if (errorMsg.includes('AbortError') || 
                errorMsg.includes('play() request was interrupted') ||
                errorMsg.includes('media playback error')) {
              console.warn('🎵 [WorkflowVisualizer] Caught unhandled media promise rejection:', errorMsg);
              console.log('🔧 [WorkflowVisualizer] Preventing unhandled rejection - this is expected with live mode + media');
              event.preventDefault();
              return false;
            }
          }
        });
      }
      
      // Official live mode pattern: replayer is ready for events
      console.log('🎯 [WorkflowVisualizer] RRWeb replayer fully initialized and ready for events');
      this.callbacks.onEvent({ type: 'player_ready' });
    } catch (error) {
      console.error('❌ [WorkflowVisualizer] Failed to create rrweb replayer:', error);
      console.error('💥 [WorkflowVisualizer] Error details:', {
        message: error instanceof Error ? error.message : String(error),
        stack: error instanceof Error ? error.stack : undefined
      });
      this.callbacks.onError(error as Error);
    }
  }
}

export type { 
  WorkflowVisualizerConfig, 
  WorkflowVisualizerCallbacks, 
  WorkflowVisualizerState, 
  WorkflowVisualizerStats 
}; 