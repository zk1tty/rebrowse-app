import asyncio
import json
import uuid
import time
import logging

from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect, BackgroundTasks
from typing import Optional

logger = logging.getLogger(__name__)

from .dependencies import supabase, get_user, get_user_optional, get_current_user, validate_session_token
from .service import WorkflowService, list_all_workflows, get_workflow_by_id, build_workflow_from_recording_data, start_workflow_upload_job, get_workflow_job_status
from .execution_history_service import get_execution_history_service
from .views import (
	TaskInfo, WorkflowUpdateRequest, WorkflowMetadataUpdateRequest, WorkflowExecuteRequest,
	WorkflowDeleteStepRequest, WorkflowAddRequest, WorkflowBuildRequest, WorkflowResponse,
	WorkflowListResponse, WorkflowExecuteResponse, WorkflowLogsResponse, WorkflowRecordResponse,
	WorkflowStatusResponse, WorkflowCancelResponse, WorkflowBuildResponse, WorkflowUploadResponse,
	WorkflowJobStatus, UploadRequest, OwnershipResponse, SessionUploadRequest,
	SessionWorkflowUpdateRequest, SessionWorkflowMetadataUpdateRequest,
	SessionWorkflowDeleteStepRequest, SessionWorkflowExecuteRequest,
	# NEW: Visual streaming models
	VisualWorkflowRequest, VisualWorkflowResponse, VisualWorkflowStatusResponse,
	SessionVisualWorkflowExecuteRequest, VisualStreamingStatusRequest,
	VisualStreamingStatusResponse, VisualStreamingEventResponse,
	VisualStreamingSessionInfo, VisualStreamingSessionsResponse,
	# NEW: Execution history models
	WorkflowExecutionHistory, WorkflowExecutionHistoryResponse, WorkflowExecutionStatsResponse,
	CreateWorkflowExecutionRequest, UpdateWorkflowExecutionRequest, GetWorkflowExecutionHistoryRequest,
	EnhancedVisualStreamingSessionInfo, EnhancedVisualStreamingSessionsResponse
)

# TODO: seperate the folder for local router and db router

# This router is for the original, file-based workflow operations
# It handles local execution, recording, etc.
local_wf_router = APIRouter(prefix='/api/workflows')

# This router is for the new, Supabase-backed workflow operations
# It handles creating, reading, and updating workflows in the database.
db_wf_router = APIRouter(prefix='/workflows')

# Global service instance
_service = None


def get_service(app=None) -> WorkflowService:
	global _service
	if _service is None:
		if supabase is None:
			raise RuntimeError("Supabase client not initialized. Please check your environment variables.")
		_service = WorkflowService(supabase_client=supabase, app=app)
	return _service


@local_wf_router.get('', response_model=WorkflowListResponse)
async def list_workflows():
	service = get_service()
	workflows = service.list_workflows()
	return WorkflowListResponse(workflows=workflows)


@local_wf_router.get('/{name}', response_model=str)
async def get_workflow(name: str):
	service = get_service()
	return service.get_workflow(name)


@local_wf_router.post('/update', response_model=WorkflowResponse)
async def update_workflow(request: WorkflowUpdateRequest):
	service = get_service()
	return service.update_workflow(request)


@local_wf_router.post('/update-metadata', response_model=WorkflowResponse)
async def update_workflow_metadata(request: WorkflowMetadataUpdateRequest):
	service = get_service()
	return service.update_workflow_metadata(request)

@local_wf_router.post('/delete-step', response_model=WorkflowResponse)
async def delete_step(request: WorkflowDeleteStepRequest):
	service = get_service()
	return service.delete_step(request)

@local_wf_router.post('/execute', response_model=WorkflowExecuteResponse)
async def execute_workflow(request: WorkflowExecuteRequest):
	service = get_service()
	workflow_name = request.name
	inputs = request.inputs

	if not workflow_name:
		raise HTTPException(status_code=400, detail='Missing workflow name')

	# Ugly code to find the matching workflow
	# Search through all files in tmp_dir to find the matching workflow
	matching_file = None
	for file_path in service.tmp_dir.iterdir():
		if not file_path.is_file() or file_path.name.startswith('temp_recording'):
			continue
		try:
			workflow_content = json.loads(file_path.read_text())
			if workflow_content.get('name') == workflow_name:
				matching_file = file_path
				# Update the request with the actual filename
				request.name = file_path.name
				break
		except (json.JSONDecodeError, KeyError):
			continue

	if not matching_file:
		raise HTTPException(status_code=404, detail=f'Workflow {workflow_name} not found')

	try:
		task_id = str(uuid.uuid4())
		cancel_event = asyncio.Event()
		service.cancel_events[task_id] = cancel_event
		log_pos = await service._log_file_position()

		task = asyncio.create_task(service.run_workflow_in_background(task_id, request, cancel_event))
		service.workflow_tasks[task_id] = task
		task.add_done_callback(
			lambda _: (
				service.workflow_tasks.pop(task_id, None),
				service.cancel_events.pop(task_id, None),
			)
		)
		# Build response for legacy workflow execution
		response = WorkflowExecuteResponse(
			success=True,
			task_id=task_id,
			message=f"Workflow '{workflow_name}' execution started with task ID: {task_id}",
			visual=request.visual
		)
		
		return response
	except Exception as exc:
		raise HTTPException(status_code=500, detail=f'Error starting workflow: {exc}')


# NEW: Enhanced workflow execution with visual streaming support
@local_wf_router.post('/execute/visual', response_model=VisualWorkflowResponse)
async def execute_workflow_with_visual_streaming(request: VisualWorkflowRequest):
	"""Enhanced workflow execution with rrweb visual streaming support"""
	service = get_service()
	workflow_name = request.name
	inputs = request.inputs

	if not workflow_name:
		raise HTTPException(status_code=400, detail='Missing workflow name')

	# Find the matching workflow (same logic as original)
	matching_file = None
	for file_path in service.tmp_dir.iterdir():
		if not file_path.is_file() or file_path.name.startswith('temp_recording'):
			continue
		try:
			workflow_content = json.loads(file_path.read_text())
			if workflow_content.get('name') == workflow_name:
				matching_file = file_path
				break
		except (json.JSONDecodeError, KeyError):
			continue

	if not matching_file:
		raise HTTPException(status_code=404, detail=f'Workflow {workflow_name} not found')

	try:
		task_id = str(uuid.uuid4())
		session_id = f"visual-{task_id}"
		cancel_event = asyncio.Event()
		service.cancel_events[task_id] = cancel_event
		log_pos = await service._log_file_position()

		# Create enhanced request for visual streaming
		enhanced_request = WorkflowExecuteRequest(
			name=matching_file.name,
			inputs=inputs,
			# TODO: mode should be "mode", not request.mode
			# need a type(not Unknown) for mode at WorkflowExecuteRequest
			mode=request.mode,
			visual=False  # Legacy visual support disabled
		)

		# TODO: replace this method run_workflow_with_visual_streaming with run_workflow_session_with_visual_streaming
		# Start workflow execution with visual streaming
		task = asyncio.create_task(
			service.run_workflow_with_visual_streaming(
				task_id, enhanced_request, cancel_event, 
				visual_streaming=request.visual_streaming,
				session_id=session_id,
				visual_quality=request.visual_quality,
				visual_events_buffer=request.visual_events_buffer
			)
		)
		service.workflow_tasks[task_id] = task
		task.add_done_callback(
			lambda _: (
				service.workflow_tasks.pop(task_id, None),
				service.cancel_events.pop(task_id, None),
			)
		)

		# Build enhanced response
		response = VisualWorkflowResponse(
			success=True,
			task_id=task_id,
			session_id=session_id,
			message=f"Workflow '{workflow_name}' execution started with visual streaming",
			visual_stream_url=f"/workflows/visual/{session_id}/stream",
			viewer_url=f"/workflows/visual/{session_id}/viewer"
		)
		
		return response
		
	except Exception as exc:
		raise HTTPException(status_code=500, detail=f'Error starting visual workflow: {exc}')


