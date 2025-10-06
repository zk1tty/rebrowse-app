"""
Logging extensions for real-time log broadcasting.

- execution_id_var: ContextVar carrying current execution id
- ExecutionIdFilter: injects execution_id into LogRecord if missing
- LogBroadcastHandler: forwards log records to a publish/subscribe hub
- LogBroadcastHub: minimal in-memory pub/sub for later WebSocket/SSE wiring

This file has no dependency on FastAPI/WS. The WS route can subscribe
callbacks later to receive per-execution log payloads.
"""

from __future__ import annotations

import asyncio
import time
import os
import socket
import logging
from contextvars import ContextVar
from typing import Awaitable, Callable, Dict, Optional, Set, List
from collections import deque
try:
    from redis.asyncio import Redis
except Exception:  # redis is optional; enable when configured
    Redis = None  # type: ignore


# Context variable to tag logs with execution scope
execution_id_var: ContextVar[Optional[str]] = ContextVar("execution_id", default=None)


class ExecutionIdFilter(logging.Filter):
    """Logging filter that ensures record.execution_id is set.

    Priority order:
    - keep existing record.execution_id if provided via LoggerAdapter/extra
    - otherwise, pull from execution_id_var ContextVar (may be None)
    """

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        try:
            if not hasattr(record, "execution_id"):
                setattr(record, "execution_id", execution_id_var.get())
            return True
        except Exception:
            # Never block logging due to filter errors
            return True


class LogBroadcastHub:
    """A lightweight async pub/sub hub keyed by execution_id.

    Subscribers register an async callback taking a payload dict.
    """

    _global_instance: Optional["LogBroadcastHub"] = None

    def __init__(self) -> None:
        self._subscribers: Dict[str, Set[Callable[[dict], Awaitable[None]]]] = {}
        # Per-execution history buffer
        self._history: Dict[str, deque] = {}
        self._history_updated_at: Dict[str, float] = {}
        self.MAX_HISTORY: int = 200
        self.HISTORY_TTL_SEC: int = 180  # 3 minutes

        # Redis PubSub (optional)
        self._redis_url: Optional[str] = os.getenv('REDIS_URL')
        self._redis: Optional[Redis] = None
        self._redis_sub_tasks: Dict[str, asyncio.Task] = {}
        self._worker_id: str = f"{socket.gethostname()}-{os.getpid()}"

    @classmethod
    def get_global(cls) -> "LogBroadcastHub":
        if cls._global_instance is None:
            cls._global_instance = LogBroadcastHub()
        return cls._global_instance

    def subscribe(self, execution_id: str, callback: Callable[[dict], Awaitable[None]]) -> None:
        if execution_id not in self._subscribers:
            self._subscribers[execution_id] = set()
        self._subscribers[execution_id].add(callback)
        # If this is the first local subscriber, start Redis subscription
        if len(self._subscribers[execution_id]) == 1:
            try:
                if self._redis_url and Redis is not None:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._start_redis_subscription(execution_id))
            except Exception:
                pass

    def unsubscribe(self, execution_id: str, callback: Callable[[dict], Awaitable[None]]) -> None:
        try:
            callbacks = self._subscribers.get(execution_id)
            if callbacks and callback in callbacks:
                callbacks.remove(callback)
                if not callbacks:
                    self._subscribers.pop(execution_id, None)
                    # No more local subscribers: stop Redis subscription
                    try:
                        self._stop_redis_subscription(execution_id)
                    except Exception:
                        pass
        except Exception:
            pass

    def publish(self, execution_id: Optional[str], payload: dict) -> int:
        """Publish payload to all subscribers of execution_id.

        Returns number of callbacks scheduled. If execution_id is None,
        nothing is published (no-op).
        """
        if not execution_id:
            return 0
        # Append to history with TTL management
        try:
            self._append_history(execution_id, payload)
            self._purge_expired()
        except Exception:
            pass
        callbacks = self._subscribers.get(execution_id)
        if not callbacks:
            return 0

        scheduled = 0
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None  # allow silent no-op if no loop

        for cb in list(callbacks):
            try:
                coro = cb(payload)
                if asyncio.iscoroutine(coro):
                    if loop:
                        asyncio.create_task(coro)  # fire-and-forget
                        scheduled += 1
                # If callback returned non-coroutine, ignore
            except Exception:
                # Never raise from publishers
                continue
        return scheduled

    async def publish_to_redis(self, execution_id: Optional[str], payload: dict) -> None:
        """Publish to Redis Pub/Sub if configured. No-op if disabled."""
        if not execution_id or not self._redis_url or Redis is None:
            return
        try:
            client = await self._ensure_redis_client()
            if not client:
                return
            msg = dict(payload)
            msg['publisher_id'] = self._worker_id
            import orjson
            data = orjson.dumps(msg)
            channel = f"logs:{execution_id}"
            await client.publish(channel, data)
        except Exception:
            # Don't fail on Redis issues
            return

    # ── History helpers ─────────────────────────────────────────────────────
    def _append_history(self, execution_id: str, payload: dict) -> None:
        if execution_id not in self._history:
            self._history[execution_id] = deque(maxlen=self.MAX_HISTORY)
        # Store a shallow copy so later mutation won't affect stored event
        try:
            entry = dict(payload)
        except Exception:
            entry = payload
        self._history[execution_id].append(entry)
        self._history_updated_at[execution_id] = time.time()

    def get_history(self, execution_id: str) -> List[dict]:
        buf = self._history.get(execution_id)
        if not buf:
            return []
        # Return a list copy
        return list(buf)

    def _purge_expired(self) -> None:
        if not self._history_updated_at:
            return
        now = time.time()
        expired: List[str] = []
        for exec_id, ts in list(self._history_updated_at.items()):
            if now - ts > self.HISTORY_TTL_SEC:
                expired.append(exec_id)
        for exec_id in expired:
            try:
                self._history.pop(exec_id, None)
                self._history_updated_at.pop(exec_id, None)
            except Exception:
                pass

    # ── Redis subscribe management ───────────────────────────────────────────
    async def _ensure_redis_client(self) -> Optional[Redis]:
        if not self._redis_url or Redis is None:
            return None
        if self._redis is None:
            try:
                self._redis = Redis.from_url(self._redis_url, decode_responses=False)
            except Exception:
                self._redis = None
        return self._redis

    async def _start_redis_subscription(self, execution_id: str) -> None:
        if execution_id in self._redis_sub_tasks:
            return
        client = await self._ensure_redis_client()
        if not client:
            return

        async def _runner() -> None:
            pubsub = None
            try:
                pubsub = client.pubsub()
                channel = f"logs:{execution_id}"
                await pubsub.subscribe(channel)
                while True:
                    try:
                        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                        if not message:
                            await asyncio.sleep(0.05)
                            continue
                        if message.get('type') != 'message':
                            continue
                        raw = message.get('data')
                        if not raw:
                            continue
                        try:
                            import orjson
                            payload = orjson.loads(raw)
                        except Exception:
                            continue
                        if payload.get('publisher_id') == self._worker_id:
                            # Skip self-echo
                            continue
                        # Ensure execution_id
                        exec_id = payload.get('execution_id') or execution_id
                        # Append to history and deliver locally without republishing to Redis
                        try:
                            self._append_history(exec_id, payload)
                        except Exception:
                            pass
                        self._deliver_local(exec_id, payload)
                    except asyncio.CancelledError:
                        break
                    except Exception:
                        await asyncio.sleep(0.1)
            finally:
                try:
                    if pubsub:
                        await pubsub.unsubscribe()
                        await pubsub.close()
                except Exception:
                    pass

        task = asyncio.create_task(_runner())
        self._redis_sub_tasks[execution_id] = task

    def _stop_redis_subscription(self, execution_id: str) -> None:
        task = self._redis_sub_tasks.pop(execution_id, None)
        if task:
            task.cancel()

    def _deliver_local(self, execution_id: str, payload: dict) -> int:
        callbacks = self._subscribers.get(execution_id)
        if not callbacks:
            return 0
        scheduled = 0
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        for cb in list(callbacks):
            try:
                coro = cb(payload)
                if asyncio.iscoroutine(coro) and loop:
                    asyncio.create_task(coro)
                    scheduled += 1
            except Exception:
                continue
        return scheduled


