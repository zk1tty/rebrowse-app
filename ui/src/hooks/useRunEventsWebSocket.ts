import { useCallback, useEffect, useRef, useState } from "react";
import { API_ENDPOINTS } from "../lib/constants";
import { applySnapshot } from "../services/workflowRunStore";
import { applyWorkflowEvent } from "../services/workflowEventReducer";
import { parseEvent, parseSnapshot } from "../types/workflow-events";
import { useAppContext as useAppContextRaw } from "../contexts/AppContext";

type ConnectionState = "connecting" | "connected" | "disconnected" | "error";

export function useRunEventsWebSocket(runId: string | undefined) {
  const [state, setState] = useState<ConnectionState>("disconnected");
  const [lastUpdate, setLastUpdate] = useState<number>(0);
  const { setCurrentRunId, currentRunId } = useAppContextRaw();
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

  const connect = useCallback(() => {
    if (!runId) return;

    if (reconnectTimeoutRef.current) {
      window.clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
    }

    const wsUrl = API_ENDPOINTS.RUN_EVENTS_WS(runId);
    setState("connecting");
    console.log(`[RunEvents] Connecting WS for runId=${runId}:`, wsUrl);
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setState("connected");
    };

    ws.onmessage = async (event: MessageEvent) => {
      try {
        let text: string | null = null;
        const raw = event.data as any;
        if (typeof raw === 'string') {
          text = raw;
        } else if (raw instanceof Blob) {
          text = await raw.text();
          try {
            console.log(`[RunEvents] Decoded Blob frame (${text.length} chars):`, text.slice(0, 120));
          } catch {}
        } else if (raw instanceof ArrayBuffer) {
          text = new TextDecoder().decode(raw);
          try {
            console.log(`[RunEvents] Decoded ArrayBuffer frame (${text.length} chars):`, text.slice(0, 120));
          } catch {}
        } else {
          // Unknown frame type; attempt to coerce via toString
          try {
            text = String(raw);
          } catch {
            console.warn('[RunEvents] Unknown WS frame type, ignoring');
            return;
          }
        }

        const data = JSON.parse(text);
        if (data?.type === "Snapshot") {
          const parsed = parseSnapshot(data);
          if (parsed.ok) {
            applySnapshot(parsed.data.runId, parsed.data);
            setLastUpdate(Date.now());
            console.log(`[RunEvents] Snapshot accepted: runId=${parsed.data.runId} seq=${parsed.data.seq} steps=${parsed.data.steps.length}`);
            try {
              if (!currentRunId || currentRunId !== parsed.data.runId) {
                setCurrentRunId(parsed.data.runId);
              }
            } catch {}
            try {
              window.dispatchEvent(new CustomEvent('wfui-run-events-update', { detail: { runId: parsed.data.runId, ts: Date.now() } }));
            } catch {}
          } else {
            console.warn("Snapshot parse error", parsed.error);
          }
          return;
        }

        const parsedEv = parseEvent(data);
        if (parsedEv.ok) {
          applyWorkflowEvent(parsedEv.data);
          setLastUpdate(Date.now());
          console.log(`[RunEvents] Event: type=${parsedEv.data.type} seq=${parsedEv.data.seq}`);
          try {
            if (!currentRunId || currentRunId !== parsedEv.data.runId) {
              setCurrentRunId(parsedEv.data.runId);
            }
          } catch {}
          try {
            window.dispatchEvent(new CustomEvent('wfui-run-events-update', { detail: { runId: parsedEv.data.runId, ts: Date.now() } }));
          } catch {}
        } else {
          console.warn("Event parse error", parsedEv.error);
        }
      } catch (err) {
        console.error("Failed to parse WS message", err);
      }
    };

    ws.onclose = (e) => {
      setState("disconnected");
      // Attempt reconnect unless normal close or session not found
      if (e.code !== 1000 && e.code !== 4404) {
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect();
        }, 2000);
      }
    };

    ws.onerror = () => {
      setState("error");
    };
  }, [runId]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimeoutRef.current) {
        window.clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  return { connectionState: state, reconnect: connect, lastUpdate };
}