@local_wf_router.get('/logs/{task_id}', response_model=WorkflowLogsResponse)
async def get_logs(task_id: str, position: int = 0):
	service = get_service()
	task_info = service.active_tasks.get(task_id)
	logs, new_pos = await service._read_logs_from_position(position)
	return WorkflowLogsResponse(
		task_id=task_id,
		logs=logs,
		position=new_pos
	)


@local_wf_router.get('/tasks/{task_id}/status', response_model=WorkflowStatusResponse)
async def get_task_status(task_id: str):
	service = get_service()
	task_info = service.get_task_status(task_id)
	if not task_info:
		raise HTTPException(status_code=404, detail=f'Task {task_id} not found')
	return task_info


@local_wf_router.post('/tasks/{task_id}/cancel', response_model=WorkflowCancelResponse)
async def cancel_workflow(task_id: str):
	service = get_service()
	result = await service.cancel_workflow(task_id)
	if not result.success and result.message == 'Task not found':
		raise HTTPException(status_code=404, detail=f'Task {task_id} not found')
	return result


@local_wf_router.post('/add', response_model=WorkflowResponse)
async def add_workflow(request: WorkflowAddRequest):
	service = get_service()
	if not request.name:
		raise HTTPException(status_code=400, detail='Missing workflow name')
	if not request.content:
		raise HTTPException(status_code=400, detail='Missing workflow content')

	try:
		# Validate that the content is valid JSON
		json.loads(request.content)
		return service.add_workflow(request)
	except json.JSONDecodeError:
		raise HTTPException(status_code=400, detail='Invalid JSON content')


@local_wf_router.delete('/{name}', response_model=WorkflowResponse)
async def delete_workflow(name: str):
	service = get_service()
	if not name:
		raise HTTPException(status_code=400, detail='Missing workflow name')
	result = service.delete_workflow(name)
	if not result:
		raise HTTPException(status_code=404, detail=f'Workflow {name} not found')
	return result


@local_wf_router.post('/record', response_model=WorkflowRecordResponse)
async def record_workflow():
	service = get_service()
	return await service.record_workflow()


@local_wf_router.post('/cancel-recording', response_model=WorkflowRecordResponse)
async def cancel_recording():
	service = get_service()
	return await service.cancel_recording()


@local_wf_router.post('/build-from-recording', response_model=WorkflowBuildResponse)
async def build_workflow(request: WorkflowBuildRequest):
	service = get_service()
	return await service.build_workflow(request)


# ─── wf from Supabase ────────
@db_wf_router.get("/", summary="Public list")
async def workflows_public():
	"""Get all workflows from Supabase database (read-only, unauthenticated)"""
	return list_all_workflows()

@db_wf_router.post("/build-from-recording", summary="Convert recording to workflow")
async def build_from_recording_api(body: dict):
	"""Convert a recording JSON into a workflow JSON using BuilderService (unauthenticated)"""
	try:
		# Extract required fields from request body
		recording_data = body.get("recording")
		user_goal = body.get("goal", "")
		workflow_name = body.get("name")
		
		if not recording_data:
			raise HTTPException(status_code=400, detail="Missing 'recording' field in request body")
		
		if not user_goal:
			raise HTTPException(status_code=400, detail="Missing 'goal' field in request body")
		
		# Use our new service function to build the workflow
		built_workflow = await build_workflow_from_recording_data(
			recording_data=recording_data,
			user_goal=user_goal,
			workflow_name=workflow_name
		)
		
		# Return the built workflow as JSON
		return {
			"success": True,
			"workflow": built_workflow.model_dump(mode='json'),
			"message": f"Workflow '{built_workflow.name}' built successfully"
		}
		
	except HTTPException:
		# Re-raise HTTP exceptions
		raise
	except Exception as e:
		# Handle any other errors
		raise HTTPException(status_code=500, detail=f"Failed to build workflow: {str(e)}")

@db_wf_router.post("/", status_code=201)
async def create_wf(body: dict, session_token: str):
	"""Create a new workflow with session authentication"""
	if not supabase:
		raise HTTPException(status_code=503, detail="Database not configured")
	
	# Validate session token
	user_id = await validate_session_token(session_token)
	if not user_id:
		raise HTTPException(status_code=401, detail="Invalid or expired session token")
		
	workflow_data = body.get("json", {})
	
	from datetime import datetime
	now = datetime.utcnow().isoformat()
	
	# Extract workflow fields from the JSON payload
	row = supabase.table("workflows").insert({
		"owner_id": user_id,  # Set owner from session
		"name": workflow_data.get("name", "Untitled Workflow"),
		"version": workflow_data.get("version", "1.0"),
		"description": workflow_data.get("description", ""),
		"workflow_analysis": workflow_data.get("workflow_analysis", ""),
		"steps": workflow_data.get("steps", []),
		"input_schema": workflow_data.get("input_schema", []),
		"created_at": now,
		"updated_at": now
	}).execute().data[0]
	
	return {"id": row["id"]}

@db_wf_router.post("/public", status_code=201, summary="Create workflow (public/testing)")
async def create_wf_public(body: dict):
	"""Create a new workflow without authentication (for testing/backwards compatibility)"""
	if not supabase:
		raise HTTPException(status_code=503, detail="Database not configured")
		
	workflow_data = body.get("json", {})
	
	from datetime import datetime
	now = datetime.utcnow().isoformat()
	
	# Extract workflow fields from the JSON payload
	row = supabase.table("workflows").insert({
		"owner_id": None,  # Public workflow (no owner)
		"name": workflow_data.get("name", "Untitled Workflow"),
		"version": workflow_data.get("version", "1.0"),
		"description": workflow_data.get("description", ""),
		"workflow_analysis": workflow_data.get("workflow_analysis", ""),
		"steps": workflow_data.get("steps", []),
		"input_schema": workflow_data.get("input_schema", []),
		"created_at": now,
		"updated_at": now
	}).execute().data[0]
	
	return {"id": row["id"]}

@db_wf_router.post("/test-owned", status_code=201, summary="Create owned workflow (testing)")
async def create_wf_test_owned(body: dict):
	"""Create a new workflow with test ownership (for testing)"""
	if not supabase:
		raise HTTPException(status_code=503, detail="Database not configured")
		
	workflow_data = body.get("json", {})
	test_user_id = "b93d8ca3-5a1c-46d3-9571-36ad44d09d6d"  # Your actual user ID
	
	from datetime import datetime
	now = datetime.utcnow().isoformat()
	
	# Extract workflow fields from the JSON payload
	row = supabase.table("workflows").insert({
		"owner_id": test_user_id,  # Set to test user
		"name": workflow_data.get("name", "Untitled Workflow"),
		"version": workflow_data.get("version", "1.0"),
		"description": workflow_data.get("description", ""),
		"workflow_analysis": workflow_data.get("workflow_analysis", ""),
		"steps": workflow_data.get("steps", []),
		"input_schema": workflow_data.get("input_schema", []),
		"created_at": now,
		"updated_at": now
	}).execute().data[0]
	
	return {"id": row["id"], "owner_id": test_user_id}

