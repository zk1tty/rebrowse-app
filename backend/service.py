import asyncio
import json
import logging
import os
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import requests
from browser_use import Browser
from browser_use.controller.service import Controller
from langchain_openai import ChatOpenAI
from supabase import Client
import aiofiles
import psutil
import subprocess

from workflow_use.controller.service import WorkflowController
from workflow_use.recorder.service import RecordingService
from workflow_use.workflow.service import Workflow
from workflow_use.builder.service import BuilderService

from .dependencies import supabase
from .execution_history_service import get_execution_history_service
from .views import (
	TaskInfo,
	WorkflowAddRequest,
	WorkflowBuildRequest,
	WorkflowBuildResponse,
	WorkflowCancelResponse,
	WorkflowDeleteStepRequest,
	WorkflowExecuteRequest,
	WorkflowMetadataUpdateRequest,
	WorkflowRecordResponse,
	WorkflowResponse,
	WorkflowStatusResponse,
	WorkflowUpdateRequest,
	WorkflowJobStatus,
)

from workflow_use.browser.custom_screensaver import patch_browser_use_screensaver

# Add job tracking at module level
workflow_jobs: Dict[str, WorkflowJobStatus] = {}

# Global task storage for tracking background executions
background_tasks: Dict[str, Dict[str, Any]] = {}

logger = logging.getLogger(__name__)

