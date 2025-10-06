"""
Local workflow routes (dev/legacy).

These endpoints operate on local JSON workflows stored under tmp/ and do not
use Supabase or execution history. Keep for development/testing; avoid in prod.
"""

import asyncio
import json
import uuid
import logging
from fastapi import APIRouter, HTTPException

from .service import (
    WorkflowService,
    list_all_workflows,
    get_workflow_by_id,
    build_workflow_from_recording_data,
)
from .views import (
    TaskInfo,
    WorkflowUpdateRequest,
    WorkflowMetadataUpdateRequest,
    WorkflowExecuteRequest,
    WorkflowDeleteStepRequest,
    WorkflowAddRequest,
    WorkflowBuildRequest,
    WorkflowResponse,
    WorkflowListResponse,
    WorkflowExecuteResponse,
    WorkflowLogsResponse,
    WorkflowRecordResponse,
)
from .service_factory import get_service  # reuse existing service factory

logger = logging.getLogger(__name__)

local_wf_router = APIRouter(prefix='/api/workflows')


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

    # Find matching workflow in tmp dir
    matching_file = None
    for file_path in service.tmp_dir.iterdir():
        if not file_path.is_file() or file_path.name.startswith('temp_recording'):
            continue
        try:
            workflow_content = json.loads(file_path.read_text())
            if workflow_content.get('name') == workflow_name:
                matching_file = file_path
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
            message=f"Workflow '{workflow_name}' execution started with task ID: {task_id}",
            visual=request.visual,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'Error starting workflow: {exc}')


@local_wf_router.post('/add', response_model=WorkflowResponse)
async def add_workflow(request: WorkflowAddRequest):
    service = get_service()
    if not request.name:
        raise HTTPException(status_code=400, detail='Missing workflow name')
    if not request.content:
        raise HTTPException(status_code=400, detail='Missing workflow content')
    try:
        json.loads(request.content)
        return service.add_workflow(request)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail='Invalid JSON content')


