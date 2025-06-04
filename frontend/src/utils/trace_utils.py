from pathlib import Path
import json
import logging
from typing import List

logger = logging.getLogger(__name__)

# Helper function to extract file upload names from a trace
def get_upload_file_names_from_trace(trace_path: str) -> List[str]:
    """Reads a .jsonl trace file and extracts unique file_name values from file_upload events."""
    upload_file_names = set()
    try:
        if Path(trace_path).exists():
            with open(trace_path, 'r') as f:
                for line in f:
                    if line.strip():
                        try:
                            event = json.loads(line)
                            if event.get("type") == "file_upload" and event.get("file_name"):
                                upload_file_names.add(event["file_name"])
                        except json.JSONDecodeError:
                            logger.warning(f"Skipping invalid JSON line in trace {trace_path}: {line.strip()}")
        else:
            logger.warning(f"Trace file not found for extracting upload names: {trace_path}")
    except Exception as e:
        logger.error(f"Error reading or parsing trace file {trace_path} for upload names: {e}")
    return sorted(list(upload_file_names))

# Add this function at an appropriate place in your webui.py, 
# or in a utility file imported by webui.py.
# Ensure necessary imports are present: from pathlib import Path, import json, import logging, from typing import List 