@db_wf_router.get("/{id:uuid}", summary="Get workflow by UUID")
async def read_wf(id: uuid.UUID, user=Depends(get_user_optional)):
	"""Get a single workflow by UUID. Returns 404 if not found."""
	try:
		# Use our new service function
		workflow = await get_workflow_by_id(str(id))
		
		if not workflow:
			raise HTTPException(status_code=404, detail=f"Workflow with ID {id} not found")
		
		# Determine if user can edit this workflow
		editable = False
		if workflow.get("owner_id") and user:
			editable = (workflow["owner_id"] == user)
		
		# Return standardized response format
		return {
			"id": workflow["id"],
			"name": workflow.get("name"),
			"version": workflow.get("version"),
			"description": workflow.get("description"),
			"steps": workflow.get("steps", []),
			"input_schema": workflow.get("input_schema", []),
			"workflow_analysis": workflow.get("workflow_analysis"),
			"editable": editable,
			"created_at": workflow.get("created_at"),
			"updated_at": workflow.get("updated_at"),
			# Legacy support: some clients expect "json" and "title" fields
			"json": {
				"name": workflow.get("name"),
				"version": workflow.get("version"),
				"description": workflow.get("description"),
				"steps": workflow.get("steps", []),
				"input_schema": workflow.get("input_schema", []),
				"workflow_analysis": workflow.get("workflow_analysis")
			},
			"title": workflow.get("name")
		}
		
	except HTTPException:
		# Re-raise HTTP exceptions (like 404)
		raise
	except Exception as e:
		# Handle service layer errors
		if "Supabase client not configured" in str(e):
			raise HTTPException(status_code=503, detail="Database service unavailable")
		else:
			raise HTTPException(status_code=500, detail="Internal server error")

@db_wf_router.patch("/{id:uuid}")
async def update_wf(id: uuid.UUID, body: dict, user=Depends(get_user)):
	if not supabase:
		raise HTTPException(status_code=503, detail="Database not configured")
		
	row = supabase.table("workflows").select("owner").eq("id", str(id)).single().execute().data
	if row["owner"] != user:
		raise HTTPException(403)
	supabase.table("workflows").update({"json": body["json"], "title": body.get("title")}).eq("id", str(id)).execute()
	return {"status": "ok"}

@db_wf_router.patch("/{id:uuid}/session", summary="Update workflow with session token")
async def update_wf_session(id: uuid.UUID, request: SessionWorkflowUpdateRequest):
	"""Update workflow using session-based authentication"""
	try:
		if not supabase:
			raise HTTPException(status_code=503, detail="Database not configured")
		
		# Validate session token
		user_id = await validate_session_token(request.session_token)
		if not user_id:
			raise HTTPException(status_code=401, detail="Invalid or expired session token")
		
		# Check ownership
		workflow = await get_workflow_by_id(str(id))
		if not workflow:
			raise HTTPException(status_code=404, detail="Workflow not found")
		
		workflow_owner_id = workflow.get("owner_id")
		if workflow_owner_id != user_id:
			raise HTTPException(status_code=403, detail="You don't own this workflow")
		
		# Update workflow data
		from datetime import datetime
		now = datetime.utcnow().isoformat()
		
		update_data = {
			"name": request.workflow_data.get("name", workflow.get("name")),
			"version": request.workflow_data.get("version", workflow.get("version")),
			"description": request.workflow_data.get("description", workflow.get("description")),
			"workflow_analysis": request.workflow_data.get("workflow_analysis", workflow.get("workflow_analysis")),
			"steps": request.workflow_data.get("steps", workflow.get("steps", [])),
			"input_schema": request.workflow_data.get("input_schema", workflow.get("input_schema", [])),
			"updated_at": now
		}
		
		supabase.table("workflows").update(update_data).eq("id", str(id)).execute()
		
		return {"success": True, "message": "Workflow updated successfully"}
		
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Failed to update workflow: {str(e)}")

@db_wf_router.patch("/{id:uuid}/metadata/session", summary="Update workflow metadata with session token")
async def update_wf_metadata_session(id: uuid.UUID, request: SessionWorkflowMetadataUpdateRequest):
	"""Update workflow metadata using session-based authentication"""
	try:
		if not supabase:
			raise HTTPException(status_code=503, detail="Database not configured")
		
		# Validate session token
		user_id = await validate_session_token(request.session_token)
		if not user_id:
			raise HTTPException(status_code=401, detail="Invalid or expired session token")
		
		# Check ownership
		workflow = await get_workflow_by_id(str(id))
		if not workflow:
			raise HTTPException(status_code=404, detail="Workflow not found")
		
		workflow_owner_id = workflow.get("owner_id")
		if workflow_owner_id != user_id:
			raise HTTPException(status_code=403, detail="You don't own this workflow")
		
		# Build update data from provided fields
		from datetime import datetime
		now = datetime.utcnow().isoformat()
		
		update_data = {"updated_at": now}
		
		if request.name is not None:
			update_data["name"] = request.name
		if request.description is not None:
			update_data["description"] = request.description
		if request.workflow_analysis is not None:
			update_data["workflow_analysis"] = request.workflow_analysis
		if request.version is not None:
			update_data["version"] = request.version
		if request.input_schema is not None:
			update_data["input_schema"] = json.dumps(request.input_schema)
		
		supabase.table("workflows").update(update_data).eq("id", str(id)).execute()
		
		return {"success": True, "message": "Workflow metadata updated successfully"}
		
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Failed to update workflow metadata: {str(e)}")

@db_wf_router.post("/upload", summary="Upload and process recording (async)")
async def upload_recording_async(
	request: UploadRequest, 
	user_id: str = Depends(get_current_user)
):
	"""Upload recording, convert to workflow, and save to database - all in one async operation"""
	try:
		# Start async processing job with owner_id
		job_id = await start_workflow_upload_job(
			recording_data=request.recording,
			user_goal=request.goal,
			workflow_name=request.name,
			owner_id=user_id
		)
		
		return WorkflowUploadResponse(
			success=True,
			job_id=job_id,
			message="Workflow upload started. Use the job_id to check progress.",
			estimated_duration_seconds=30
		)
		
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Failed to start workflow upload: {str(e)}")

@db_wf_router.post("/upload/public", summary="Upload and process recording (public/testing)")
async def upload_recording_public(request: UploadRequest):
	"""Upload recording (public endpoint for testing/backwards compatibility)"""
	try:
		# Start async processing job without owner_id (public workflow)
		job_id = await start_workflow_upload_job(
			recording_data=request.recording,
			user_goal=request.goal,
			workflow_name=request.name,
			owner_id=None  # Public workflow
		)
		
		return WorkflowUploadResponse(
			success=True,
			job_id=job_id,
			message="Workflow upload started. Use the job_id to check progress.",
			estimated_duration_seconds=30
		)
		
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Failed to start workflow upload: {str(e)}")

