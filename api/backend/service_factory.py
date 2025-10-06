import logging
from typing import Optional

from .dependencies import supabase
from .service import WorkflowService

logger = logging.getLogger(__name__)

_service: Optional[WorkflowService] = None

def get_service(app=None) -> WorkflowService:
	global _service
	if _service is None:
		if supabase is None:
			raise RuntimeError("Supabase client not initialized. Please check your environment variables.")
		_service = WorkflowService(supabase_client=supabase, app=app)
	return _service


