from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict

from workflow_use.schema.views import WorkflowDefinitionSchema


# Task Models
class TaskInfo(BaseModel):
	model_config = ConfigDict(extra='ignore')
	status: str
	workflow: str
	result: Optional[List[Dict[str, Any]]] = None
	error: Optional[str] = None


# Request Models
class WorkflowUpdateRequest(BaseModel):
	filename: str
	nodeId: int
	stepData: Dict[str, Any]


class WorkflowMetadataUpdateRequest(BaseModel):
	name: str
	metadata: Dict[str, Any]


class WorkflowExecuteRequest(BaseModel):
	name: str
	inputs: Dict[str, Any]


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


class WorkflowExecuteResponse(BaseModel):
	success: bool
	task_id: str
	workflow: str
	log_position: int
	message: str


class WorkflowLogsResponse(BaseModel):
	logs: List[str]
	position: int
	log_position: int
	status: str
	result: Optional[List[Dict[str, Any]]] = None
	error: Optional[str] = None


class WorkflowRecordResponse(BaseModel):
	success: bool
	workflow: Optional[WorkflowDefinitionSchema] = None
	error: Optional[str] = None


class WorkflowStatusResponse(BaseModel):
	task_id: str
	status: str
	workflow: str
	result: Optional[List[Dict[str, Any]]] = None
	error: Optional[str] = None


class WorkflowCancelResponse(BaseModel):
	success: bool
	message: str


class WorkflowBuildResponse(BaseModel):
	success: bool
	message: str
	error: Optional[str] = None


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

class SessionWorkflowExecuteRequest(BaseModel):
	inputs: Dict[str, Any]  # Input parameters for workflow execution
	session_token: str
