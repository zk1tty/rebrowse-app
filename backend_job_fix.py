# Improved job processing with better error handling
async def process_workflow_upload_async_improved(job_id: str, recording_data: dict, user_goal: str, workflow_name: Optional[str] = None, owner_id: Optional[str] = None):
    """Process workflow upload with improved error handling and progress tracking."""
    try:
        # Update job status: Starting conversion
        workflow_jobs[job_id].status = "processing"
        workflow_jobs[job_id].progress = 10
        workflow_jobs[job_id].estimated_remaining_seconds = 25
        
        # Step 1: Convert recording to workflow (this takes time)
        try:
            built_workflow = await build_workflow_from_recording_data(
                recording_data=recording_data,
                user_goal=user_goal,
                workflow_name=workflow_name
            )
            
            # Update progress: Conversion successful
            workflow_jobs[job_id].progress = 80
            workflow_jobs[job_id].estimated_remaining_seconds = 5
            
        except Exception as e:
            # Conversion failed
            workflow_jobs[job_id].status = "failed"
            workflow_jobs[job_id].error = f"Workflow conversion failed: {str(e)}"
            workflow_jobs[job_id].estimated_remaining_seconds = 0
            print(f"Workflow conversion failed for job {job_id}: {e}")
            return None
        
        # Step 2: Save to database with content sanitization
        try:
            if not supabase:
                raise Exception("Database not configured")
            
            from datetime import datetime
            now = datetime.utcnow().isoformat()
            
            # Sanitize content before database insertion
            sanitized_steps = []
            for step in built_workflow.steps:
                step_dict = step.model_dump()
                # Remove or sanitize problematic Unicode characters
                if 'content' in step_dict and step_dict['content']:
                    step_dict['content'] = sanitize_content(step_dict['content'])
                sanitized_steps.append(step_dict)
            
            row = supabase.table("workflows").insert({
                "owner_id": owner_id,
                "name": sanitize_content(built_workflow.name),
                "version": built_workflow.version,
                "description": sanitize_content(built_workflow.description),
                "workflow_analysis": sanitize_content(built_workflow.workflow_analysis),
                "steps": sanitized_steps,
                "input_schema": [item.model_dump() for item in built_workflow.input_schema],
                "created_at": now,
                "updated_at": now
            }).execute().data[0]
            
            # Job completed successfully
            workflow_jobs[job_id].status = "completed" 
            workflow_jobs[job_id].progress = 100
            workflow_jobs[job_id].workflow_id = row["id"]
            workflow_jobs[job_id].estimated_remaining_seconds = 0
            
            return row["id"]
            
        except Exception as e:
            # Database save failed
            workflow_jobs[job_id].status = "failed"
            workflow_jobs[job_id].error = f"Database save failed: {str(e)}"
            workflow_jobs[job_id].estimated_remaining_seconds = 0
            print(f"Database save failed for job {job_id}: {e}")
            return None
        
    except Exception as e:
        # Unexpected error
        workflow_jobs[job_id].status = "failed"
        workflow_jobs[job_id].error = f"Unexpected error: {str(e)}"
        workflow_jobs[job_id].estimated_remaining_seconds = 0
        print(f"Unexpected error in job {job_id}: {e}")
        return None

def sanitize_content(content: str) -> str:
    """Sanitize content to prevent database Unicode errors."""
    if not content:
        return content
    
    # Remove null bytes and other problematic characters
    content = content.replace('\x00', '')  # Remove null bytes
    content = content.replace('\u0000', '')  # Remove Unicode null
    
    # Limit length to prevent overly long content
    if len(content) > 10000:
        content = content[:10000] + "... (truncated)"
    
    # Escape or remove problematic Unicode sequences
    try:
        # Test if content can be safely stored
        content.encode('utf-8')
        return content
    except UnicodeEncodeError:
        # Fallback: remove non-UTF-8 characters
        return content.encode('utf-8', 'ignore').decode('utf-8')

# Usage: Replace the current process_workflow_upload_async with this improved version 