class WorkflowService:
	"""Workflow execution service."""

	def __init__(self, supabase_client: Client, app=None) -> None:
		self.supabase = supabase_client
		
		# NOTE: Screensaver now implemented on frontend to avoid JavaScript conflicts
		# Frontend shows CSS screensaver until rrweb replayer takes over
		# This eliminates browser-side JavaScript conflicts with rrweb recording
		
		# ---------- Core resources to fetch from local storage ----------
		self.tmp_dir: Path = Path('./tmp')
		self.log_dir: Path = self.tmp_dir / 'logs'
		self.log_dir.mkdir(exist_ok=True, parents=True)

		# LLM / workflow executor
		try:
			self.llm_instance = ChatOpenAI(model='gpt-4.1-mini')
		except Exception as exc:
			print(f'Error initializing LLM: {exc}. Ensure OPENAI_API_KEY is set.')
			self.llm_instance = None

		# Browser configuration for production/Railway
		# Browser instance will be created dynamically based on execution mode
		self.browser_instance = None  # Created per workflow execution with specific mode
		self.controller_instance = WorkflowController()
		self.recording_service = RecordingService(app=app)

		# In‑memory task tracking
		self.active_tasks: Dict[str, TaskInfo] = {}
		self.workflow_tasks: Dict[str, asyncio.Task] = {}
		self.cancel_events: Dict[str, asyncio.Event] = {}

	def _cleanup_browser_profile(self, profile_path: str = None) -> bool:
		"""Clean up browser profile directory to prevent SingletonLock conflicts"""
		try:
			import shutil
			import os
			import subprocess
			import psutil
			
			if not profile_path:
				# Default browser profile path
				profile_path = os.path.expanduser("~/.config/browseruse/profiles/default")
			
			# AGGRESSIVE CLEANUP: Kill any running chromium/browser processes first
			try:
				# Find and kill any chromium processes using the profile directory
				for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
					try:
						if proc.info['name'] and 'chromium' in proc.info['name'].lower():
							if proc.info['cmdline'] and any(profile_path in arg for arg in proc.info['cmdline']):
								logger.warning(f"Killing chromium process {proc.info['pid']} using profile {profile_path}")
								proc.kill()
								proc.wait(timeout=3)  # Wait up to 3 seconds for process to die
					except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
						continue
			except ImportError:
				# psutil not available, try alternative approach
				try:
					# Kill any chromium processes (less precise but works)
					subprocess.run(['pkill', '-f', 'chromium'], check=False, capture_output=True)
					subprocess.run(['pkill', '-f', 'chrome'], check=False, capture_output=True)
				except (subprocess.SubprocessError, FileNotFoundError):
					pass
			
			# Wait a moment for processes to fully terminate
			import time
			time.sleep(1)
			
			if os.path.exists(profile_path):
				# Force remove the entire profile directory
				logger.warning(f"Force removing browser profile directory: {profile_path}")
				try:
					# Try to remove read-only files as well
					def handle_remove_readonly(func, path, exc):
						os.chmod(path, 0o777)
						func(path)
					
					shutil.rmtree(profile_path, onerror=handle_remove_readonly)
					logger.info(f"Successfully cleaned up browser profile at {profile_path}")
					return True
				except Exception as e:
					logger.error(f"Failed to remove profile directory {profile_path}: {e}")
					# Try alternative cleanup
					try:
						subprocess.run(['rm', '-rf', profile_path], check=False, capture_output=True)
						logger.info(f"Alternative cleanup successful for {profile_path}")
						return True
					except:
						pass
			
			return False
		except Exception as e:
			logger.error(f"Error in aggressive browser profile cleanup: {e}")
			return False

	def _create_browser_instance(self, mode: str = "auto") -> Browser:
		"""Create browser instance with specified mode.
		
		Args:
			mode: Browser mode ('cloud-run', 'local-run', or 'auto')
		
		Returns:
			Browser instance configured for the specified mode
		"""
		# Clean up any conflicting browser profiles before creating new instance
		self._cleanup_browser_profile()
		
		logger.info(f"[WorkflowService] Initializing browser in {mode.upper()} mode")
		
		import shutil
		from browser_use.browser.browser import BrowserProfile
		
		# Auto-detect environment if mode is "auto"
		if mode == "auto":
			is_production = os.getenv('RAILWAY_ENVIRONMENT') is not None or os.getenv('RENDER') is not None
			detected_mode = "cloud-run" if is_production else "local-run"
			print(f"[WorkflowService] Auto-detected mode: {detected_mode}")
			mode = detected_mode
		
		if mode == "cloud-run":
			# Cloud/Server configuration - headless
			print("[WorkflowService] Initializing browser in CLOUD-RUN mode (headless)")
			print(f"[WorkflowService] Display: {os.getenv('DISPLAY', 'not set')}")
			
			# Check if Playwright browsers are installed (platform-specific paths)
			playwright_chromium_paths = [
				"/root/.cache/ms-playwright/chromium-1169/chrome-linux/chrome",  # Production Linux
				os.path.expanduser("~/.cache/ms-playwright/chromium-1169/chrome-linux/chrome"),  # Local Linux
				os.path.expanduser("~/Library/Caches/ms-playwright/chromium-1169/chrome-mac/Chromium.app/Contents/MacOS/Chromium"),  # macOS
			]
			
			playwright_chromium_found = False
			for path in playwright_chromium_paths:
				if os.path.exists(path):
					print(f"[WorkflowService] Playwright Chromium found at: {path}")
					playwright_chromium_found = True
					break
			
			if not playwright_chromium_found:
				print(f"[WorkflowService] WARNING: Playwright Chromium not found at any expected path")
				print("[WorkflowService] Searched paths:", playwright_chromium_paths)
				print("[WorkflowService] Make sure 'playwright install chromium' was run")
			
			# Optimized arguments for cloud execution with better navigation support
			base_args = [
					'--no-sandbox',  # Required for Docker/Railway
					'--disable-dev-shm-usage',  # Overcome limited resource problems
					'--disable-web-security',  # Disable web security for automation
					'--disable-features=VizDisplayCompositor',  # Disable compositor
					'--disable-background-timer-throttling',  # Disable background throttling
					'--disable-backgrounding-occluded-windows',
					'--disable-renderer-backgrounding',
					'--disable-extensions',  # Disable extensions for security
					'--no-first-run',  # Skip first run setup
					'--no-default-browser-check',  # Skip default browser check
					'--disable-default-apps',  # Disable default apps
					'--disable-component-update',  # Disable component updates
					'--disable-background-networking',  # Disable background networking
					'--disable-sync',  # Disable sync
					'--metrics-recording-only',  # Disable metrics uploading
					'--no-report-upload',  # Don't upload crash reports
					'--disable-breakpad',  # Disable crash reporting
					# Network and navigation improvements
					'--aggressive-cache-discard',  # Better memory management
					'--enable-automation',  # Enable automation features
					'--disable-blink-features=AutomationControlled',  # Hide automation detection
					'--disable-client-side-phishing-detection',  # Disable phishing detection that can block navigation
					'--disable-features=TranslateUI',  # Disable translate UI
					'--disable-ipc-flooding-protection',  # Allow more IPC messages
					'--max_old_space_size=4096',  # Increase memory limit
			]
			
			# Standard headless configuration with better navigation support
			profile = BrowserProfile(
				headless=True,  # Run without GUI
				disable_security=True,
				keep_alive=False,  # Cloud-run mode: browser will be closed after use
				args=base_args + [
					'--disable-gpu',  # Disable GPU hardware acceleration for headless
					# REMOVED: --single-process (can cause navigation issues)
					'--disable-software-rasterizer',  # Disable software rasterizer
					'--run-all-compositor-stages-before-draw',  # Better rendering
					'--disable-threaded-animation',  # Disable threaded animation
				]
			)
			
			# Let browser-use/Playwright handle the executable path automatically
			return Browser(browser_profile=profile)
			
		elif mode == "local-run":
			# Local user configuration - use their installed Chromium with GUI
			print("[WorkflowService] Initializing browser in LOCAL-RUN mode (user's Chromium)")
			
			# Find user's local Chromium installation
			chromium_paths = [
				'/usr/bin/chromium-browser',
				'/usr/bin/chromium',
				'/usr/bin/google-chrome',
				'/usr/bin/google-chrome-stable',
				'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',  # macOS
			]
			
			chromium_executable = None
			for path in chromium_paths:
				if os.path.exists(path):
					chromium_executable = path
					break
			
			if not chromium_executable:
				# Try using shutil.which
				for name in ['chromium-browser', 'chromium', 'google-chrome', 'google-chrome-stable']:
					found = shutil.which(name)
					if found:
						chromium_executable = found
						break
			
			if chromium_executable:
				print(f"[WorkflowService] Using local Chromium: {chromium_executable}")
			else:
				print("[WorkflowService] WARNING: No local Chromium found, falling back to default")
				print("[WorkflowService] Make sure to install Chrome or Chromium browser")
			
			# Local configuration with GUI enabled and better navigation support
			base_local_args = [
				'--disable-web-security',  # Disable web security for automation
				'--no-first-run',  # Skip first run setup
				'--disable-default-browser-check',  # Skip default browser check
				'--disable-extensions',  # Disable extensions for consistency
				'--enable-automation',  # Enable automation features
				'--disable-blink-features=AutomationControlled',  # Hide automation detection
				'--disable-client-side-phishing-detection',  # Disable phishing detection
				'--disable-features=TranslateUI',  # Disable translate UI
				'--disable-background-networking',  # Disable background networking
				'--disable-sync',  # Disable sync
				'--no-default-browser-check',  # Skip default browser check
				'--disable-component-update',  # Disable component updates
				# Note: Keep --no-sandbox and other container-specific flags out for local use
			]
			
			profile = BrowserProfile(
				headless=False,  # Enable GUI for local development
				disable_security=True,  # Still disable security for automation
				keep_alive=True,  # Local-run mode: keep browser alive for development
				args=base_local_args
			)
			
			return Browser(browser_profile=profile)
		
		else:
			raise ValueError(f"Invalid browser mode: {mode}. Must be 'cloud-run', 'local-run', or 'auto'")

	def _get_timestamp(self) -> str:
		"""Get current timestamp in the format used for logging."""
		return datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

	async def _log_file_position(self) -> int:
		log_file = self.log_dir / 'backend.log'
		if not log_file.exists():
			log_file.write_text('')
			return 0
		return log_file.stat().st_size

	async def _read_logs_from_position(self, position: int) -> Tuple[List[str], int]:
		log_file = self.log_dir / 'backend.log'
		if not log_file.exists():
			return [], 0

		current_size = log_file.stat().st_size
		if position >= current_size:
			return [], position

		with open(log_file, 'r', encoding='utf-8') as f:
			f.seek(position)
			all_logs = f.readlines()
			new_logs = [
				line
				for line in all_logs
				if not line.strip().startswith('INFO:')
				and not line.strip().startswith('WARNING:')
				and not line.strip().startswith('DEBUG:')
				and not line.strip().startswith('ERROR:')
			]
		return new_logs, current_size

	async def _write_log(self, log_file: Path, message: str) -> None:
		"""Write a message to the log file."""
		async with aiofiles.open(log_file, 'a') as f:
			await f.write(message)

	async def _write_error_log(self, log_file: Path, message: str) -> None:
		"""Write an ERROR message with red color and emoji."""
		# ANSI color codes: Red text
		red_color = "\033[91m"
		reset_color = "\033[0m"
		formatted_message = f"{red_color}❌ [{self._get_timestamp()}] ERROR: {message}{reset_color}\n"
		async with aiofiles.open(log_file, 'a') as f:
			await f.write(formatted_message)

	async def _write_warning_log(self, log_file: Path, message: str) -> None:
		"""Write a WARNING message with yellow color and emoji."""
		# ANSI color codes: Yellow text
		yellow_color = "\033[93m"
		reset_color = "\033[0m"
		formatted_message = f"{yellow_color}🚨 [{self._get_timestamp()}] WARNING: {message}{reset_color}\n"
		async with aiofiles.open(log_file, 'a') as f:
			await f.write(formatted_message)

	def _sync_workflow_filename(self, file_path: Path, workflow_content: dict) -> Path:
		"""Synchronize the workflow file name with its internal name."""
		current_name = workflow_content.get('name')
		if not current_name:
			return file_path

		# Check if a file with this name already exists (excluding current file)
		name_exists = False
		for path in self.tmp_dir.iterdir():
			if (path.is_file() and not path.name.startswith('temp_recording') 
				and path != file_path 
				and path.stem == current_name):
				name_exists = True
				break

		if name_exists:
			# If name exists, update both file name and internal name
			new_filename = self._get_next_available_filename(current_name)
			new_name = Path(new_filename).stem  # Get name without extension
			workflow_content['name'] = new_name
			new_file_path = self.tmp_dir / new_filename
			file_path.rename(new_file_path)
			return new_file_path
		elif file_path.stem != current_name:
			# If name doesn't exist but file name doesn't match internal name
			new_filename = f"{current_name}.json"
			new_file_path = self.tmp_dir / new_filename
			file_path.rename(new_file_path)
			return new_file_path

		return file_path
	
	def list_workflows(self) -> List[str]:
		return [f.name for f in self.tmp_dir.iterdir() if f.is_file() and not f.name.startswith('temp_recording')]

	def get_workflow(self, name: str) -> str:
		wf_file = self.tmp_dir / name
		try:
			data = wf_file.read_text()
			workflow_content = json.loads(data)
			
			# If file name doesn't match internal name, sync them
			if workflow_content.get('name') != wf_file.stem:
				wf_file = self._sync_workflow_filename(wf_file, workflow_content)
				# Return the updated file contents as string, not the parsed dict
				return wf_file.read_text()
				
			return data
		except (FileNotFoundError, json.JSONDecodeError):
			return ""

	def update_workflow(self, request: WorkflowUpdateRequest) -> WorkflowResponse:
		workflow_filename = request.filename
		node_id = request.nodeId
		updated_step_data = request.stepData

		if not (workflow_filename and node_id is not None and updated_step_data):
			return WorkflowResponse(success=False, error='Missing required fields')

		# Search through all files in tmp_dir to find the matching workflow
		matching_file = None
		for file_path in self.tmp_dir.iterdir():
			if not file_path.is_file() or file_path.name.startswith('temp_recording'):
				continue
			try:
				workflow_content = json.loads(file_path.read_text())
				if workflow_content.get('name') == workflow_filename:
					matching_file = file_path
					break
			except (json.JSONDecodeError, KeyError):
				continue

		if not matching_file:
			return WorkflowResponse(success=False, error=f"Workflow with name '{workflow_filename}' not found")
		# Load and modify the workflow
		workflow_content = json.loads(matching_file.read_text())
		steps = workflow_content.get('steps', [])

		try:
			node_index = int(node_id)
		except ValueError:
			return WorkflowResponse(success=False, error='Invalid node ID')

		# Updating or adding a step
		if 0 <= node_index < len(steps):
			steps[node_index] = updated_step_data
		elif node_index == len(steps):  # Add new step
			steps.append(updated_step_data)
		else:
			return WorkflowResponse(success=False, error='Node index out of bounds for adding step')

		workflow_content['steps'] = steps
		matching_file.write_text(json.dumps(workflow_content, indent=2))
		return WorkflowResponse(success=True)

	def update_workflow_metadata(self, request: WorkflowMetadataUpdateRequest) -> WorkflowResponse:
		workflow_name = request.name
		updated_metadata = request.metadata

		if not (workflow_name and updated_metadata):
			return WorkflowResponse(success=False, error='Missing required fields')

		# Search through all files in tmp_dir to find the matching workflow
		matching_file = None
		for file_path in self.tmp_dir.iterdir():
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
			print(f"Workflow with name '{workflow_name}' not found")
			return WorkflowResponse(success=False, error=f"Workflow with name '{workflow_name}' not found")

		workflow_content = json.loads(matching_file.read_text())
		
		# Update metadata fields directly from updated_metadata
		if 'name' in updated_metadata:
			workflow_content['name'] = updated_metadata['name']
		if 'description' in updated_metadata:
			workflow_content['description'] = updated_metadata['description']
		if 'workflow_analysis' in updated_metadata:
			workflow_content['workflow_analysis'] = updated_metadata['workflow_analysis']
		if 'version' in updated_metadata:
			workflow_content['version'] = updated_metadata['version']
		if 'input_schema' in updated_metadata:
			workflow_content['input_schema'] = updated_metadata['input_schema']

		# Only sync if the name was updated and is different from current file name
		if 'name' in updated_metadata and updated_metadata['name'] != matching_file.stem:
			matching_file = self._sync_workflow_filename(matching_file, workflow_content)

		matching_file.write_text(json.dumps(workflow_content, indent=2))
		return WorkflowResponse(success=True)
	
	def delete_step(self, request: WorkflowDeleteStepRequest) -> WorkflowResponse:
		workflow_name = request.workflowName
		step_index = request.stepIndex

		if not (workflow_name and step_index):
			return WorkflowResponse(success=False, error='Missing required fields')

		# Search through all files in tmp_dir to find the matching workflow
		matching_file = None
		for file_path in self.tmp_dir.iterdir():
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
			print(f"Workflow with name '{workflow_name}' not found")
			return WorkflowResponse(success=False, error=f"Workflow with name '{workflow_name}' not found")

		if not matching_file:
			return WorkflowResponse(success=False, error="Workflow not found")

		workflow_content = json.loads(matching_file.read_text())
		steps = workflow_content.get('steps', [])

		if 0 <= step_index < len(steps):
			del steps[step_index]
			workflow_content['steps'] = steps
			matching_file.write_text(json.dumps(workflow_content, indent=2))
			return WorkflowResponse(success=True)

		return WorkflowResponse(success=False, error="Invalid step index")

	async def run_workflow_in_background(
		self,
		task_id: str,
		request: WorkflowExecuteRequest,
		cancel_event: asyncio.Event,
	) -> None:
		"""Run workflow in background with task tracking."""
		log_file = self.log_dir / f'task_{task_id}.log'
		
		try:
			# Initialize task info
			task_info = TaskInfo(
				status='running',
				workflow=request.name,
				result=None,
				error=None,
			)
			self.active_tasks[task_id] = task_info

			await self._write_log(log_file, f'[{self._get_timestamp()}] ▶️Starting workflow execution: {request.name}\n')
			await self._write_log(log_file, f'[{self._get_timestamp()}] Mode: {request.mode}\n')
			await self._write_log(log_file, f'[{self._get_timestamp()}] Visual feedback: {request.visual}\n')

			# Create browser instance with appropriate mode
			browser_instance = self._create_browser_instance(
				mode=request.mode
			)
			
			# Store browser instance for potential cleanup
			self.browser_instance = browser_instance

			# Load workflow from file
			workflow_path = self.tmp_dir / request.name
			if not workflow_path.exists():
				raise FileNotFoundError(f'Workflow file not found: {request.name}')

			workflow_content = json.loads(workflow_path.read_text())
			
			await self._write_log(log_file, f'[{self._get_timestamp()}] Workflow loaded: {workflow_content.get("name", "Unknown")}\n')

			# Create workflow instance
			workflow = Workflow.load_from_file(
				workflow_path,
				browser=browser_instance,
				llm=self.llm_instance,
				controller=self.controller_instance,
			)

			await self._write_log(log_file, f'[{self._get_timestamp()}] Workflow instance created\n')

			# Execute workflow
			result = await workflow.run(
				inputs=request.inputs,
				close_browser_at_end=True,
				cancel_event=cancel_event,
			)

			await self._write_log(log_file, f'[{self._get_timestamp()}] Workflow execution completed successfully\n')

			# Update task status
			task_info.status = 'completed'
			task_info.result = result.model_dump() if hasattr(result, 'model_dump') else str(result)

		except asyncio.CancelledError:
			await self._write_log(log_file, f'[{self._get_timestamp()}] Workflow execution cancelled\n')
			if task_id in self.active_tasks:
				self.active_tasks[task_id].status = 'cancelled'
			raise
		except Exception as exc:
			error_msg = f'Workflow execution failed: {exc}'
			await self._write_log(log_file, f'[{self._get_timestamp()}] {error_msg}\n')
			if task_id in self.active_tasks:
				self.active_tasks[task_id].status = 'failed'
				self.active_tasks[task_id].error = str(exc)
			print(f'[WorkflowService] Error in workflow execution: {exc}')
		finally:
			# Cleanup browser instance
			if hasattr(self, 'browser_instance') and self.browser_instance:
				try:
					await self.browser_instance.close()
					self.browser_instance = None
					await self._write_log(log_file, f'[{self._get_timestamp()}] Browser instance closed\n')
				except Exception as e:
					await self._write_error_log(log_file, f'Error closing browser: {e}')

	async def run_workflow_session_with_visual_streaming(
		self,
		task_id: str,
		workflow_id: str,
		inputs: dict,
		cancel_event: asyncio.Event,
		owner_id: Optional[str] = None,
		mode: str = "cloud-run",
		visual: bool = False,
		visual_streaming: bool = False,
		visual_quality: str = "standard",
		visual_events_buffer: int = 1000,
	) -> None:
		"""Execute a workflow from database with enhanced visual streaming support using rrweb."""
		log_file = self.log_dir / 'backend.log'
		temp_file = None
		session_id = f"visual-{task_id}"
		execution_start_time = time.time()
		execution_id = None
		
		# Get execution history service for tracking
		from backend.execution_history_service import get_execution_history_service
		execution_service = get_execution_history_service(self.supabase)
		
		# 🔧 CRITICAL FIX: Create visual streaming session IMMEDIATELY to avoid "Session not found" errors
		if visual_streaming and session_id:
			try:
				from backend.visual_streaming import streaming_manager
				# Create the session immediately so frontend polling works
				streamer = streaming_manager.get_or_create_streamer(session_id)
				await streamer.start_streaming()
				await self._write_log(log_file, f'[{self._get_timestamp()}] Visual streaming session created early for frontend polling: {session_id}\n')
			except Exception as e:
				await self._write_warning_log(log_file, f'Failed to create early visual streaming session: {e}')
		
		try:
			# Fetch workflow from database
			workflow_data = self.get_workflow_by_id(workflow_id)
			if not workflow_data:
				raise ValueError(f"Workflow {workflow_id} not found in database")
			
			# Verify ownership if owner_id provided
			if owner_id and workflow_data.get('owner_id') and workflow_data.get('owner_id') != owner_id:
				raise ValueError(f"Access denied: User {owner_id} does not own workflow {workflow_id}")
			
			workflow_name = workflow_data.get('name', f'workflow_{workflow_id}')
			
			# STEP 1: Create execution record in database
			try:
				execution_id = await execution_service.create_execution_record(
					workflow_id=workflow_id,
					user_id=owner_id,
					inputs=inputs,
					mode=mode,
					visual_enabled=visual,
					visual_streaming_enabled=visual_streaming,
					visual_quality=visual_quality,
					session_id=session_id if visual_streaming else None
				)
				await self._write_log(log_file, f"[{self._get_timestamp()}] Created execution record: {execution_id}\n")
			except Exception as e:
				await self._write_warning_log(log_file, f"Failed to create execution record: {e}")
				# Continue execution even if database tracking fails
			
			# Initialize task info with visual streaming fields
			from backend.views import TaskInfo
			task_info = TaskInfo(
				status='running',
				workflow=workflow_name,
				result=None,
				error=None,
			)
			
			# Add visual streaming URLs if enabled
			if visual_streaming and session_id:
				task_info.visual_stream_url = f"/workflows/visual/{session_id}/stream"
				task_info.viewer_url = f"/workflows/visual/{session_id}/viewer"
			
			self.active_tasks[task_id] = task_info

			await self._write_log(log_file, f"[{self._get_timestamp()}] ▶️Starting enhanced session workflow '{workflow_name}' (ID: {workflow_id})\n")
			await self._write_log(log_file, f'[{self._get_timestamp()}] Mode: {mode}\n')
			await self._write_log(log_file, f'[{self._get_timestamp()}] Visual feedback: {visual}\n')
			await self._write_log(log_file, f'[{self._get_timestamp()}] Visual streaming: {visual_streaming}\n')
			await self._write_log(log_file, f'[{self._get_timestamp()}] Session ID: {session_id}\n')
			await self._write_log(log_file, f'[{self._get_timestamp()}] Visual quality: {visual_quality}\n')
			await self._write_log(log_file, f'[{self._get_timestamp()}] Execution ID: {execution_id}\n')
			await self._write_log(log_file, f'[{self._get_timestamp()}] Input parameters: {json.dumps(inputs)}\n')

			if cancel_event.is_set():
				await self._write_log(log_file, f'[{self._get_timestamp()}] Workflow cancelled before execution\n')
				self.active_tasks[task_id].status = 'cancelled'
				# Update execution record
				if execution_id:
					await execution_service.update_execution_status(execution_id, status='cancelled')
				return

			# Create temporary workflow file
			temp_file = self.tmp_dir / f"temp_session_{task_id}_{workflow_id}.json"
			temp_file.write_text(json.dumps(workflow_data))
			
			await self._write_log(log_file, f'[{self._get_timestamp()}] Created temporary workflow file: {temp_file.name}\n')

			# Create browser instance for workflow execution
			browser = None
			browser_for_workflow = None
			visual_browser = None
			
			# Initialize visual streaming if enabled
			visual_events_captured = 0
			visual_stream_start_time = time.time()
			
			if visual_streaming and session_id:
				try:
					# Import new architecture components
					from backend.visual_streaming import streaming_manager
					from workflow_use.browser.browser_factory import browser_factory
					
					# Get or create streamer for session
					streamer = streaming_manager.get_or_create_streamer(session_id)
					await streamer.start_streaming()
					await self._write_log(log_file, f'[{self._get_timestamp()}] Visual streaming initialized for session: {session_id}\n')
					
					# Create streaming callback that feeds into our streaming system with consistent format handling
					async def streaming_callback(event_data):
						nonlocal visual_events_captured
						try:
							# FIXED: Consistently handle event format - RRWebRecorder always sends {'event': rrweb_event}
							if isinstance(event_data, dict) and 'event' in event_data:
								# Extract the actual rrweb event from the wrapper
								actual_rrweb_event = event_data['event']
								await streamer.process_rrweb_event(actual_rrweb_event)
							else:
								# Fallback: if raw event data is received (shouldn't happen with new architecture)
								logger.warning(f"Received raw event data instead of wrapped format: {type(event_data)}")
								await streamer.process_rrweb_event(event_data)
							visual_events_captured += 1
						except Exception as e:
							await self._write_error_log(log_file, f'Error in streaming callback: {e}')
					
					# Create browser + recorder using new architecture
					await self._write_log(log_file, f'[{self._get_timestamp()}] Creating browser with rrweb using new architecture...\n')
					browser_for_workflow, rrweb_recorder = await browser_factory.create_browser_with_rrweb(
						mode='visual',
						session_id=session_id,
						event_callback=streaming_callback,
						headless=True
					)
					
					# Attach recorder to browser for controller access
					browser_for_workflow._rrweb_recorder = rrweb_recorder
					
					await self._write_log(log_file, f'[{self._get_timestamp()}] ✅ Browser + RRWebRecorder created using new architecture\n')
					
					# Start rrweb recording
					await self._write_log(log_file, f'[{self._get_timestamp()}] Starting rrweb recording...\n')
					recording_success = await rrweb_recorder.start_recording()
					
					if recording_success:
						await self._write_log(log_file, f'[{self._get_timestamp()}] ✅ rrweb recording started successfully\n')
						
						# Phase management: Transition to READY phase
						await streamer.transition_to_ready()
						await self._write_log(log_file, f'[{self._get_timestamp()}] 🔄 Phase transition: SETUP → READY\n')
						
						# CRITICAL FIX: Keep navigation monitoring disabled during READY phase
						# This prevents screensaver recording interruption
						await rrweb_recorder.set_phase("READY")
						await self._write_log(log_file, f'[{self._get_timestamp()}] 🔕 Navigation monitoring disabled during READY phase\n')
						
						# Wait briefly for recording to stabilize
						await asyncio.sleep(0.5)
					else:
						await self._write_error_log(log_file, f'Failed to start rrweb recording')
						raise RuntimeError("Failed to start rrweb recording")
					
				except ImportError as e:
					error_msg = f'Visual streaming components not available: {e}'
					await self._write_error_log(log_file, error_msg)
					raise RuntimeError(f"Visual streaming setup failed: {error_msg}")
				except Exception as e:
					error_msg = f'Failed to create visual streaming setup: {e}'
					await self._write_error_log(log_file, error_msg)
					raise RuntimeError(f"Visual streaming initialization failed: {error_msg}")
			else:
				# No visual streaming: create regular browser
				browser = self._create_browser_instance(mode=mode)
				await self._write_log(log_file, f'[{self._get_timestamp()}] Browser instance created in {mode} mode\n')
				await browser.start()
				await self._write_log(log_file, f'[{self._get_timestamp()}] Browser started successfully\n')
				browser_for_workflow = browser

			# Execute workflow
			await self._write_log(log_file, f'[{self._get_timestamp()}] ▶️Starting workflow execution...\n')
			
			# 🔧 PHASE MANAGEMENT: Transition to EXECUTING phase (workflow execution starting)
			# CRITICAL FIX: Do this ONLY once to prevent duplicate phase transitions
			if visual_streaming and session_id:
				try:
					from backend.visual_streaming import streaming_manager
					streamer = streaming_manager.get_streamer(session_id)
					if streamer:
						await streamer.transition_to_executing()
						await self._write_log(log_file, f'[{self._get_timestamp()}] 🔄 Phase transition: READY → EXECUTING\n')
						
						# CRITICAL FIX: Enable navigation monitoring ONLY during actual workflow execution
						# NOT during screensaver phase to prevent recording restart
						await rrweb_recorder.set_phase("EXECUTING")
						await self._write_log(log_file, f'[{self._get_timestamp()}] 🔊 Navigation monitoring enabled for EXECUTING phase\n')
				except Exception as e:
					await self._write_warning_log(log_file, f'Failed to transition to executing phase: {e}')
			
			# Controller access is already handled via _rrweb_recorder attribute
			
			# Load workflow using the correct method
			from workflow_use.workflow.service import Workflow
			workflow = Workflow.load_from_file(
				str(temp_file),
				browser=browser_for_workflow,
				llm=self.llm_instance
			)
			
			# Check for cancellation before execution
			if cancel_event.is_set():
				await self._write_log(log_file, f'[{self._get_timestamp()}] Workflow cancelled before execution start\n')
				self.active_tasks[task_id].status = 'cancelled'
				if execution_id:
					await execution_service.update_execution_status(execution_id, status='cancelled')
				return

			# Execute the workflow with the appropriate browser
			# CRITICAL FIX: Don't close browser at end if visual streaming is enabled
			close_browser_at_end = not visual_streaming  # Keep browser alive for visual streaming cleanup
			result = await workflow.run(inputs, close_browser_at_end=close_browser_at_end)
			
			# 🔧 PHASE MANAGEMENT: Transition to COMPLETED phase (workflow execution finished)
			if visual_streaming and session_id:
				try:
					from backend.visual_streaming import streaming_manager
					streamer = streaming_manager.get_streamer(session_id)
					if streamer:
						await streamer.transition_to_completed()
						await self._write_log(log_file, f'[{self._get_timestamp()}] 🔄 Phase transition: EXECUTING → COMPLETED\n')
						
						# CRITICAL FIX: Disable navigation monitoring after workflow completion
						await rrweb_recorder.set_phase("COMPLETED")
						await self._write_log(log_file, f'[{self._get_timestamp()}] 🔕 Navigation monitoring disabled after COMPLETED phase\n')
				except Exception as e:
					await self._write_warning_log(log_file, f'Failed to transition to completed phase: {e}')
			
			# Calculate execution metrics
			execution_end_time = time.time()
			execution_time_seconds = execution_end_time - execution_start_time
			visual_stream_duration = execution_end_time - visual_stream_start_time if visual_streaming else None
			
			await self._write_log(log_file, f'[{self._get_timestamp()}] Workflow execution completed successfully\n')
			await self._write_log(log_file, f'[{self._get_timestamp()}] Execution time: {execution_time_seconds:.2f} seconds\n')
			if visual_streaming:
				await self._write_log(log_file, f'[{self._get_timestamp()}] Visual events captured: {visual_events_captured}\n')
				if visual_stream_duration:
					await self._write_log(log_file, f'[{self._get_timestamp()}] Visual stream duration: {visual_stream_duration:.2f} seconds\n')

			# Update task status
			task_info = self.active_tasks[task_id]
			task_info.status = 'completed'
			# Convert result to serializable format for TaskInfo
			if hasattr(result, 'step_results'):
				task_info.result = [{"step_id": i, "content": str(step)} for i, step in enumerate(result.step_results)]
			else:
				task_info.result = [{"step_id": 0, "content": str(result)}]

			# Update execution record with results
			if execution_id:
				try:
					# Get logs for database storage
					logs_content = []
					try:
						if log_file.exists():
							with open(log_file, 'r') as f:
								all_logs = f.read()
						# Extract logs related to this execution (simplified)
						logs_content = [line.strip() for line in all_logs.split('\n') if line.strip()][-100:]  # Last 100 lines
					except Exception as log_error:
						await self._write_warning_log(log_file, f'Could not extract logs for database: {log_error}')
					
					await execution_service.update_execution_status(
						execution_id=execution_id,
						status='completed',
						result=task_info.result,
						execution_time_seconds=execution_time_seconds,
						visual_events_captured=visual_events_captured if visual_streaming else None,
						visual_stream_duration=visual_stream_duration,
						logs=logs_content
					)
					await self._write_log(log_file, f'[{self._get_timestamp()}] Execution record updated successfully\n')
				except Exception as e:
					await self._write_warning_log(log_file, f'Failed to update execution record: {e}')

			await self._write_log(log_file, f'[{self._get_timestamp()}] Session workflow completed: {workflow_name}\n')

		except asyncio.CancelledError:
			await self._write_log(log_file, f'[{self._get_timestamp()}] Session workflow force‑cancelled\n')
			self.active_tasks[task_id].status = 'cancelled'
			if execution_id:
				await execution_service.update_execution_status(execution_id, status='cancelled')
			
			# Mark browser not ready on cancellation
			if visual_streaming and session_id:
				try:
					from backend.visual_streaming import streaming_manager
					streamer = streaming_manager.get_streamer(session_id)
					if streamer:
						await streamer.transition_to_cleanup()
						await self._write_log(log_file, f'[{self._get_timestamp()}] 🔄 Phase transition: → CLEANUP (cancellation)\n')
				except Exception as e:
					await self._write_warning_log(log_file, f'Error transitioning to cleanup on cancellation: {e}')
			
			raise
		except Exception as exc:
			execution_end_time = time.time()
			execution_time_seconds = execution_end_time - execution_start_time
			
			await self._write_error_log(log_file, f'[{self._get_timestamp()}] Session workflow error: {exc}\n')
			self.active_tasks[task_id].status = 'failed'
			self.active_tasks[task_id].error = str(exc)

			# Mark browser not ready on error
			if visual_streaming and session_id:
				try:
					from backend.visual_streaming import streaming_manager
					streamer = streaming_manager.get_streamer(session_id)
					if streamer:
						await streamer.transition_to_cleanup()
						await self._write_log(log_file, f'[{self._get_timestamp()}] 🔄 Phase transition: → CLEANUP (error)\n')
				except Exception as mark_error:
					await self._write_warning_log(log_file, f'Error transitioning to cleanup on error: {mark_error}\n')
			
			# Update execution record with error
			if execution_id:
				try:
					# Get error logs
					logs_content = []
					try:
						if log_file.exists():
							with open(log_file, 'r') as f:
								all_logs = f.read()
							logs_content = [line.strip() for line in all_logs.split('\n') if line.strip()][-100:]
					except Exception:
						pass
					
					await execution_service.update_execution_status(
						execution_id=execution_id,
						status='failed',
						error=str(exc),
						execution_time_seconds=execution_time_seconds,
						visual_events_captured=visual_events_captured if visual_streaming else None,
						logs=logs_content
					)
					await self._write_log(log_file, f'[{self._get_timestamp()}] Execution record updated with error\n')
				except Exception as update_error:
					await self._write_warning_log(log_file, f'Failed to update execution record with error: {update_error}')
		finally:
			# Clean up temporary file
			if temp_file and temp_file.exists():
				try:
					temp_file.unlink()
					await self._write_log(log_file, f'[{self._get_timestamp()}] Cleaned up temporary file: {temp_file.name}\n')
				except Exception as e:
					await self._write_warning_log(log_file, f'Failed to cleanup temp file {temp_file.name}: {e}\n')
			
			# Clean up visual streaming if it was initialized
			if visual_streaming and session_id:
				try:
					# Clean up streaming manager FIRST, before browser cleanup
					from backend.visual_streaming import streaming_manager
					streamer = streaming_manager.get_streamer(session_id)
					if streamer:
						# 🔧 PHASE MANAGEMENT: Transition to CLEANUP phase (browser cleanup starting)
						await streamer.transition_to_cleanup()
						await self._write_log(log_file, f'[{self._get_timestamp()}] 🔄 Phase transition: COMPLETED → CLEANUP\n')
						
						# Add delay BEFORE cleanup to allow frontend to receive final events
						await self._write_log(log_file, f'[{self._get_timestamp()}] Keeping session alive for frontend connection: {session_id}\n')
						await asyncio.sleep(10)  # Give frontend 10 seconds to receive final events
						
						# Give additional time for WebSocket to gracefully disconnect
						await asyncio.sleep(3)
						
						# 🔧 FINAL CLEANUP: Now mark browser as not ready and stop streaming
						await streamer.final_cleanup()
						await streamer.stop_streaming()
						await self._write_log(log_file, f'[{self._get_timestamp()}] Visual streaming stopped for session {session_id}\n')
					
					# RRWebRecorder cleanup is handled automatically by browser_factory
					
				except Exception as e:
					await self._write_warning_log(log_file, f'Error stopping visual streaming: {e}\n')

			# Cleanup browser instance (only if it's the regular browser, not the visual browser)
			if browser and browser != browser_for_workflow:
				try:
					await browser.close()
					await self._write_log(log_file, f'[{self._get_timestamp()}] Regular browser instance closed\n')
				except Exception as e:
					await self._write_warning_log(log_file, f'Error closing regular browser: {e}\n')

	def add_workflow(self, request: WorkflowAddRequest) -> WorkflowResponse:
		"""Add a new workflow file."""
		if not request.name or not request.content:
			return WorkflowResponse(success=False, error='Missing required fields')

		# Create new workflow file with collision handling
		try:
			workflow_file = self.tmp_dir / self._get_next_available_filename(request.name)
			workflow_file.write_text(request.content)
			return WorkflowResponse(success=True)
		except Exception as e:
			return WorkflowResponse(success=False, error=f'Error creating workflow: {str(e)}')

	def delete_workflow(self, name: str) -> WorkflowResponse:
		"""Delete a workflow file."""
		if not name:
			return WorkflowResponse(success=False, error='Missing workflow name')

		# Find and delete the workflow file
		for file_path in self.tmp_dir.iterdir():
			if not file_path.is_file() or file_path.name.startswith('temp_recording'):
				continue
			try:
				workflow_content = json.loads(file_path.read_text())
				if workflow_content.get('name') == name:
					file_path.unlink()
					return WorkflowResponse(success=True)
			except (json.JSONDecodeError, KeyError):
				continue

		return WorkflowResponse(success=False, error=f"Workflow '{name}' not found")

	async def record_workflow(self) -> WorkflowRecordResponse:
		"""Record a new workflow using the recording service."""
		try:
			workflow_data = await self.recording_service.record_workflow_using_main_server()
			return WorkflowRecordResponse(success=True, workflow=workflow_data)
		except Exception as e:
			print(f'Error recording workflow: {e}')
			return WorkflowRecordResponse(success=False, workflow=None, error=str(e))

	async def cancel_recording(self) -> WorkflowRecordResponse:
		"""Cancel an ongoing workflow recording."""
		try:
			await self.recording_service.cancel_recording()
			return WorkflowRecordResponse(success=True, workflow=None)
		except Exception as e:
			print(f'Error cancelling recording: {e}')
			return WorkflowRecordResponse(success=False, workflow=None, error=str(e))

	async def cancel_workflow(self, task_id: str) -> WorkflowCancelResponse:
		"""Cancel a running workflow task."""
		try:
			# Check if task exists
			if task_id not in self.active_tasks:
				return WorkflowCancelResponse(
					success=False,
					message='Task not found'
				)
			
			# Check if task is already completed or cancelled
			task_info = self.active_tasks[task_id]
			if task_info.status in ['completed', 'cancelled', 'failed']:
				return WorkflowCancelResponse(
					success=False,
					message=f'Task {task_id} is already {task_info.status} and cannot be cancelled'
				)
			
			# Signal cancellation if cancel event exists
			if task_id in self.cancel_events:
				cancel_event = self.cancel_events[task_id]
				cancel_event.set()  # Signal the running task to cancel
				
				# Update task status
				task_info.status = 'cancelling'
				
				return WorkflowCancelResponse(
					success=True,
					message=f'Cancellation signal sent to task {task_id}'
				)
			else:
				# Task exists but no cancel event (shouldn't happen in normal operation)
				task_info.status = 'cancelled'
				return WorkflowCancelResponse(
					success=True,
					message=f'Task {task_id} marked as cancelled (no active execution found)'
				)
				
		except Exception as e:
			print(f'Error cancelling workflow {task_id}: {e}')
			return WorkflowCancelResponse(
				success=False,
				message=f'Error cancelling workflow: {str(e)}'
			)

	def _get_next_available_filename(self, base_name: str) -> str:
		"""Get the next available filename by adding incremental numbers."""
		counter = 1
		file_name = f'{base_name}.json'
		while (self.tmp_dir / file_name).exists():
			file_name = f'{base_name}{counter}.json'
			counter += 1
		return file_name

	async def build_workflow(self, request: WorkflowBuildRequest) -> WorkflowBuildResponse:
		"""Build a workflow from the edited recording."""
		try:
			if not self.llm_instance:
				return WorkflowBuildResponse(
					success=False,
					message='Failed to build workflow',
					error='LLM instance not available. Please ensure OPENAI_API_KEY is set.',
				)

			# Initialize the builder service with the LLM instance
			builder_service = BuilderService(llm=self.llm_instance)

			# Build the workflow using the builder service
			built_workflow = await builder_service.build_workflow(
				input_workflow=request.workflow,
				user_goal=request.prompt,
				use_screenshots=False,  # TODO: We don't need screenshots for now
			)

			# Set timestamps for steps that don't have them
			current_time = int(time.time() * 1000)  # Current time in milliseconds
			has_timestamp = False
			for step in built_workflow.steps:
				if hasattr(step, 'type') and step.type != 'agent' and hasattr(step, 'timestamp') and step.timestamp is not None:
					has_timestamp = True
					break
			if not has_timestamp:
				for step in built_workflow.steps:
					if hasattr(step, 'type') and step.type != 'agent' and hasattr(step, 'timestamp'):
						step.timestamp = current_time

			# Handle workflow name
			if not request.name:
				workflow_name = built_workflow.name
			else:
				built_workflow.name = request.name
				workflow_name = request.name

			# Save the built workflow to the final location with collision handling
			final_file = self.tmp_dir / self._get_next_available_filename(workflow_name)
			final_file.write_text(built_workflow.model_dump_json(indent=2))

			return WorkflowBuildResponse(success=True, message=f"Workflow '{final_file.stem}' built successfully")
		except Exception as e:
			print(f'Error building workflow: {e}')
			return WorkflowBuildResponse(success=False, message='Failed to build workflow', error=str(e))

	def get_workflow_by_id(self, workflow_id: str) -> Optional[Dict[str, Any]]:
		"""Fetch workflow from database by ID."""
		try:
			response = self.supabase.table('workflows').select('*').eq('id', workflow_id).execute()
			
			if response.data and len(response.data) > 0:
				return response.data[0]
			else:
				logger.warning(f"No workflow found with ID: {workflow_id}")
				return None
				
		except Exception as e:
			logger.error(f"Error fetching workflow {workflow_id}: {e}")
			return None


