import logging
import time
import uuid
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta

from supabase import Client

from .views import (
    WorkflowExecutionHistory,
    WorkflowExecutionHistoryResponse,
    WorkflowExecutionStatsResponse,
    EnhancedVisualStreamingSessionInfo
)

logger = logging.getLogger(__name__)


class WorkflowExecutionHistoryService:
    """Service for managing workflow execution history in the database"""
    
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
        self.active_executions: Dict[str, Dict[str, Any]] = {}  # In-memory tracking
    
    async def create_execution_record(
        self,
        workflow_id: str,
        user_id: Optional[str] = None,
        inputs: Dict[str, Any] = None,
        mode: str = "cloud-run",
        visual_enabled: bool = False,
        visual_streaming_enabled: bool = False,
        visual_quality: str = "standard",
        session_id: Optional[str] = None
    ) -> str:
        """Create a new workflow execution record and return execution_id"""
        try:
            execution_id = str(uuid.uuid4())
            now = time.time()
            
            # Create database record
            execution_data = {
                "execution_id": execution_id,
                "workflow_id": workflow_id,
                "user_id": user_id,
                "status": "running",
                "mode": mode,
                "visual_enabled": visual_enabled,
                "visual_streaming_enabled": visual_streaming_enabled,
                "visual_quality": visual_quality if visual_streaming_enabled else None,
                "inputs": inputs or {},
                "created_at": datetime.fromtimestamp(now).isoformat(),
                "session_id": session_id
            }
            
            # Insert into database
            result = self.supabase.table("workflow_executions").insert(execution_data).execute()
            
            # Track in memory for quick access
            self.active_executions[execution_id] = {
                "workflow_id": workflow_id,
                "user_id": user_id,
                "status": "running",
                "started_at": now,
                "session_id": session_id,
                "visual_streaming_enabled": visual_streaming_enabled
            }
            
            logger.info(f"Created execution record: {execution_id} for workflow {workflow_id}")
            return execution_id
            
        except Exception as e:
            logger.error(f"Failed to create execution record: {e}")
            raise Exception(f"Failed to create execution record: {str(e)}")
    
    async def update_execution_status(
        self,
        execution_id: str,
        status: Optional[str] = None,
        result: Optional[List[Dict[str, Any]]] = None,
        error: Optional[str] = None,
        logs: Optional[List[str]] = None,
        execution_time_seconds: Optional[float] = None,
        visual_events_captured: Optional[int] = None,
        visual_stream_duration: Optional[float] = None
    ) -> bool:
        """Update workflow execution status and metrics"""
        try:
            update_data = {}
            
            if status is not None:
                update_data["status"] = status
                if status in ["completed", "failed", "cancelled"]:
                    update_data["completed_at"] = datetime.utcnow().isoformat()
            
            if result is not None:
                update_data["result"] = result
            
            if error is not None:
                update_data["error"] = error
            
            if logs is not None:
                update_data["logs"] = logs
            
            if execution_time_seconds is not None:
                update_data["execution_time_seconds"] = execution_time_seconds
            
            if visual_events_captured is not None:
                update_data["visual_events_captured"] = visual_events_captured
            
            if visual_stream_duration is not None:
                update_data["visual_stream_duration"] = visual_stream_duration
            
            # Update database
            self.supabase.table("workflow_executions").update(update_data).eq("execution_id", execution_id).execute()
            
            # Update in-memory tracking
            if execution_id in self.active_executions:
                self.active_executions[execution_id].update({
                    "status": status or self.active_executions[execution_id].get("status"),
                    "updated_at": time.time()
                })
                
                # Remove from active tracking if completed
                if status in ["completed", "failed", "cancelled"]:
                    self.active_executions.pop(execution_id, None)
            
            logger.info(f"Updated execution {execution_id}: status={status}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update execution {execution_id}: {e}")
            return False
    
    async def get_execution_history(
        self,
        workflow_id: Optional[str] = None,
        user_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
        status_filter: Optional[str] = None,
        mode_filter: Optional[str] = None,
        visual_streaming_only: bool = False
    ) -> WorkflowExecutionHistoryResponse:
        """Get workflow execution history with filtering and pagination"""
        try:
            # Build query
            query = self.supabase.table("workflow_executions").select("*")
            
            # Apply filters
            if workflow_id:
                query = query.eq("workflow_id", workflow_id)
            
            if user_id:
                query = query.eq("user_id", user_id)
            
            if status_filter:
                query = query.eq("status", status_filter)
            
            if mode_filter:
                query = query.eq("mode", mode_filter)
            
            if visual_streaming_only:
                query = query.eq("visual_streaming_enabled", True)
            
            # Apply pagination
            offset = (page - 1) * page_size
            query = query.order("created_at", desc=True).range(offset, offset + page_size - 1)
            
            # Execute query
            result = query.execute()
            
            # Convert to WorkflowExecutionHistory objects
            executions = []
            for row in result.data:
                execution = WorkflowExecutionHistory(
                    execution_id=row["execution_id"],
                    workflow_id=row["workflow_id"],
                    user_id=row.get("user_id"),
                    status=row["status"],
                    mode=row.get("mode", "cloud-run"),
                    visual_enabled=row.get("visual_enabled", False),
                    visual_streaming_enabled=row.get("visual_streaming_enabled", False),
                    inputs=row.get("inputs", {}),
                    result=row.get("result"),
                    error=row.get("error"),
                    logs=row.get("logs"),
                    execution_time_seconds=row.get("execution_time_seconds"),
                    created_at=datetime.fromisoformat(row["created_at"]).timestamp(),
                    completed_at=datetime.fromisoformat(row["completed_at"]).timestamp() if row.get("completed_at") else None,
                    session_id=row.get("session_id"),
                    visual_events_captured=row.get("visual_events_captured"),
                    visual_stream_duration=row.get("visual_stream_duration"),
                    visual_quality=row.get("visual_quality")
                )
                executions.append(execution)
            
            # Get total count for pagination
            count_query = self.supabase.table("workflow_executions").select("execution_id", count="exact")
            if workflow_id:
                count_query = count_query.eq("workflow_id", workflow_id)
            if user_id:
                count_query = count_query.eq("user_id", user_id)
            if status_filter:
                count_query = count_query.eq("status", status_filter)
            if mode_filter:
                count_query = count_query.eq("mode", mode_filter)
            if visual_streaming_only:
                count_query = count_query.eq("visual_streaming_enabled", True)
            
            count_result = count_query.execute()
            total_executions = count_result.count
            
            return WorkflowExecutionHistoryResponse(
                success=True,
                executions=executions,
                total_executions=total_executions,
                page=page,
                page_size=page_size,
                has_next_page=(offset + page_size) < total_executions,
                message=f"Retrieved {len(executions)} execution records"
            )
            
        except Exception as e:
            logger.error(f"Failed to get execution history: {e}")
            return WorkflowExecutionHistoryResponse(
                success=False,
                executions=[],
                total_executions=0,
                page=page,
                page_size=page_size,
                has_next_page=False,
                message=f"Failed to retrieve execution history: {str(e)}"
            )
    
    async def get_workflow_execution_stats(self, workflow_id: str) -> WorkflowExecutionStatsResponse:
        """Get comprehensive statistics for a workflow's execution history"""
        try:
            # Get all executions for this workflow
            result = self.supabase.table("workflow_executions").select("*").eq("workflow_id", workflow_id).execute()
            
            if not result.data:
                return WorkflowExecutionStatsResponse(
                    success=True,
                    workflow_id=workflow_id,
                    total_executions=0,
                    successful_executions=0,
                    failed_executions=0,
                    message="No execution history found for this workflow"
                )
            
            executions = result.data
            total_executions = len(executions)
            
            # Calculate statistics
            successful_executions = len([e for e in executions if e["status"] == "completed"])
            failed_executions = len([e for e in executions if e["status"] == "failed"])
            
            # Calculate average execution time
            completed_with_time = [e for e in executions if e.get("execution_time_seconds") is not None]
            average_execution_time = None
            if completed_with_time:
                average_execution_time = sum(e["execution_time_seconds"] for e in completed_with_time) / len(completed_with_time)
            
            # Find most recent execution
            last_execution_at = None
            if executions:
                latest_execution = max(executions, key=lambda e: e["created_at"])
                last_execution_at = datetime.fromisoformat(latest_execution["created_at"]).timestamp()
            
            # Find most common mode
            modes = [e.get("mode", "cloud-run") for e in executions]
            most_common_mode = max(set(modes), key=modes.count) if modes else None
            
            # Calculate visual streaming usage rate
            visual_streaming_executions = len([e for e in executions if e.get("visual_streaming_enabled", False)])
            visual_streaming_usage_rate = (visual_streaming_executions / total_executions * 100) if total_executions > 0 else 0
            
            return WorkflowExecutionStatsResponse(
                success=True,
                workflow_id=workflow_id,
                total_executions=total_executions,
                successful_executions=successful_executions,
                failed_executions=failed_executions,
                average_execution_time=average_execution_time,
                last_execution_at=last_execution_at,
                most_common_mode=most_common_mode,
                visual_streaming_usage_rate=visual_streaming_usage_rate,
                message=f"Statistics calculated for {total_executions} executions"
            )
            
        except Exception as e:
            logger.error(f"Failed to get workflow stats for {workflow_id}: {e}")
            return WorkflowExecutionStatsResponse(
                success=False,
                workflow_id=workflow_id,
                total_executions=0,
                successful_executions=0,
                failed_executions=0,
                message=f"Failed to calculate statistics: {str(e)}"
            )
    
    def get_active_executions(self) -> Dict[str, Dict[str, Any]]:
        """Get currently active executions from in-memory tracking"""
        return self.active_executions.copy()
    
    async def cleanup_old_executions(self, days_to_keep: int = 30) -> int:
        """Clean up old execution records (optional maintenance function)"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            # Delete old records
            result = self.supabase.table("workflow_executions").delete().lt("created_at", cutoff_date.isoformat()).execute()
            
            deleted_count = len(result.data) if result.data else 0
            logger.info(f"Cleaned up {deleted_count} old execution records")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old executions: {e}")
            return 0


# Global service instance
_execution_history_service: Optional[WorkflowExecutionHistoryService] = None


def get_execution_history_service(supabase_client: Client) -> WorkflowExecutionHistoryService:
    """Get or create the global execution history service instance"""
    global _execution_history_service
    if _execution_history_service is None:
        _execution_history_service = WorkflowExecutionHistoryService(supabase_client)
    return _execution_history_service 