@db_wf_router.post("/upload/session", summary="Upload with session token (Chrome extension)")
async def upload_recording_session(request: SessionUploadRequest):
	"""Upload recording using Supabase session token (bypasses JWT verification issues)"""
	try:
		if not supabase:
			raise HTTPException(status_code=503, detail="Database not configured")
		
		# Validate session token using our updated validation method
		user_id = await validate_session_token(request.session_token)
		if not user_id:
			raise HTTPException(status_code=401, detail="Invalid or expired session token")
		
		# Start async processing job with authenticated user_id
		job_id = await start_workflow_upload_job(
			recording_data=request.recording,
			user_goal=request.goal,
			workflow_name=request.name,
			owner_id=user_id
		)
		
		return WorkflowUploadResponse(
			success=True,
			job_id=job_id,
			message="Workflow upload started. Use the job_id to check progress.",
			estimated_duration_seconds=30
		)
		
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Failed to start workflow upload: {str(e)}")

@db_wf_router.get("/upload/{job_id}/status", summary="Check upload job status")
async def get_upload_job_status(job_id: str):
	"""Check the status of an async workflow upload job"""
	job_status = get_workflow_job_status(job_id)
	
	if not job_status:
		raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
	
	return job_status

@db_wf_router.get("/{workflow_id}/ownership", summary="Check workflow ownership")
async def check_ownership(
	workflow_id: str,
	session_token: Optional[str] = None
):
	"""Check if the current user owns the specified workflow (session-based auth)"""
	try:
		# Validate session token
		if not session_token:
			raise HTTPException(status_code=401, detail="session_token parameter required")
		
		user_id = await validate_session_token(session_token)
		if not user_id:
			raise HTTPException(status_code=401, detail="Invalid or expired session token")
		
		workflow = await get_workflow_by_id(workflow_id)
		
		if not workflow:
			raise HTTPException(status_code=404, detail="Workflow not found")
		
		workflow_owner_id = workflow.get("owner_id")
		is_owner = workflow_owner_id == user_id if workflow_owner_id else False
		is_legacy = workflow_owner_id is None
		
		return OwnershipResponse(
			is_owner=is_owner,
			owner_id=workflow_owner_id,
			is_legacy=is_legacy
		)
		
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Failed to check ownership: {str(e)}")

@db_wf_router.get("/{workflow_id}/ownership/test", summary="Test ownership endpoint (no auth)")
async def check_ownership_test(workflow_id: str):
	"""Test ownership endpoint without requiring authentication"""
	try:
		workflow = await get_workflow_by_id(workflow_id)
		
		if not workflow:
			raise HTTPException(status_code=404, detail="Workflow not found")
		
		workflow_owner_id = workflow.get("owner_id")
		test_user_id = "b93d8ca3-5a1c-46d3-9571-36ad44d09d6d"  # Your actual user ID
		is_owner = workflow_owner_id == test_user_id if workflow_owner_id else False
		is_legacy = workflow_owner_id is None
		
		return {
			"is_owner": is_owner,
			"owner_id": workflow_owner_id,
			"is_legacy": is_legacy,
			"test_user_id": test_user_id,
			"message": "Test endpoint - no auth required"
		}
		
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Failed to check ownership: {str(e)}")

@db_wf_router.delete("/{id:uuid}/steps/{step_index}/session", summary="Delete workflow step with session token")
async def delete_workflow_step_session(id: uuid.UUID, step_index: int, request: SessionWorkflowDeleteStepRequest):
	"""Delete a specific step from workflow using session-based authentication"""
	try:
		if not supabase:
			raise HTTPException(status_code=503, detail="Database not configured")
		
		# Validate session token
		user_id = await validate_session_token(request.session_token)
		if not user_id:
			raise HTTPException(status_code=401, detail="Invalid or expired session token")
		
		# Check ownership
		workflow = await get_workflow_by_id(str(id))
		if not workflow:
			raise HTTPException(status_code=404, detail="Workflow not found")
		
		workflow_owner_id = workflow.get("owner_id")
		if workflow_owner_id != user_id:
			raise HTTPException(status_code=403, detail="You don't own this workflow")
		
		# Get current steps
		current_steps = workflow.get("steps", [])
		
		# Validate step index
		if step_index < 0 or step_index >= len(current_steps):
			raise HTTPException(status_code=400, detail=f"Invalid step index: {step_index}")
		
		# Remove the step
		updated_steps = current_steps.copy()
		updated_steps.pop(step_index)
		
		# Update workflow with new steps
		from datetime import datetime
		now = datetime.utcnow().isoformat()
		
		update_data = {
			"steps": updated_steps,
			"updated_at": now
		}
		
		supabase.table("workflows").update(update_data).eq("id", str(id)).execute()
		
		return {"success": True, "message": f"Step {step_index} deleted successfully"}
		
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Failed to delete workflow step: {str(e)}")

@db_wf_router.post("/{id:uuid}/execute/session", summary="Execute workflow with session token")
async def execute_workflow_session(id: uuid.UUID, request: SessionVisualWorkflowExecuteRequest):
	"""Execute workflow using session-based authentication"""
	try:
		if not supabase:
			raise HTTPException(status_code=503, detail="Database not configured")
		
		# Validate session token
		user_id = await validate_session_token(request.session_token)
		if not user_id:
			raise HTTPException(status_code=401, detail="Invalid or expired session token")
		
		# Check workflow exists
		workflow = await get_workflow_by_id(str(id))
		if not workflow:
			raise HTTPException(status_code=404, detail="Workflow not found")
		
		# Check ownership (allow execution of public workflows)
		workflow_owner_id = workflow.get("owner_id")
		if workflow_owner_id and workflow_owner_id != user_id:
			raise HTTPException(status_code=403, detail="You don't have permission to execute this workflow")
		
		# Get workflow service instance
		service = get_service()
		
		# Generate task ID and setup cancellation
		import uuid as uuid_lib
		task_id = str(uuid_lib.uuid4())
		cancel_event = asyncio.Event()
		service.cancel_events[task_id] = cancel_event
		
		# Get log position for tracking
		log_pos = await service._log_file_position()
		
		# Validate execution mode
		if request.mode not in ["cloud-run", "local-run"]:
			raise HTTPException(status_code=400, detail="Invalid mode. Must be 'cloud-run' or 'local-run'")
		
		# Start workflow execution in background with visual streaming support
		if request.visual_streaming:
			# Use enhanced visual streaming execution
			task = asyncio.create_task(
				service.run_workflow_session_with_visual_streaming(
					task_id=task_id,
					workflow_id=str(id),
					inputs=request.inputs or {},
					cancel_event=cancel_event,
					owner_id=user_id,
					mode=request.mode,
					visual=request.visual,
					visual_streaming=request.visual_streaming,
					visual_quality=request.visual_quality,
					visual_events_buffer=request.visual_events_buffer
				)
			)
		else:
			# Use legacy execution
			task = asyncio.create_task(
				service.run_workflow_session_in_background(
					task_id=task_id,
					workflow_id=str(id),
					inputs=request.inputs or {},
					cancel_event=cancel_event,
					owner_id=user_id,
					mode=request.mode,
					visual=request.visual
				)
			)
		
		# Track the task for cleanup
		service.workflow_tasks[task_id] = task
		task.add_done_callback(
			lambda _: (
				service.workflow_tasks.pop(task_id, None),
				service.cancel_events.pop(task_id, None),
			)
		)
		
		# Build response with visual streaming information
		if request.visual_streaming:
			# Create session_id variable in proper scope
			visual_session_id = f"visual-{task_id}"
			
			response = VisualWorkflowResponse(
				success=True,
				task_id=task_id,
				workflow=workflow.get("name", "Unknown"),
				log_position=log_pos,
				message=f"Workflow '{workflow.get('name', 'Unknown')}' execution started with visual streaming (mode: {request.mode})",
				mode=request.mode,
				session_id=visual_session_id,
				visual_enabled=request.visual,
				visual_streaming_enabled=request.visual_streaming,
				visual_quality=request.visual_quality,
				visual_stream_url=f"/workflows/visual/{visual_session_id}/stream",
				viewer_url=f"/workflows/visual/{visual_session_id}/viewer"
			)
		else:
			response = WorkflowExecuteResponse(
				success=True,
				task_id=task_id,
				workflow=workflow.get("name", "Unknown"),
				log_position=log_pos,
				message=f"Workflow '{workflow.get('name', 'Unknown')}' execution started with task ID: {task_id} (mode: {request.mode})",
				mode=request.mode,
				visual_enabled=request.visual
			)
		
				
		return response
		
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Failed to execute workflow: {str(e)}")