# ─── Supabase Service Helpers ────────
def list_all_workflows(limit: int = 100):
	"""Fetch all workflows from Supabase database in read-only mode."""
	if not supabase:
		raise Exception("Supabase client not configured")
		
	return supabase.from_("workflows")           \
	               .select("*")                  \
	               .order("created_at", desc=True) \
	               .limit(limit)                 \
	               .execute().data


async def get_workflow_by_id(workflow_id: str):
	"""Get single workflow by UUID with proper error handling."""
	if not supabase:
		raise Exception("Supabase client not configured")
	
	try:
		result = supabase.from_("workflows") \
		               .select("*") \
		               .eq("id", workflow_id) \
		               .execute()
		
		# Check if any data was returned
		if not result.data or len(result.data) == 0:
			return None
			
		return result.data[0]  # Return the first (and only) result
		
	except Exception as e:
		# Log the error but don't expose internal details
		print(f"Database error retrieving workflow {workflow_id}: {e}")
		raise Exception("Failed to retrieve workflow")


def sanitize_content(content: str | None) -> str:
	"""Sanitize content to prevent database Unicode errors."""
	if not content:
		return content or ""
	
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


async def build_workflow_from_recording_data(recording_data: dict, user_goal: str, workflow_name: Optional[str] = None):
	"""Build a workflow from recording JSON data using BuilderService."""
	try:
		# Initialize the builder service with the LLM instance
		if not hasattr(build_workflow_from_recording_data, '_builder_service'):
			from langchain_openai import ChatOpenAI
			llm_instance = ChatOpenAI(model='gpt-4o')
			build_workflow_from_recording_data._builder_service = BuilderService(llm=llm_instance)
		
		builder_service = build_workflow_from_recording_data._builder_service
		
		# Validate and convert recording data to WorkflowDefinitionSchema
		from workflow_use.schema.views import WorkflowDefinitionSchema
		recording_schema = WorkflowDefinitionSchema.model_validate(recording_data)
		
		# Build the workflow using the builder service
		built_workflow = await builder_service.build_workflow(
			input_workflow=recording_schema,
			user_goal=user_goal,
			use_screenshots=False,  # Disabled for faster demo processing
			max_images=0  # No images for faster processing
		)
		
		# Use LLM-generated name first, fallback to provided name
		if not built_workflow.name or built_workflow.name.strip() == "":
			built_workflow.name = workflow_name or "New Workflow"
			
		# Set timestamps for steps that don't have them
		import time
		current_time = int(time.time() * 1000)  # Current time in milliseconds
		has_timestamp = False
		for step in built_workflow.steps:
			if hasattr(step, 'type') and step.type != 'agent' and hasattr(step, 'timestamp') and step.timestamp is not None:
				has_timestamp = True
				break
		if not has_timestamp:
			for step in built_workflow.steps:
				if hasattr(step, 'type') and step.type != 'agent' and hasattr(step, 'timestamp'):
					step.timestamp = current_time
		
		return built_workflow
		
	except Exception as e:
		print(f'Error building workflow from recording: {e}')
		raise Exception(f"Failed to build workflow: {str(e)}")


