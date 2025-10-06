"""
RunEventsHub: per-run step state, snapshot builder, and in-process pub/sub.

Responsibilities:
- Maintain per-run step states and summary
- Provide canonical Snapshot per the agreed schema
- Emit ordered (seq) live events to local subscribers (WS layer will subscribe)

Notes:
- This module is transport-agnostic (no FastAPI/WS import)
- Pub/Sub is local-process; cross-worker fanout can be added later via Redis
"""

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set


logger = logging.getLogger(__name__)


# Step status constants
STATUS_READY = "ready"
STATUS_RUNNING = "running"
STATUS_FALLBACK = "AI-fallback"
STATUS_SUCCESS = "success"
STATUS_FAIL = "fail"


@dataclass
class StepState:
    """State for a single step within a run (run-scoped)."""
    step_id: str
    static_step_key: str
    step_index: int
    total_steps: int
    title: str
    status: str = STATUS_READY
    source_flags: Dict[str, bool] = field(default_factory=lambda: {"workflowUse": False, "browserUse": False})


@dataclass
class RunState:
    """State for one run (execution)."""
    run_id: str
    seq: int = 0
    steps: Dict[str, StepState] = field(default_factory=dict)
    # Cached summary fields (recomputed on demand too)
    total_steps_hint: Optional[int] = None
    # Event buffer for replay
    buffer: deque = field(default_factory=lambda: deque(maxlen=200))
    subscribers: Set[Callable[[dict], Awaitable[None]]] = field(default_factory=set)
    last_updated_ts_ms: int = 0