# NEW: Visual streaming WebSocket endpoint
@db_wf_router.websocket("/visual/{session_id}/stream")
async def visual_streaming_websocket(websocket: WebSocket, session_id: str):
	"""WebSocket endpoint for rrweb visual streaming"""
	try:
		# SESSION ID NORMALIZATION (same logic as status endpoint)
		original_session_id = session_id
		if not session_id.startswith("visual-"):
			try:
				import uuid
				uuid.UUID(session_id)  # Validate UUID format
				session_id = f"visual-{session_id}"
				logger.info(f"WebSocket: Normalized session ID from '{original_session_id}' to '{session_id}'")
			except ValueError:
				await websocket.accept()
				await websocket.send_json({
					"error": f"Invalid session ID format: {original_session_id}",
					"type": "error"
				})
				await websocket.close()
				return
		
		# Import visual streaming components
		try:
			from backend.visual_streaming import streaming_manager
			from backend.websocket_manager import websocket_manager
		except ImportError:
			await websocket.accept()
			await websocket.send_json({
				"error": "Visual streaming components not available",
				"type": "error"
			})
			await websocket.close()
			return
		
		try:
			# Get or create streamer for session (using normalized session_id)
			streamer = streaming_manager.get_or_create_streamer(session_id)
			
			# Connect client to WebSocket manager (this will handle websocket.accept())
			client_id = await websocket_manager.handle_client_connection(websocket, session_id)
			
			# Send buffered events to new client
			buffered_events = streamer.get_buffered_events()
			if buffered_events:
				for event in buffered_events:
					await websocket.send_json(event)
			
			# Keep connection alive and handle messages
			while True:
				try:
					# Wait for messages from client
					message = await websocket.receive_json()
					
					# Handle different message types
					message_type = message.get("type", "unknown")
					
					if message_type == "ping":
						await websocket.send_json({"type": "pong", "timestamp": time.time()})
					elif message_type == "client_ready":
						await websocket.send_json({
							"type": "status", 
							"message": "Client connected to visual stream",
							"session_id": session_id
						})
					else:
						# Log unknown message types
						logger.warning(f"Unknown message type from client {client_id}: {message_type}")
						
				except WebSocketDisconnect:
					break
				except Exception as e:
					logger.error(f"Error in visual streaming WebSocket: {e}")
					break
					
		finally:
			# Cleanup client connection
			await websocket_manager.handle_client_disconnection(client_id)
			
	except Exception as e:
		logger.error(f"Error in visual streaming WebSocket setup: {e}")
		try:
			await websocket.send_json({"error": str(e), "type": "error"})
			await websocket.close()
		except:
			pass

# NEW: Visual streaming status endpoint
@db_wf_router.get("/visual/{session_id}/status", response_model=VisualStreamingStatusResponse)
async def get_visual_streaming_status(session_id: str):
	"""Get status of visual streaming session with readiness check"""
	try:
		# ═══════════════════════════════════════════════════════════════
		# SESSION ID VALIDATION AND NORMALIZATION
		# ═══════════════════════════════════════════════════════════════
		
		# Normalize session ID format - handle both "visual-uuid" and "uuid" formats
		original_session_id = session_id
		
		# If session_id doesn't start with "visual-", add it
		if not session_id.startswith("visual-"):
			# Validate that it's a valid UUID format
			try:
				import uuid
				uuid.UUID(session_id)  # This will raise ValueError if invalid
				session_id = f"visual-{session_id}"
				logger.info(f"Normalized session ID from '{original_session_id}' to '{session_id}'")
			except ValueError:
				# Not a valid UUID, return error
				logger.error(f"Invalid session ID format: '{original_session_id}' - must be UUID or visual-UUID format")
				raise HTTPException(
					status_code=400, 
					detail=f"Invalid session ID format: '{original_session_id}'. Must be a valid UUID or 'visual-<UUID>' format."
				)
		else:
			# Validate that the UUID part after "visual-" is valid
			uuid_part = session_id[7:]  # Remove "visual-" prefix
			try:
				import uuid
				uuid.UUID(uuid_part)  # This will raise ValueError if invalid
				logger.debug(f"Valid session ID format: '{session_id}'")
			except ValueError:
				# Invalid UUID part, return error
				logger.error(f"Invalid UUID in session ID: '{session_id}' - UUID part '{uuid_part}' is invalid")
				raise HTTPException(
					status_code=400, 
					detail=f"Invalid session ID format: '{session_id}'. The UUID part '{uuid_part}' is not valid."
				)
		
		# ═══════════════════════════════════════════════════════════════
		# VISUAL STREAMING STATUS LOGIC
		# ═══════════════════════════════════════════════════════════════
		
		# Import visual streaming components
		try:
			from backend.visual_streaming import streaming_manager
			from backend.websocket_manager import websocket_manager
		except ImportError:
			raise HTTPException(
				status_code=503, 
				detail="Visual streaming components not available"
			)
		
		# Get streamer for session (using normalized session_id)
		streamer = streaming_manager.get_streamer(session_id)
		
		if not streamer:
			logger.warning(f"Session not found: '{session_id}' (original: '{original_session_id}')")
			return VisualStreamingStatusResponse(
				success=False,
				session_id=session_id,  # Return normalized ID
				streaming_active=False,
				streaming_ready=False,
				browser_ready=False,
				events_processed=0,
				events_buffered=0,
				connected_clients=0,
				error=f"Session not found: '{session_id}'"
			)
		
		logger.info(f"Found session: '{session_id}' (original: '{original_session_id}')")
		
		# Get statistics from streamer
		stats = streamer.get_stats()
		
		# Get connected clients count from session status
		session_status = websocket_manager.get_session_status(session_id)
		connected_clients = session_status.get('client_count', 0) if 'error' not in session_status else 0
		
		# Check if streaming is truly ready (FIXED LOGIC)
		streaming_active = stats.get('streaming_active', False)
		events_processed = stats.get('total_events', 0)
		# FIX: Access browser_ready directly from stats, not as attribute
		browser_ready = stats.get('browser_ready', False)
		
		# Streaming is ready when:
		# 1. Streaming is active
		# 2. Browser automation has started (if browser_ready is available)
		# 3. At least 1 event has been processed
		streaming_ready = (streaming_active and 
		                  events_processed > 0 and
		                  (browser_ready or events_processed >= 3))  # Fallback: 3+ events indicates browser activity
		
		# Convert last_event_time to string if it exists
		last_event_time = stats.get('last_event_time')
		if last_event_time is not None and last_event_time > 0:
			last_event_time = str(last_event_time)
		else:
			last_event_time = None

		return VisualStreamingStatusResponse(
			success=True,
			session_id=session_id,  # Return normalized ID
			streaming_active=streaming_active,
			streaming_ready=streaming_ready,  # NEW: Key readiness indicator
			browser_ready=browser_ready,      # NEW: Browser automation status
			events_processed=events_processed,
			events_buffered=stats.get('buffer_size', 0),
			last_event_time=last_event_time,
			connected_clients=connected_clients,
			stream_url=f"/workflows/visual/{session_id}/stream",
			viewer_url=f"/workflows/visual/{session_id}/viewer",
			quality=stats.get('quality', 'standard')
		)
		
	except HTTPException:
		# Re-raise HTTP exceptions (like 400, 404)
		raise
	except Exception as e:
		logger.error(f"Error getting visual streaming status for '{original_session_id}': {e}")
		raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# NEW: Visual streaming viewer endpoint
