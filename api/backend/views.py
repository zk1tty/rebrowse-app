from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict

from workflow_use.schema.views import WorkflowDefinitionSchema


# Task Models
class TaskInfo(BaseModel):
	model_config = ConfigDict(extra='ignore')
	status: str
	workflow: str
	result: Optional[Any] = None
	error: Optional[str] = None
	# Visual streaming URLs (rrweb-based)
	visual_stream_url: Optional[str] = None  # rrweb streaming endpoint
	viewer_url: Optional[str] = None  # rrweb viewer page


# Request Models
class WorkflowUpdateRequest(BaseModel):
	filename: str
	nodeId: int
	stepData: Dict[str, Any]


class WorkflowMetadataUpdateRequest(BaseModel):
	name: str
	metadata: Dict[str, Any]


# ENHANCED: Visual streaming support in workflow execution
class VisualWorkflowRequest(BaseModel):
	name: str
	inputs: dict
	mode: str = "auto"  # "cloud-run", "local-run", or "auto"
	visual_streaming: bool = True  # Enable rrweb visual streaming
	visual_quality: str = "standard"  # "low", "standard", "high"
	visual_events_buffer: int = 1000  # Number of events to buffer


class WorkflowExecuteRequest(BaseModel):
	name: str
	inputs: dict
	mode: str = "auto"  # "cloud-run", "local-run", or "auto"
	visual: bool = False  # Legacy visual feedback (deprecated)


class WorkflowDeleteStepRequest(BaseModel):
	workflowName: str
	stepIndex: int

class WorkflowAddRequest(BaseModel):
	name: str
	content: str  # JSON string containing the workflow definition


class WorkflowBuildRequest(BaseModel):
	workflow: WorkflowDefinitionSchema
	prompt: str
	name: str


# Response Models
class WorkflowResponse(BaseModel):
	success: bool
	error: Optional[str] = None


class WorkflowListResponse(BaseModel):
	workflows: List[str]


# ENHANCED: Visual streaming support in workflow execution response
class VisualWorkflowResponse(BaseModel):
	success: bool
	task_id: str
	session_id: str  # Visual streaming session ID
	message: str
	execution_id: Optional[str] = None  # Newly included when available
	# Legacy and new visual fields
	workflow: Optional[str] = None  # Workflow name
	log_position: Optional[int] = None  # Log position for tracking
	mode: Optional[str] = None  # Execution mode
	visual_enabled: bool = False  # Legacy visual feedback
	visual_streaming_enabled: bool = True  # rrweb visual streaming
	visual_quality: Optional[str] = "standard"  # Visual quality setting
	# rrweb streaming URLs
	visual_stream_url: str  # WebSocket endpoint for rrweb events
	viewer_url: str  # HTML viewer page for rrweb playback


class WorkflowExecuteResponse(BaseModel):
	success: bool
	task_id: str
	message: str
	visual: bool = False  # Legacy visual feedback


class WorkflowLogsResponse(BaseModel):
	task_id: str
	logs: List[str]
	position: int


class WorkflowRecordResponse(BaseModel):
	success: bool
	workflow: Optional[WorkflowDefinitionSchema] = None
	error: Optional[str] = None


# ENHANCED: Visual streaming support in status response
class VisualWorkflowStatusResponse(BaseModel):
	"""Enhanced workflow status with visual streaming information"""
	task_id: str
	status: str
	workflow: str
	result: Optional[List[Dict[str, Any]]] = None
	error: Optional[str] = None
	# rrweb visual streaming fields
	visual_streaming_enabled: bool = False  # Whether rrweb streaming is active
	visual_stream_url: Optional[str] = None  # WebSocket URL for rrweb events
	viewer_url: Optional[str] = None  # HTML viewer URL for rrweb playback
	visual_events_count: Optional[int] = None  # Number of events captured
	visual_last_event_time: Optional[str] = None  # Timestamp of last event


class WorkflowStatusResponse(BaseModel):
	task_id: str
	status: str
	workflow: str
	result: Optional[Any] = None
	error: Optional[str] = None


class WorkflowCancelResponse(BaseModel):
	success: bool
	message: str


class WorkflowBuildResponse(BaseModel):
	success: bool
	message: str
	error: Optional[str] = None


# NEW: Visual streaming specific models
class VisualStreamingStatusRequest(BaseModel):
	"""Request model for visual streaming status"""
	session_id: str


