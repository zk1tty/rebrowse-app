import asyncio
import json
import uuid

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional

from .dependencies import supabase, get_user, get_user_optional, get_current_user, validate_session_token
from .service import WorkflowService, list_all_workflows, get_workflow_by_id, build_workflow_from_recording_data, start_workflow_upload_job, get_workflow_job_status
from .views import (
	TaskInfo, WorkflowUpdateRequest, WorkflowMetadataUpdateRequest, WorkflowExecuteRequest,
	WorkflowDeleteStepRequest, WorkflowAddRequest, WorkflowBuildRequest, WorkflowResponse,
	WorkflowListResponse, WorkflowExecuteResponse, WorkflowLogsResponse, WorkflowRecordResponse,
	WorkflowStatusResponse, WorkflowCancelResponse, WorkflowBuildResponse, WorkflowUploadResponse,
	WorkflowJobStatus, UploadRequest, OwnershipResponse, SessionUploadRequest,
	SessionWorkflowUpdateRequest, SessionWorkflowMetadataUpdateRequest,
	SessionWorkflowDeleteStepRequest, SessionWorkflowExecuteRequest
)

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
		return WorkflowExecuteResponse(
			success=True,
			task_id=task_id,
			workflow=workflow_name,
			log_position=log_pos,
			message=f"Workflow '{workflow_name}' execution started with task ID: {task_id}",
		)
	except Exception as exc:
		raise HTTPException(status_code=500, detail=f'Error starting workflow: {exc}')


@local_wf_router.get('/logs/{task_id}', response_model=WorkflowLogsResponse)
async def get_logs(task_id: str, position: int = 0):
	service = get_service()
	task_info = service.active_tasks.get(task_id)
	logs, new_pos = await service._read_logs_from_position(position)
	return WorkflowLogsResponse(
		logs=logs,
		position=new_pos,
		log_position=new_pos,
		status=task_info.status if task_info else 'unknown',
		result=task_info.result if task_info else None,
		error=task_info.error if task_info else None,
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
	return await list_all_workflows()

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
async def execute_workflow_session(id: uuid.UUID, request: SessionWorkflowExecuteRequest):
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
		
		# Start workflow execution in background
		task = asyncio.create_task(
			service.run_workflow_session_in_background(
				task_id=task_id,
				workflow_id=str(id),
				inputs=request.inputs or {},
				cancel_event=cancel_event,
				owner_id=user_id
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
		
		return WorkflowExecuteResponse(
			success=True,
			task_id=task_id,
			workflow=workflow.get("name", "Unknown"),
			log_position=log_pos,
			message=f"Workflow '{workflow.get('name', 'Unknown')}' execution started with task ID: {task_id}"
		)
		
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Failed to execute workflow: {str(e)}")