@db_wf_router.get("/visual/{session_id}/viewer")
async def get_visual_streaming_viewer(session_id: str):
	"""Get HTML viewer for visual streaming session"""
	try:
		# Import visual streaming components
		try:
			from backend.visual_streaming import streaming_manager
		except ImportError:
			raise HTTPException(
				status_code=503, 
				detail="Visual streaming components not available"
			)
		
		# Check if session exists
		streamer = streaming_manager.get_streamer(session_id)
		if not streamer:
			raise HTTPException(status_code=404, detail="Visual streaming session not found")
		
		# Return HTML viewer (we'll create this in the rrweb_demo folder)
		from fastapi.responses import HTMLResponse
		
		viewer_html = f"""
		<!DOCTYPE html>
		<html>
		<head>
			<title>Visual Workflow Viewer - {session_id}</title>
			<script src="https://cdn.jsdelivr.net/npm/rrweb@latest/dist/rrweb.min.js"></script>
			<style>
				body {{ margin: 0; padding: 20px; font-family: Arial, sans-serif; }}
				#viewer {{ width: 100%; height: 80vh; border: 1px solid #ccc; }}
				#status {{ padding: 10px; background: #f5f5f5; margin-bottom: 10px; }}
				.connected {{ color: green; }}
				.disconnected {{ color: red; }}
			</style>
		</head>
		<body>
			<div id="status">
				<strong>Session:</strong> {session_id} | 
				<strong>Status:</strong> <span id="connection-status" class="disconnected">Connecting...</span> |
				<strong>Events:</strong> <span id="event-count">0</span>
			</div>
			<div id="viewer"></div>
			
			<script>
				const sessionId = '{session_id}';
				const wsUrl = `ws://localhost:8000/workflows/visual/${{sessionId}}/stream`;
				let replayer = null;
				let eventCount = 0;
				
				// 🔧 FIX: Enhanced replayer with iframe sandbox handling
				function initReplayer() {{
					replayer = new rrweb.Replayer([], {{
						target: document.getElementById('viewer'),
						mouseTail: false,
						useVirtualDom: false,  // Disable virtual DOM to prevent sandbox issues
						liveMode: true,        // Enable live mode for real-time updates
						skipInactive: false,   // Don't skip any events
						speed: 1,              // Normal playback speed
						blockClass: 'rr-block',
						ignoreClass: 'rr-ignore',
						
						// 🔧 IFRAME SANDBOX FIXES
						UNSAFE_replayCanvas: true,    // Allow canvas replay despite security
						unpackFn: rrweb.unpack,      // Ensure proper unpacking
						
						// Enhanced CSS handling for Amazon's complex styles
						insertStyleRules: [
							'.rr-block {{ visibility: hidden !important; }}',
							'.rr-ignore {{ pointer-events: none !important; }}',
							'iframe {{ pointer-events: auto !important; }}',  // Fix iframe interactions
							'[data-rrweb-id] {{ position: relative !important; }}'  // Ensure element positioning
						],
						
						// 🔧 ERROR HANDLING for sandbox issues
						onError: function(error) {{
							console.warn('rrweb replayer warning (continuing):', error);
							// Don't throw - continue replay despite sandbox errors
						}},
						
						// Custom event processing for better Amazon compatibility
						plugins: [
							// Handle Amazon's dynamic content loading
							{{
								onBuild: (node, options) => {{
									if (node.tagName === 'IFRAME') {{
										// Remove sandbox restrictions for replay
										node.removeAttribute('sandbox');
									}}
									return node;
								}}
							}}
						]
					}});
					
					// Start live mode immediately
					replayer.startLive();
					console.log('🎬 Enhanced rrweb replayer initialized with sandbox fixes');
				}}
				
				// Connect to WebSocket
				function connect() {{
					const ws = new WebSocket(wsUrl);
					
					ws.onopen = function() {{
						document.getElementById('connection-status').textContent = 'Connected';
						document.getElementById('connection-status').className = 'connected';
						ws.send(JSON.stringify({{type: 'client_ready'}}));
					}};
					
					ws.onmessage = function(event) {{
						let data;
						try {{
							data = JSON.parse(event.data);
						}} catch (e) {{
							console.error('❌ Failed to parse WebSocket message:', e);
							return;
						}}
						
						// 🔧 FIX: Enhanced event processing with fallback handling
						let rrwebEvent = null;
						
						// Primary format: New backend format (should work after our fixes)
						if (data.event) {{
							rrwebEvent = data.event;
							console.log('✅ Received new format event:', rrwebEvent.type);
						}}
						// Fallback format: Legacy event_data format (for backward compatibility)
						else if (data.event_data) {{
							rrwebEvent = data.event_data;
							console.warn('⚠️ Received legacy event_data format, using fallback');
						}}
						// Alternative format: Direct rrweb event
						else if (data.type !== undefined) {{
							rrwebEvent = data;
							console.warn('⚠️ Received direct rrweb event format');
						}}
						// Unknown format
						else {{
							console.error('❌ Unknown event format:', Object.keys(data));
							return;
						}}
						
						// Validate rrweb event structure
						if (!rrwebEvent || typeof rrwebEvent.type !== 'number') {{
							console.error('❌ Invalid rrweb event structure:', rrwebEvent);
							return;
						}}
						
						// Initialize replayer on first FullSnapshot (type 2)
						if (rrwebEvent.type === 2 && !replayer) {{
							console.log('🎬 Initializing replayer with FullSnapshot');
							initReplayer();
						}}
						
						// Add event to replayer if it exists
						if (replayer && typeof replayer.addEvent === 'function') {{
							try {{
								replayer.addEvent(rrwebEvent);
								eventCount++;
								document.getElementById('event-count').textContent = eventCount;
								
								// Enhanced logging for debugging
								if (rrwebEvent.type === 2) {{
									console.log('📸 FullSnapshot added to replayer');
								}} else if (rrwebEvent.type === 3) {{
									console.log('📝 IncrementalSnapshot added to replayer');
								}}
								
							}} catch (replayError) {{
								console.warn('⚠️ Replayer error (continuing anyway):', replayError);
								// Continue processing other events even if one fails
							}}
						}} else if (rrwebEvent.type === 2) {{
							console.error('❌ FullSnapshot received but replayer not available');
						}}
					}};
					
					ws.onclose = function() {{
						document.getElementById('connection-status').textContent = 'Disconnected';
						document.getElementById('connection-status').className = 'disconnected';
						// Attempt to reconnect after 3 seconds
						setTimeout(connect, 3000);
					}};
					
					ws.onerror = function(error) {{
						console.error('WebSocket error:', error);
					}};
				}}
				
				// Start connection
				connect();
			</script>
		</body>
		</html>
		"""
		
		return HTMLResponse(content=viewer_html)
		
	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"Error serving visual streaming viewer: {e}")
		raise HTTPException(status_code=500, detail=str(e))