class VisualStreamingStatusResponse(BaseModel):
	"""Response model for visual streaming status"""
	success: bool
	session_id: str
	streaming_active: bool
	streaming_ready: bool = False  # NEW: True when streaming is ready with events
	browser_ready: bool = False    # NEW: True when browser automation has started
	events_processed: int
	events_buffered: int
	last_event_time: Optional[str] = None
	connected_clients: int
	stream_url: Optional[str] = None
	viewer_url: Optional[str] = None
	quality: Optional[str] = None
	error: Optional[str] = None


class VisualStreamingEventResponse(BaseModel):
	"""Response model for individual rrweb events (FIXED FORMAT)"""
	session_id: str
	timestamp: float
	event: Dict[str, Any]  # FIXED: rrweb event object (was event_data)
	sequence_id: int = 0
	metadata: Optional[Dict[str, Any]] = None
	# REMOVED: event_type (redundant with event.type)


# New models for async processing
class WorkflowUploadResponse(BaseModel):
	success: bool
	job_id: str
	message: str
	estimated_duration_seconds: int = 30

class WorkflowJobStatus(BaseModel):
	job_id: str
	status: str  # "processing", "completed", "failed"
	progress: int  # 0-100
	workflow_id: Optional[str] = None  # UUID when completed
	error: Optional[str] = None
	estimated_remaining_seconds: Optional[int] = None

class UploadRequest(BaseModel):
	recording: dict
	goal: str
	name: Optional[str] = None

class OwnershipResponse(BaseModel):
	is_owner: bool
	owner_id: Optional[str]
	is_legacy: bool

class SessionUploadRequest(BaseModel):
	recording: dict
	goal: str
	name: Optional[str] = None
	session_token: str  # Supabase session access token

# Session-based request models for database operations
class SessionWorkflowUpdateRequest(BaseModel):
	workflow_data: dict  # The workflow JSON data to update
	session_token: str

class SessionWorkflowMetadataUpdateRequest(BaseModel):
	name: Optional[str] = None
	description: Optional[str] = None
	workflow_analysis: Optional[str] = None
	version: Optional[str] = None
	input_schema: Optional[List[dict]] = None
	session_token: str

class SessionWorkflowDeleteStepRequest(BaseModel):
	step_index: int  # Index of the step to delete
	session_token: str

# ENHANCED: Session-based workflow execution with visual streaming
class SessionVisualWorkflowExecuteRequest(BaseModel):
	"""Enhanced session-based workflow execution with visual streaming"""
	inputs: Dict[str, Any]  # Input parameters for workflow execution
	session_token: str
	mode: str = "cloud-run"  # "cloud-run" or "local-run"
	visual: bool = False  # Enable DevTools visual feedback (legacy)
	# NEW: rrweb visual streaming fields
	visual_streaming: bool = False  # Enable rrweb visual streaming
	visual_quality: str = "standard"  # "standard", "high", "low"
	visual_events_buffer: int = 1000  # Maximum events to buffer


class SessionWorkflowExecuteRequest(BaseModel):
	"""Legacy session-based workflow execution for backward compatibility"""
	inputs: Dict[str, Any]  # Input parameters for workflow execution
	session_token: str
	mode: str = "cloud-run"  # "cloud-run" or "local-run"
	visual: bool = False  # Enable visual feedback (legacy)

# NEW: Visual streaming session management models
class VisualStreamingSessionInfo(BaseModel):
	"""Information about a visual streaming session"""
	session_id: str
	streaming_active: bool
	events_processed: int
	events_buffered: int
	connected_clients: int
	created_at: float  # timestamp
	last_event_time: Optional[float] = None
	workflow_name: Optional[str] = None
	quality: str = "standard"
	stream_url: Optional[str] = None
	viewer_url: Optional[str] = None


class VisualStreamingSessionsResponse(BaseModel):
	"""Response for listing all visual streaming sessions"""
	success: bool
	sessions: Dict[str, VisualStreamingSessionInfo]
	total_sessions: int
	active_sessions: int
	total_events_processed: int
	message: str