class RunEventsHub:
    """In-memory hub for per-run step states and event broadcasting."""

    def __init__(self) -> None:
        self._runs: Dict[str, RunState] = {}
        self._lock = asyncio.Lock()

    async def ensure_run(self, run_id: str) -> RunState:
        async with self._lock:
            if run_id not in self._runs:
                self._runs[run_id] = RunState(run_id=run_id)
            return self._runs[run_id]

    # ── Subscription ─────────────────────────────────────────────────────────
    async def subscribe(self, run_id: str, callback: Callable[[dict], Awaitable[None]]) -> None:
        run = await self.ensure_run(run_id)
        run.subscribers.add(callback)

    async def unsubscribe(self, run_id: str, callback: Callable[[dict], Awaitable[None]]) -> None:
        run = await self.ensure_run(run_id)
        try:
            run.subscribers.discard(callback)
        except Exception:
            pass

    # ── Snapshot ────────────────────────────────────────────────────────────
    async def build_snapshot(self, run_id: str) -> Dict[str, Any]:
        run = await self.ensure_run(run_id)
        now_ms = int(time.time() * 1000)

        # Compute summary counts
        completed = 0
        failed = 0
        total_steps = run.total_steps_hint or 0
        for step in run.steps.values():
            if step.status == STATUS_SUCCESS:
                completed += 1
            elif step.status == STATUS_FAIL:
                failed += 1
            if step.total_steps > total_steps:
                total_steps = step.total_steps

        overall_status = STATUS_RUNNING
        if failed > 0:
            overall_status = STATUS_FAIL
        elif total_steps > 0 and completed >= total_steps:
            overall_status = STATUS_SUCCESS

        steps_payload: List[Dict[str, Any]] = []
        for step in sorted(run.steps.values(), key=lambda s: s.step_index):
            steps_payload.append({
                "stepId": str(step.step_id),
                "staticStepKey": step.static_step_key,
                "stepIndex": step.step_index,
                "totalSteps": step.total_steps,
                "title": step.title,
                "status": step.status,
                "sourceFlags": {
                    "workflowUse": bool(step.source_flags.get("workflowUse", False)),
                    "browserUse": bool(step.source_flags.get("browserUse", False)),
                },
            })

        snapshot = {
            "type": "Snapshot",
            "schemaVersion": 1,
            "runId": run.run_id,
            "seq": run.seq,
            "ts": now_ms,
            "summary": {
                "status": overall_status,
                "totalSteps": total_steps,
                "completedSteps": completed,
                "failedSteps": failed,
            },
            "steps": steps_payload,
        }
        return snapshot

    async def get_buffered_events(self, run_id: str) -> List[Dict[str, Any]]:
        """Return a shallow copy list of buffered events for the given run."""
        run = await self.ensure_run(run_id)
        try:
            return list(run.buffer)
        except Exception:
            return []

    # ── Mutations (emit events) ─────────────────────────────────────────────
    async def run_started(self, run_id: str) -> None:
        event = {"type": "RunStarted"}
        await self._publish(run_id, event)

    async def run_ended(self, run_id: str, status: str) -> None:
        event = {"type": "RunEnded", "status": status}
        await self._publish(run_id, event)

    async def step_started(
        self,
        run_id: str,
        step_id: str,
        step_index: int,
        total_steps: int,
        title: str,
        static_step_key: str,
        source_workflow_use: bool = True,
    ) -> None:
        run = await self.ensure_run(run_id)
        state = run.steps.get(step_id)
        if state is None:
            state = StepState(
                step_id=step_id,
                static_step_key=static_step_key,
                step_index=step_index,
                total_steps=total_steps,
                title=title,
                status=STATUS_RUNNING,
            )
            run.steps[step_id] = state
        else:
            state.step_index = step_index
            state.total_steps = total_steps
            state.title = title
            state.status = STATUS_RUNNING
        state.source_flags["workflowUse"] = bool(source_workflow_use)
        if run.total_steps_hint is None or total_steps > run.total_steps_hint:
            run.total_steps_hint = total_steps

        event = {
            "type": "StepStarted",
            "stepId": step_id,
            "stepIndex": step_index,
            "totalSteps": total_steps,
            "title": title,
            "status": STATUS_RUNNING,
            "sourceFlags": {"workflowUse": True, "browserUse": False},
        }
        await self._publish(run_id, event)

    async def step_finished_success(self, run_id: str, step_id: str) -> None:
        run = await self.ensure_run(run_id)
        state = run.steps.get(step_id)
        if state is None:
            # Create minimal state to avoid dropping the event
            state = StepState(step_id=step_id, static_step_key="", step_index=0, total_steps=0, title="")
            run.steps[step_id] = state
        state.status = STATUS_SUCCESS
        event = {"type": "StepFinishedSuccess", "stepId": step_id, "status": STATUS_SUCCESS}
        await self._publish(run_id, event)

    async def step_finished_fail(self, run_id: str, step_id: str) -> None:
        run = await self.ensure_run(run_id)
        state = run.steps.get(step_id)
        if state is None:
            state = StepState(step_id=step_id, static_step_key="", step_index=0, total_steps=0, title="")
            run.steps[step_id] = state
        state.status = STATUS_FAIL
        event = {"type": "StepFinishedFail", "stepId": step_id, "status": STATUS_FAIL}
        await self._publish(run_id, event)

    async def fallback_started(self, run_id: str, step_id: str, attempt: int, max_attempts: int, session_id: Optional[str]) -> None:
        run = await self.ensure_run(run_id)
        state = run.steps.get(step_id)
        if state is None:
            state = StepState(step_id=step_id, static_step_key="", step_index=0, total_steps=0, title="")
            run.steps[step_id] = state
        state.status = STATUS_FALLBACK
        state.source_flags["browserUse"] = True
        event = {
            "type": "FallbackStarted",
            "stepId": step_id,
            "status": STATUS_FALLBACK,
            "fallback": {"attempt": attempt, "maxAttempts": max_attempts, "sessionId": session_id},
            "sourceFlags": {"workflowUse": bool(state.source_flags.get("workflowUse", False)), "browserUse": True},
        }
        await self._publish(run_id, event)

    async def fallback_retry_progress(self, run_id: str, step_id: str, attempt: int, max_attempts: int, session_id: Optional[str]) -> None:
        run = await self.ensure_run(run_id)
        state = run.steps.get(step_id)
        if state is None:
            state = StepState(step_id=step_id, static_step_key="", step_index=0, total_steps=0, title="")
            run.steps[step_id] = state
        state.status = STATUS_FALLBACK
        state.source_flags["browserUse"] = True
        event = {
            "type": "FallbackRetryProgress",
            "stepId": step_id,
            "status": STATUS_FALLBACK,
            "fallback": {"attempt": attempt, "maxAttempts": max_attempts, "sessionId": session_id},
        }
        await self._publish(run_id, event)

    async def fallback_finished_success(self, run_id: str, step_id: str) -> None:
        await self.step_finished_success(run_id, step_id)

    async def fallback_finished_fail(self, run_id: str, step_id: str, attempt: int, max_attempts: int, session_id: Optional[str]) -> None:
        run = await self.ensure_run(run_id)
        state = run.steps.get(step_id)
        if state is None:
            state = StepState(step_id=step_id, static_step_key="", step_index=0, total_steps=0, title="")
            run.steps[step_id] = state
        state.status = STATUS_FAIL
        event = {
            "type": "FallbackFinishedFail",
            "stepId": step_id,
            "status": STATUS_FAIL,
            "fallback": {"attempt": attempt, "maxAttempts": max_attempts, "sessionId": session_id},
        }
        await self._publish(run_id, event)

    # ── Internals ───────────────────────────────────────────────────────────
    async def _publish(self, run_id: str, event: Dict[str, Any]) -> None:
        run = await self.ensure_run(run_id)
        run.seq += 1
        event["runId"] = run_id
        # Ensure schemaVersion for client compatibility
        if "schemaVersion" not in event:
            event["schemaVersion"] = 1
        event["seq"] = run.seq
        event["ts"] = int(time.time() * 1000)
        run.buffer.append(event)
        run.last_updated_ts_ms = event["ts"]

        # Fan out to subscribers without blocking
        callbacks = list(run.subscribers)
        for cb in callbacks:
            try:
                coro = cb(event)
                if asyncio.iscoroutine(coro):
                    asyncio.create_task(coro)
            except Exception as e:
                logger.debug(f"RunEventsHub subscriber error: {e}")
        try:
            logger.debug(f"RunEventsHub published event type={event.get('type')} runId={run_id} seq={event.get('seq')} subscribers={len(callbacks)}")
        except Exception:
            pass


# Global hub instance
run_events_hub = RunEventsHub()