# NEW: List all visual streaming sessions
@db_wf_router.get("/visual/sessions", response_model=VisualStreamingSessionsResponse)
async def list_visual_streaming_sessions():
	"""List all active visual streaming sessions"""
	try:
		# Import visual streaming components
		try:
			from backend.visual_streaming import streaming_manager
			from backend.websocket_manager import websocket_manager
		except ImportError:
			raise HTTPException(
				status_code=503, 
				detail="Visual streaming components not available"
			)
		
		# Get all streamers
		all_stats = streaming_manager.get_all_stats()
		
		sessions = {}
		total_events = 0
		active_count = 0
		
		for session_id, stats in all_stats.get('sessions', {}).items():
			# Get connected clients count from session status
			session_status = websocket_manager.get_session_status(session_id)
			connected_clients = session_status.get('client_count', 0) if 'error' not in session_status else 0
			is_active = stats.get('streaming_active', False)
			
			if is_active:
				active_count += 1
			
			events_processed = stats.get('total_events', 0)
			total_events += events_processed
			
			# Convert last_event_time to float if it exists
			last_event_time = stats.get('last_event_time')
			if last_event_time is not None and last_event_time > 0:
				last_event_time = float(last_event_time)
			else:
				last_event_time = None
			
			sessions[session_id] = VisualStreamingSessionInfo(
				session_id=session_id,
				streaming_active=is_active,
				events_processed=events_processed,
				events_buffered=stats.get('buffer_size', 0),
				connected_clients=connected_clients,
				created_at=stats.get('created_at', time.time()),
				last_event_time=last_event_time,
				quality=stats.get('quality', 'standard'),
				stream_url=f"/workflows/visual/{session_id}/stream",
				viewer_url=f"/workflows/visual/{session_id}/viewer"
			)
		
		return VisualStreamingSessionsResponse(
			success=True,
			sessions=sessions,
			total_sessions=len(sessions),
			active_sessions=active_count,
			total_events_processed=total_events,
			message=f"Found {len(sessions)} visual streaming sessions ({active_count} active)"
		)
		
	except Exception as e:
		logger.error(f"Error listing visual streaming sessions: {e}")
		raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# ENHANCED DATABASE ENDPOINTS - Workflow Execution History
# ═══════════════════════════════════════════════════════════════════════════════

@db_wf_router.post("/executions", response_model=dict, summary="Create workflow execution record")
async def create_workflow_execution(request: CreateWorkflowExecutionRequest):
	"""Create a new workflow execution record in the database"""
	try:
		if not supabase:
			raise HTTPException(status_code=503, detail="Database not configured")
		
		# Validate session token
		user_id = await validate_session_token(request.session_token)
		if not user_id:
			raise HTTPException(status_code=401, detail="Invalid or expired session token")
		
		# Verify workflow exists
		workflow = await get_workflow_by_id(request.workflow_id)
		if not workflow:
			raise HTTPException(status_code=404, detail="Workflow not found")
		
		# Get execution history service
		execution_service = get_execution_history_service(supabase)
		
		# Generate session ID for visual streaming if enabled
		session_id = None
		if request.visual_streaming_enabled:
			session_id = f"visual-{uuid.uuid4()}"
		
		# Create execution record
		execution_id = await execution_service.create_execution_record(
			workflow_id=request.workflow_id,
			user_id=user_id,
			inputs=request.inputs,
			mode=request.mode,
			visual_enabled=request.visual_enabled,
			visual_streaming_enabled=request.visual_streaming_enabled,
			visual_quality=request.visual_quality,
			session_id=session_id
		)
		
		response = {
			"success": True,
			"execution_id": execution_id,
			"workflow_id": request.workflow_id,
			"status": "running",
			"message": "Workflow execution record created successfully"
		}
		
		# Add visual streaming URLs if enabled
		if request.visual_streaming_enabled and session_id:
			response.update({
				"session_id": session_id,
				"visual_stream_url": f"/workflows/visual/{session_id}/stream",
				"viewer_url": f"/workflows/visual/{session_id}/viewer"
			})
		
		return response
		
	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"Error creating workflow execution: {e}")
		raise HTTPException(status_code=500, detail=f"Failed to create execution record: {str(e)}")


@db_wf_router.patch("/executions/{execution_id}", response_model=dict, summary="Update workflow execution status")
async def update_workflow_execution(execution_id: str, request: UpdateWorkflowExecutionRequest):
	"""Update workflow execution status and results"""
	try:
		if not supabase:
			raise HTTPException(status_code=503, detail="Database not configured")
		
		# Validate session token
		user_id = await validate_session_token(request.session_token)
		if not user_id:
			raise HTTPException(status_code=401, detail="Invalid or expired session token")
		
		# Get execution history service
		execution_service = get_execution_history_service(supabase)
		
		# Update execution status
		success = await execution_service.update_execution_status(
			execution_id=execution_id,
			status=request.status,
			result=request.result,
			error=request.error,
			logs=request.logs,
			execution_time_seconds=request.execution_time_seconds,
			visual_events_captured=request.visual_events_captured,
			visual_stream_duration=request.visual_stream_duration
		)
		
		if not success:
			raise HTTPException(status_code=404, detail="Execution record not found or update failed")
		
		return {
			"success": True,
			"execution_id": execution_id,
			"message": "Execution status updated successfully"
		}
		
	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"Error updating workflow execution {execution_id}: {e}")
		raise HTTPException(status_code=500, detail=f"Failed to update execution: {str(e)}")


@db_wf_router.post("/executions/history", response_model=WorkflowExecutionHistoryResponse, summary="Get workflow execution history")
async def get_workflow_execution_history(request: GetWorkflowExecutionHistoryRequest):
	"""Get workflow execution history with filtering and pagination"""
	try:
		if not supabase:
			raise HTTPException(status_code=503, detail="Database not configured")
		
		# Validate session token
		user_id = await validate_session_token(request.session_token)
		if not user_id:
			raise HTTPException(status_code=401, detail="Invalid or expired session token")
		
		# Get execution history service
		execution_service = get_execution_history_service(supabase)
		
		# If user_id is provided in request, verify it matches the authenticated user
		# (unless it's an admin - for now, only allow users to see their own history)
		filter_user_id = request.user_id if request.user_id else user_id
		if request.user_id and request.user_id != user_id:
			# For now, restrict to own history. In future, add admin role check here
			filter_user_id = user_id
		
		# Get execution history
		history_response = await execution_service.get_execution_history(
			workflow_id=request.workflow_id,
			user_id=filter_user_id,
			page=request.page,
			page_size=min(request.page_size, 100),  # Cap at 100 records per page
			status_filter=request.status_filter,
			mode_filter=request.mode_filter,
			visual_streaming_only=request.visual_streaming_only
		)
		
		return history_response
		
	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"Error getting workflow execution history: {e}")
		raise HTTPException(status_code=500, detail=f"Failed to retrieve execution history: {str(e)}")