async def process_workflow_upload_async(job_id: str, recording_data: dict, user_goal: str, workflow_name: Optional[str] = None, owner_id: Optional[str] = None):
	"""Process workflow upload with improved error handling and granular progress updates."""
	import asyncio
	
	# Progress updater for granular progress during conversion
	async def update_progress_gradually(start_progress: int, end_progress: int, max_duration: float):
		"""Update progress every 10% with shorter intervals for responsiveness"""
		progress_points = list(range(start_progress + 10, end_progress, 10))  # [20, 30, 40, 50, 60, 70]
		if not progress_points:
			return
			
		# Update every 0.8 seconds for responsiveness
		update_interval = 0.8
		
		for target_progress in progress_points:
			await asyncio.sleep(update_interval)
			if job_id in workflow_jobs and workflow_jobs[job_id].progress < target_progress:
				workflow_jobs[job_id].progress = target_progress
				# Estimate remaining time based on current progress
				progress_ratio = target_progress / end_progress
				remaining_time = max(2, int(max_duration * (1 - progress_ratio)))
				workflow_jobs[job_id].estimated_remaining_seconds = remaining_time
	
	try:
		# Update job status: Starting conversion
		workflow_jobs[job_id].status = "processing"
		workflow_jobs[job_id].progress = 10
		workflow_jobs[job_id].estimated_remaining_seconds = 25
		
		# Step 1: Convert recording to workflow (this takes time)
		try:
			# Start gradual progress updates during conversion (10% → 80%)
			progress_task = asyncio.create_task(
				update_progress_gradually(start_progress=10, end_progress=80, max_duration=15)
			)
			
			# Run conversion and progress updates concurrently
			conversion_task = asyncio.create_task(build_workflow_from_recording_data(
				recording_data=recording_data,
				user_goal=user_goal,
				workflow_name=workflow_name
			))
			
			# Wait for conversion to complete
			built_workflow = await conversion_task
			
			# Cancel progress updater and set final conversion progress
			progress_task.cancel()
			try:
				await progress_task
			except asyncio.CancelledError:
				pass
			
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
			
			# Gradual progress during database operations (80% → 100%)
			workflow_jobs[job_id].progress = 85
			workflow_jobs[job_id].estimated_remaining_seconds = 3
			await asyncio.sleep(0.3)  # Brief pause to make progress visible
			
			from datetime import datetime
			now = datetime.utcnow().isoformat()
			
			# Progress: Sanitizing content
			workflow_jobs[job_id].progress = 90
			workflow_jobs[job_id].estimated_remaining_seconds = 2
			await asyncio.sleep(0.2)  # Brief pause
			
			# Sanitize content before database insertion
			sanitized_steps = []
			for step in built_workflow.steps:
				step_dict = step.model_dump()
				# Remove or sanitize problematic Unicode characters
				if 'content' in step_dict and step_dict['content']:
					step_dict['content'] = sanitize_content(step_dict['content'])
				sanitized_steps.append(step_dict)
			
			# Progress: Inserting into database
			workflow_jobs[job_id].progress = 95
			workflow_jobs[job_id].estimated_remaining_seconds = 1
			await asyncio.sleep(0.2)  # Brief pause
			
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


async def start_workflow_upload_job(recording_data: dict, user_goal: str, workflow_name: Optional[str] = None, owner_id: Optional[str] = None) -> str:
	"""Start an async workflow upload job and return job ID."""
	job_id = str(uuid4())
	
	# Initialize job status
	workflow_jobs[job_id] = WorkflowJobStatus(
		job_id=job_id,
		status="processing",
		progress=0,
		estimated_remaining_seconds=30
	)
	
	# Start background task (fire and forget)
	import asyncio
	asyncio.create_task(process_workflow_upload_async(job_id, recording_data, user_goal, workflow_name, owner_id))
	
	return job_id


def get_workflow_job_status(job_id: str) -> Optional[WorkflowJobStatus]:
	"""Get the current status of a workflow upload job."""
	return workflow_jobs.get(job_id)