# NEW: Workflow execution history models
class WorkflowExecutionHistory(BaseModel):
	"""Model for workflow execution history records"""
	execution_id: str  # UUID for the execution
	workflow_id: str  # UUID of the workflow that was executed
	user_id: Optional[str] = None  # User who executed the workflow
	status: str  # "running", "completed", "failed", "cancelled"
	mode: str = "cloud-run"  # "cloud-run" or "local-run"
	visual_enabled: bool = False  # Whether visual feedback was enabled
	visual_streaming_enabled: bool = False  # Whether rrweb streaming was enabled
	inputs: Dict[str, Any] = {}  # Input parameters used
	result: Optional[List[Dict[str, Any]]] = None  # Execution result
	error: Optional[str] = None  # Error message if failed
	logs: Optional[List[str]] = None  # Execution logs
	execution_time_seconds: Optional[float] = None  # Total execution time
	created_at: float  # Timestamp when execution started
	completed_at: Optional[float] = None  # Timestamp when execution finished
	session_id: Optional[str] = None  # Visual streaming session ID if applicable
	# NEW: Visual streaming metrics
	visual_events_captured: Optional[int] = None  # Number of rrweb events captured
	visual_stream_duration: Optional[float] = None  # Duration of visual streaming
	visual_quality: Optional[str] = None  # Quality setting used


class WorkflowExecutionHistoryResponse(BaseModel):
	"""Response model for workflow execution history"""
	success: bool
	executions: List[WorkflowExecutionHistory]
	total_executions: int
	page: int = 1
	page_size: int = 50
	has_next_page: bool = False
	message: str


class WorkflowExecutionStatsResponse(BaseModel):
	"""Response model for workflow execution statistics"""
	success: bool
	workflow_id: str
	total_executions: int
	successful_executions: int
	failed_executions: int
	average_execution_time: Optional[float] = None
	last_execution_at: Optional[float] = None
	most_common_mode: Optional[str] = None
	visual_streaming_usage_rate: Optional[float] = None  # Percentage of executions with visual streaming
	message: str


# ENHANCED: Visual streaming session with execution history
class EnhancedVisualStreamingSessionInfo(BaseModel):
	"""Enhanced visual streaming session with execution context"""
	session_id: str
	streaming_active: bool
	events_processed: int
	events_buffered: int
	connected_clients: int
	created_at: float  # timestamp
	last_event_time: Optional[float] = None
	workflow_name: Optional[str] = None
	workflow_id: Optional[str] = None  # NEW: Link to workflow
	execution_id: Optional[str] = None  # NEW: Link to execution history
	quality: str = "standard"
	stream_url: Optional[str] = None
	viewer_url: Optional[str] = None
	# NEW: Execution context
	execution_status: Optional[str] = None  # Current execution status
	execution_progress: Optional[float] = None  # Execution progress (0-100)
	user_id: Optional[str] = None  # User who started the execution


class EnhancedVisualStreamingSessionsResponse(BaseModel):
	"""Enhanced response for listing all visual streaming sessions with execution context"""
	success: bool
	sessions: Dict[str, EnhancedVisualStreamingSessionInfo]
	total_sessions: int
	active_sessions: int
	total_events_processed: int
	# NEW: Execution history summary
	total_executions_with_streaming: int
	active_executions: int
	completed_executions_today: int
	message: str


# NEW: Database endpoint request models
class CreateWorkflowExecutionRequest(BaseModel):
	"""Request to create a new workflow execution record"""
	workflow_id: str
	session_token: str
	inputs: Dict[str, Any] = {}
	mode: str = "cloud-run"
	visual_enabled: bool = False
	visual_streaming_enabled: bool = False
	visual_quality: str = "standard"


class UpdateWorkflowExecutionRequest(BaseModel):
	"""Request to update workflow execution status"""
	execution_id: str
	session_token: str
	status: Optional[str] = None  # "running", "completed", "failed", "cancelled"
	result: Optional[List[Dict[str, Any]]] = None
	error: Optional[str] = None
	logs: Optional[List[str]] = None
	execution_time_seconds: Optional[float] = None
	visual_events_captured: Optional[int] = None
	visual_stream_duration: Optional[float] = None


class GetWorkflowExecutionHistoryRequest(BaseModel):
	"""Request to get workflow execution history"""
	workflow_id: Optional[str] = None  # Filter by specific workflow
	user_id: Optional[str] = None  # Filter by specific user
	session_token: str
	page: int = 1
	page_size: int = 50
	status_filter: Optional[str] = None  # Filter by execution status
	mode_filter: Optional[str] = None  # Filter by execution mode
	visual_streaming_only: bool = False  # Only show executions with visual streaming


# NEW: Terminate execution request model
class TerminateExecutionRequest(BaseModel):
    session_token: str
    mode: str = "stop_then_kill"  # "stop_then_kill" | "force"
    timeout_ms: int = 5000
    reason: Optional[str] = None
