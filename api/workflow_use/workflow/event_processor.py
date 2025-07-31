"""
Event Processing Pipeline for Visual Workflow Streaming

This module handles the capture, processing, and broadcasting of rrweb events
from browser pages during workflow execution.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Callable
from collections import deque
from datetime import datetime

logger = logging.getLogger(__name__)


class VisualEventProcessor:
    """Processes rrweb events from browser pages and routes them to streaming system"""
    
    def __init__(self, session_id: str, max_buffer_size: int = 1000):
        self.session_id = session_id
        self.max_buffer_size = max_buffer_size
        self.event_buffer = deque(maxlen=max_buffer_size)
        self.event_queue = asyncio.Queue()
        self.processing_active = False
        self.event_callbacks: List[Callable] = []
        
        # Event statistics
        self.events_processed = 0
        self.events_dropped = 0
        self.last_event_time = None
        
        # Event type counters
        self.event_type_counts = {
            0: 0,  # DomContentLoaded
            1: 0,  # Load
            2: 0,  # FullSnapshot
            3: 0,  # IncrementalSnapshot
            4: 0,  # Meta
            5: 0,  # Custom
        }
    
    def add_event_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Add a callback function to be called for each processed event"""
        self.event_callbacks.append(callback)
    
    def remove_event_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Remove a callback function"""
        if callback in self.event_callbacks:
            self.event_callbacks.remove(callback)
    
    async def process_visual_events(self, browser_page, session_id: str) -> None:
        """
        Process rrweb events from browser page
        
        This is the main entry point for Step 2.3 implementation
        """
        if not browser_page:
            logger.warning(f"No browser page available for session {session_id}")
            return
        
        logger.info(f"Starting visual event processing for session {session_id}")
        
        try:
            # Setup event capture from browser page
            await self._setup_event_capture(browser_page)
            
            # Start processing loop
            self.processing_active = True
            await self._event_processing_loop()
            
        except Exception as e:
            logger.error(f"Error in visual event processing: {e}")
            raise
        finally:
            self.processing_active = False
            logger.info(f"Visual event processing stopped for session {session_id}")
    
    async def _setup_event_capture(self, browser_page) -> None:
        """Setup event capture from browser page"""
        try:
            # Expose function to receive rrweb events from browser
            await browser_page.expose_function('sendRRWebEvent', self._handle_browser_event)
            logger.info(f"Event capture setup completed for session {self.session_id}")
            
        except Exception as e:
            if "already registered" in str(e):
                logger.info(f"Event capture function already registered for session {self.session_id}")
            else:
                logger.error(f"Failed to setup event capture: {e}")
                raise
    
    async def _handle_browser_event(self, event_json: str) -> None:
        """Handle rrweb events received from the browser"""
        try:
            # Parse the event
            event_data = json.loads(event_json)
            
            # Create enhanced event with metadata
            enhanced_event = {
                'session_id': self.session_id,
                'timestamp': datetime.now().isoformat(),
                'event_loop_time': asyncio.get_event_loop().time(),
                'event': event_data,
                'metadata': {
                    'processed_by': 'VisualEventProcessor',
                    'buffer_size': len(self.event_buffer),
                    'queue_size': self.event_queue.qsize()
                }
            }
            
            # Update statistics
            self._update_event_statistics(event_data)
            
            # Add to buffer for reconnection scenarios
            self.event_buffer.append(enhanced_event)
            
            # Add to processing queue
            if not self.event_queue.full():
                await self.event_queue.put(enhanced_event)
            else:
                self.events_dropped += 1
                logger.warning(f"Event queue full, dropped event for session {self.session_id}")
            
            logger.debug(f"Processed browser event: type={event_data.get('type', 'unknown')} for session {self.session_id}")
            
        except Exception as e:
            logger.error(f"Error handling browser event: {e}")
    
    def _update_event_statistics(self, event_data: Dict[str, Any]) -> None:
        """Update event processing statistics"""
        self.events_processed += 1
        self.last_event_time = datetime.now()
        
        # Update event type counter
        event_type = event_data.get('type', -1)
        if event_type in self.event_type_counts:
            self.event_type_counts[event_type] += 1
    
    async def _event_processing_loop(self) -> None:
        """Main event processing loop"""
        logger.info(f"Starting event processing loop for session {self.session_id}")
        
        while self.processing_active:
            try:
                # Wait for event with timeout
                event = await asyncio.wait_for(self.event_queue.get(), timeout=1.0)
                
                # Process the event
                await self._process_single_event(event)
                
            except asyncio.TimeoutError:
                # No events to process, continue loop
                continue
            except Exception as e:
                logger.error(f"Error in event processing loop: {e}")
                # Continue processing other events
                continue
    
    async def _process_single_event(self, event: Dict[str, Any]) -> None:
        """Process a single event and call all callbacks"""
        try:
            # Call all registered callbacks
            for callback in self.event_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(event)
                    else:
                        callback(event)
                except Exception as e:
                    logger.error(f"Error in event callback: {e}")
            
            logger.debug(f"Successfully processed event for session {self.session_id}")
            
        except Exception as e:
            logger.error(f"Error processing single event: {e}")
    
    def get_buffered_events(self) -> List[Dict[str, Any]]:
        """Get all buffered events for reconnection scenarios"""
        return list(self.event_buffer)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get event processing statistics"""
        return {
            'session_id': self.session_id,
            'events_processed': self.events_processed,
            'events_dropped': self.events_dropped,
            'buffer_size': len(self.event_buffer),
            'queue_size': self.event_queue.qsize(),
            'last_event_time': self.last_event_time.isoformat() if self.last_event_time else None,
            'event_type_counts': self.event_type_counts.copy(),
            'processing_active': self.processing_active,
            'callbacks_registered': len(self.event_callbacks)
        }
    
    async def stop_processing(self) -> None:
        """Stop event processing"""
        self.processing_active = False
        logger.info(f"Event processing stopped for session {self.session_id}")
    
    def clear_buffer(self) -> None:
        """Clear the event buffer"""
        self.event_buffer.clear()
        logger.info(f"Event buffer cleared for session {self.session_id}")


