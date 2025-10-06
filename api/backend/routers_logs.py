import asyncio
import logging
from typing import Optional

import orjson
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .logging_broadcast import LogBroadcastHub


logger = logging.getLogger(__name__)

# Dedicated router for log streaming
logs_router = APIRouter()


@logs_router.websocket("/ws/logs/{execution_id}")
async def websocket_logs(websocket: WebSocket, execution_id: str):
    """WebSocket endpoint that streams realtime logs for a specific execution_id.

    The endpoint subscribes to the in-process LogBroadcastHub and forwards
    structured log payloads to the client. It uses a bounded queue to avoid
    unbounded memory growth when clients are slow (basic backpressure).
    """
    await websocket.accept()
    # Emit a probe log to verify broadcast pipeline end-to-end
    try:
        # Emit probe logs on both namespaces with execution_id context
        base_logger = logging.getLogger('browser_use')
        adapter = logging.LoggerAdapter(base_logger, extra={'execution_id': execution_id})
        adapter.info(f"[logs-ws] Connected execution_id={execution_id} (probe)")
        wu_logger = logging.getLogger('workflow_use')
        wu_adapter = logging.LoggerAdapter(wu_logger, extra={'execution_id': execution_id})
        wu_adapter.info(f"[logs-ws] Connected execution_id={execution_id} (probe)")
    except Exception:
        pass

    hub = LogBroadcastHub.get_global()

    send_queue: asyncio.Queue = asyncio.Queue(maxsize=500)
    stop_event = asyncio.Event()

    async def _on_log(payload: dict) -> None:
        # Non-blocking enqueue with drop-oldest on overflow
        try:
            send_queue.put_nowait(payload)
        except asyncio.QueueFull:
            try:
                _ = send_queue.get_nowait()
            except Exception:
                pass
            try:
                send_queue.put_nowait(payload)
            except Exception:
                pass

    # Subscribe before starting loops
    hub.subscribe(execution_id, _on_log)
    try:
        logger.info(f"[logs-ws] Subscribed to execution_id={execution_id}")
    except Exception:
        pass

    # Send recent history first, mark as replay
    try:
        history = hub.get_history(execution_id)
        if history:
            for item in history:
                try:
                    replay_item = dict(item)
                except Exception:
                    replay_item = item
                replay_item["replay"] = True
                await websocket.send_bytes(orjson.dumps(replay_item))
    except Exception:
        pass

    async def _sender() -> None:
        try:
            while not stop_event.is_set():
                try:
                    payload = await send_queue.get()
                    data = orjson.dumps(payload)
                    await websocket.send_bytes(data)
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logger.debug(f"Log WS sender error: {e}")
                    await asyncio.sleep(0.01)
        finally:
            stop_event.set()

    async def _receiver() -> None:
        # Optional: handle simple ping or close from client
        try:
            while not stop_event.is_set():
                try:
                    _ = await websocket.receive_text()
                    # No-op; could parse control messages if needed
                except WebSocketDisconnect:
                    break
                except Exception:
                    await asyncio.sleep(0.05)
        finally:
            stop_event.set()

    sender_task = asyncio.create_task(_sender())
    receiver_task = asyncio.create_task(_receiver())

    try:
        await asyncio.wait(
            {sender_task, receiver_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
    finally:
        stop_event.set()
        try:
            hub.unsubscribe(execution_id, _on_log)
        except Exception:
            pass
        try:
            await websocket.close()
        except Exception:
            pass