class LogBroadcastHandler(logging.Handler):
    """Logging handler that forwards log records to LogBroadcastHub.

    Use alongside a file/console handler. This does not perform formatting
    for human readability; it constructs a structured payload for clients.
    """

    def __init__(self, hub: Optional[LogBroadcastHub] = None, level: int = logging.INFO) -> None:
        super().__init__(level=level)
        self.hub = hub or LogBroadcastHub.get_global()

    def emit(self, record: logging.LogRecord) -> None:  # type: ignore[override]
        try:
            # Ensure execution_id attribute exists (filter should have done it)
            execution_id = getattr(record, "execution_id", None)
            if execution_id is None:
                # Fallback to ContextVar in case logger filters didn't run at this level
                try:
                    execution_id = execution_id_var.get()
                except Exception:
                    execution_id = None
            message = record.getMessage()
            payload = {
                "type": "log",
                "timestamp": record.created,
                "level": record.levelname,
                "logger": record.name,
                "message": message,
                "execution_id": execution_id,
                "pathname": record.pathname,
                "lineno": record.lineno,
            }
            self.hub.publish(execution_id, payload)
            # Cross-worker fan-out
            try:
                # Fire-and-forget publish to Redis if available
                loop = asyncio.get_running_loop()
                if loop and execution_id:
                    asyncio.create_task(self.hub.publish_to_redis(execution_id, payload))
            except Exception:
                pass
        except Exception:
            # Logging must never fail the app
            pass