class WorkflowEventManager:
    """Manages event processors for multiple workflow sessions"""
    
    def __init__(self):
        self.processors: Dict[str, VisualEventProcessor] = {}
        self.global_callbacks: List[Callable] = []
    
    def create_processor(self, session_id: str, max_buffer_size: int = 1000) -> VisualEventProcessor:
        """Create a new event processor for a session"""
        if session_id in self.processors:
            logger.warning(f"Processor already exists for session {session_id}, returning existing")
            return self.processors[session_id]
        
        processor = VisualEventProcessor(session_id, max_buffer_size)
        
        # Add global callbacks to the processor
        for callback in self.global_callbacks:
            processor.add_event_callback(callback)
        
        self.processors[session_id] = processor
        logger.info(f"Created event processor for session {session_id}")
        
        return processor
    
    def get_processor(self, session_id: str) -> Optional[VisualEventProcessor]:
        """Get event processor for a session"""
        return self.processors.get(session_id)
    
    def remove_processor(self, session_id: str) -> None:
        """Remove event processor for a session"""
        if session_id in self.processors:
            processor = self.processors[session_id]
            asyncio.create_task(processor.stop_processing())
            del self.processors[session_id]
            logger.info(f"Removed event processor for session {session_id}")
    
    def add_global_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Add a global callback that applies to all processors"""
        self.global_callbacks.append(callback)
        
        # Add to existing processors
        for processor in self.processors.values():
            processor.add_event_callback(callback)
    
    def get_all_statistics(self) -> Dict[str, Any]:
        """Get statistics for all processors"""
        return {
            'total_processors': len(self.processors),
            'active_sessions': list(self.processors.keys()),
            'global_callbacks': len(self.global_callbacks),
            'processor_stats': {
                session_id: processor.get_statistics()
                for session_id, processor in self.processors.items()
            }
        }


# Global event manager instance
event_manager = WorkflowEventManager()


# Convenience functions for Step 2.3 implementation
async def process_visual_events(browser_page, session_id: str) -> VisualEventProcessor:
    """
    Main entry point for Step 2.3: Event Processing Pipeline
    
    Args:
        browser_page: The browser page to capture events from
        session_id: Session identifier
        
    Returns:
        VisualEventProcessor instance for further configuration
    """
    processor = event_manager.create_processor(session_id)
    
    # Start processing in background
    asyncio.create_task(processor.process_visual_events(browser_page, session_id))
    
    return processor


def get_event_processor(session_id: str) -> Optional[VisualEventProcessor]:
    """Get event processor for a session"""
    return event_manager.get_processor(session_id)


def cleanup_event_processor(session_id: str) -> None:
    """Clean up event processor for a session"""
    event_manager.remove_processor(session_id) 