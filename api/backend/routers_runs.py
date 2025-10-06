import asyncio
import logging
import orjson
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .run_events import run_events_hub


logger = logging.getLogger(__name__)

runs_router = APIRouter()


@runs_router.websocket("/runs/{run_id}/events")
async def websocket_run_events(websocket: WebSocket, run_id: str):
    """Per-run WebSocket: sends Snapshot first, then live step/run events.

    Delivery:
    - On connect: Snapshot
    - Then: live events ordered by seq
    """
    await websocket.accept()
    try:
        logger.info(f"[run-events-ws] Connected run_id={run_id}")
    except Exception:
        pass

    send_queue: asyncio.Queue = asyncio.Queue(maxsize=500)
    stop_event = asyncio.Event()

    async def _on_event(event: dict) -> None:
        try:
            send_queue.put_nowait(event)
        except asyncio.QueueFull:
            try:
                _ = send_queue.get_nowait()
            except Exception:
                pass
            try:
                send_queue.put_nowait(event)
            except Exception:
                pass

    # Subscribe and send Snapshot
    await run_events_hub.subscribe(run_id, _on_event)
    try:
        logger.info(f"[run-events-ws] Subscribed to run_id={run_id}")
    except Exception:
        pass
    try:
        snapshot = await run_events_hub.build_snapshot(run_id)
        await websocket.send_bytes(orjson.dumps(snapshot))
        try:
            logger.info(f"[run-events-ws] Sent snapshot run_id={run_id} seq={snapshot.get('seq')} steps={len(snapshot.get('steps', []))}")
        except Exception:
            pass
        # Send buffered events after snapshot (best-effort catch-up)
        try:
            buffered = await run_events_hub.get_buffered_events(run_id)
            snap_seq = int(snapshot.get("seq", 0)) if isinstance(snapshot.get("seq", 0), int) else 0
            for ev in buffered:
                ev_seq = ev.get("seq", 0)
                try:
                    ev_seq = int(ev_seq)
                except Exception:
                    ev_seq = 0
                if ev_seq > snap_seq:
                    await websocket.send_bytes(orjson.dumps(ev))
            try:
                logger.info(f"[run-events-ws] Replayed buffered events after snapshot run_id={run_id} count={len(buffered)}")
            except Exception:
                pass
        except Exception:
            pass
    except Exception as e:
        logger.debug(f"Failed to send snapshot for {run_id}: {e}")

    async def _sender() -> None:
        try:
            while not stop_event.is_set():
                try:
                    payload = await send_queue.get()
                    await websocket.send_bytes(orjson.dumps(payload))
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logger.debug(f"Run WS sender error: {e}")
                    await asyncio.sleep(0.01)
        finally:
            stop_event.set()

    async def _receiver() -> None:
        # Placeholder for future acks/controls
        try:
            while not stop_event.is_set():
                try:
                    _ = await websocket.receive_text()
                except WebSocketDisconnect:
                    break
                except Exception:
                    await asyncio.sleep(0.05)
        finally:
            stop_event.set()

    sender_task = asyncio.create_task(_sender())
    receiver_task = asyncio.create_task(_receiver())

    try:
        await asyncio.wait({sender_task, receiver_task}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        stop_event.set()
        try:
            await run_events_hub.unsubscribe(run_id, _on_event)  # type: ignore[arg-type]
        except Exception:
            pass
        try:
            await websocket.close()
        except Exception:
            pass