@db_wf_router.get("/executions/stats/{workflow_id}", response_model=WorkflowExecutionStatsResponse, summary="Get workflow execution statistics")
async def get_workflow_execution_stats(workflow_id: str, session_token: str):
	"""Get comprehensive statistics for a workflow's execution history"""
	try:
		if not supabase:
			raise HTTPException(status_code=503, detail="Database not configured")
		
		# Validate workflow_id format (should be a UUID)
		if workflow_id in ['undefined', 'null', ''] or not workflow_id:
			raise HTTPException(status_code=400, detail="Invalid workflow ID provided")
		
		# Basic UUID format validation
		try:
			import uuid
			uuid.UUID(workflow_id)
		except ValueError:
			raise HTTPException(status_code=400, detail="Invalid workflow ID format (must be a valid UUID)")
		
		# Validate session token
		user_id = await validate_session_token(session_token)
		if not user_id:
			raise HTTPException(status_code=401, detail="Invalid or expired session token")
		
		# Verify workflow exists and user has access
		workflow = await get_workflow_by_id(workflow_id)
		if not workflow:
			raise HTTPException(status_code=404, detail="Workflow not found")
		
		# Check if user owns the workflow or if it's public
		workflow_owner_id = workflow.get("owner_id")
		if workflow_owner_id and workflow_owner_id != user_id:
			raise HTTPException(status_code=403, detail="You don't have permission to view this workflow's statistics")
		
		# Get execution history service
		execution_service = get_execution_history_service(supabase)
		
		# Get workflow statistics
		stats_response = await execution_service.get_workflow_execution_stats(workflow_id)
		
		return stats_response
		
	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"Error getting workflow execution stats for {workflow_id}: {e}")
		raise HTTPException(status_code=500, detail=f"Failed to retrieve execution statistics: {str(e)}")


@db_wf_router.get("/executions/active", response_model=dict, summary="Get active workflow executions")
async def get_active_workflow_executions(session_token: str):
	"""Get currently active workflow executions"""
	try:
		if not supabase:
			raise HTTPException(status_code=503, detail="Database not configured")
		
		# Validate session token
		user_id = await validate_session_token(session_token)
		if not user_id:
			raise HTTPException(status_code=401, detail="Invalid or expired session token")
		
		# Get execution history service
		execution_service = get_execution_history_service(supabase)
		
		# Get active executions from in-memory tracking
		active_executions = execution_service.get_active_executions()
		
		# Filter to only show user's executions
		user_executions = {
			exec_id: exec_data 
			for exec_id, exec_data in active_executions.items() 
			if exec_data.get("user_id") == user_id
		}
		
		return {
			"success": True,
			"active_executions": user_executions,
			"total_active": len(user_executions),
			"message": f"Retrieved {len(user_executions)} active executions"
		}
		
	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"Error getting active workflow executions: {e}")
		raise HTTPException(status_code=500, detail=f"Failed to retrieve active executions: {str(e)}")

# ENHANCED: Visual streaming sessions with execution history context
@db_wf_router.get("/visual/sessions/enhanced", response_model=EnhancedVisualStreamingSessionsResponse)
async def get_enhanced_visual_streaming_sessions(session_token: str):
	"""Get all visual streaming sessions with execution history context"""
	try:
		if not supabase:
			raise HTTPException(status_code=503, detail="Database not configured")
		
		# Validate session token
		user_id = await validate_session_token(session_token)
		if not user_id:
			raise HTTPException(status_code=401, detail="Invalid or expired session token")
		
		# Import visual streaming components
		try:
			from backend.visual_streaming import streaming_manager
			from backend.websocket_manager import websocket_manager
		except ImportError:
			raise HTTPException(
				status_code=503, 
				detail="Visual streaming components not available"
			)
		
		# Get execution history service
		execution_service = get_execution_history_service(supabase)
		
		# Get all streaming sessions
		all_sessions = streaming_manager.get_all_stats()
		
		# Get active executions for context
		active_executions = execution_service.get_active_executions()
		
		# Build enhanced session info
		enhanced_sessions = {}
		total_events_processed = 0
		active_sessions = 0
		total_executions_with_streaming = 0
		active_executions_count = 0
		
		for session_id, session_stats in all_sessions.get('sessions', {}).items():
			# Get WebSocket connection info
			session_status = websocket_manager.get_session_status(session_id)
			connected_clients = session_status.get('client_count', 0) if 'error' not in session_status else 0
			
			# Find corresponding execution
			execution_info = None
			execution_id = None
			for exec_id, exec_data in active_executions.items():
				if exec_data.get("session_id") == session_id:
					execution_info = exec_data
					execution_id = exec_id
					break
			
			# Build enhanced session info
			enhanced_session = EnhancedVisualStreamingSessionInfo(
				session_id=session_id,
				streaming_active=session_stats.get('streaming_active', False),
				events_processed=session_stats.get('total_events', 0),
				events_buffered=session_stats.get('buffer_size', 0),
				connected_clients=connected_clients,
				created_at=session_stats.get('created_at', time.time()),
				last_event_time=session_stats.get('last_event_time'),
				workflow_name=execution_info.get('workflow_name') if execution_info else None,
				workflow_id=execution_info.get('workflow_id') if execution_info else None,
				execution_id=execution_id,
				quality=session_stats.get('quality', 'standard'),
				stream_url=f"/workflows/visual/{session_id}/stream",
				viewer_url=f"/workflows/visual/{session_id}/viewer",
				execution_status=execution_info.get('status') if execution_info else None,
				execution_progress=None,  # Could be calculated based on execution state
				user_id=execution_info.get('user_id') if execution_info else None
			)
			
			# Only include sessions for this user
			if not execution_info or execution_info.get('user_id') == user_id:
				enhanced_sessions[session_id] = enhanced_session
				total_events_processed += session_stats.get('total_events', 0)
				
				if session_stats.get('streaming_active', False):
					active_sessions += 1
				
				if execution_info and execution_info.get('visual_streaming_enabled'):
					total_executions_with_streaming += 1
				
				if execution_info and execution_info.get('status') == 'running':
					active_executions_count += 1
		
		# Get completed executions today (for summary)
		from datetime import datetime, timedelta
		today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
		
		# This would require a database query to get today's completed executions
		# For now, we'll use a placeholder value
		completed_executions_today = 0  # TODO: Implement this query
		
		return EnhancedVisualStreamingSessionsResponse(
			success=True,
			sessions=enhanced_sessions,
			total_sessions=len(enhanced_sessions),
			active_sessions=active_sessions,
			total_events_processed=total_events_processed,
			total_executions_with_streaming=total_executions_with_streaming,
			active_executions=active_executions_count,
			completed_executions_today=completed_executions_today,
			message=f"Retrieved {len(enhanced_sessions)} enhanced visual streaming sessions"
		)
		
	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"Error getting enhanced visual streaming sessions: {e}")
		raise HTTPException(status_code=500, detail=str(e))