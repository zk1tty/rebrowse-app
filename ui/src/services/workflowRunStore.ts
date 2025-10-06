import { Snapshot, StepState } from "../types/workflow-events";

export type RunSummary = {
  status: "ready" | "running" | "AI-fallback" | "success" | "fail";
  totalSteps: number;
  completedSteps: number;
  failedSteps: number;
};

export type RunState = {
  lastSeq: number;
  steps: Map<string, StepState>;
  summary: RunSummary;
};

const RUN_LASTSEQ_STORAGE_KEY = (runId: string) => `wfui:lastSeq:${runId}`;

function loadLastSeq(runId: string): number {
  try {
    const raw = localStorage.getItem(RUN_LASTSEQ_STORAGE_KEY(runId));
    if (!raw) return 0;
    const parsed = Number(raw);
    return Number.isFinite(parsed) && parsed >= 0 ? parsed : 0;
  } catch {
    return 0;
  }
}

function saveLastSeq(runId: string, seq: number): void {
  try {
    localStorage.setItem(RUN_LASTSEQ_STORAGE_KEY(runId), String(seq));
  } catch {
    // no-op: storage may be unavailable
  }
}

export const runStore: Map<string, RunState> = new Map();

export function getOrCreateRun(runId: string): RunState {
  const existing = runStore.get(runId);
  if (existing) return existing;
  const state: RunState = {
    lastSeq: loadLastSeq(runId),
    steps: new Map<string, StepState>(),
    summary: { status: "ready", totalSteps: 0, completedSteps: 0, failedSteps: 0 },
  };
  runStore.set(runId, state);
  return state;
}

export function removeRun(runId: string): void {
  runStore.delete(runId);
  try {
    localStorage.removeItem(RUN_LASTSEQ_STORAGE_KEY(runId));
  } catch {
    // ignore storage errors
  }
}

export function applySnapshot(runId: string, snapshot: Snapshot): RunState {
  const state = getOrCreateRun(runId);

  // Replace steps wholesale
  const nextSteps = new Map<string, StepState>();
  for (const step of snapshot.steps) {
    nextSteps.set(step.stepId, step);
  }
  state.steps = nextSteps;

  // Replace summary and lastSeq
  state.summary = {
    status: snapshot.summary.status,
    totalSteps: snapshot.summary.totalSteps,
    completedSteps: snapshot.summary.completedSteps,
    failedSteps: snapshot.summary.failedSteps,
  };

  state.lastSeq = snapshot.seq;
  saveLastSeq(runId, state.lastSeq);
  try {
    console.log('[RunEvents][Store] applySnapshot', { runId, seq: snapshot.seq, steps: snapshot.steps.length, summary: state.summary });
  } catch {}

  return state;
}

export function updateLastSeq(runId: string, seq: number): void {
  const state = getOrCreateRun(runId);
  if (seq > state.lastSeq) {
    state.lastSeq = seq;
    saveLastSeq(runId, state.lastSeq);
    try {
      console.log('[RunEvents][Store] updateLastSeq', { runId, seq });
    } catch {}
  }
}

export function recomputeRunSummary(runId: string): void {
  const state = getOrCreateRun(runId);
  const steps = Array.from(state.steps.values());

  let totalStepsCandidate = 0;
  for (const s of steps) {
    if (typeof s.totalSteps === "number" && s.totalSteps > totalStepsCandidate) {
      totalStepsCandidate = s.totalSteps;
    }
  }
  const completedSteps = steps.filter((s) => s.status === "success").length;
  const failedSteps = steps.filter((s) => s.status === "fail").length;

  const totalSteps = totalStepsCandidate || state.summary.totalSteps || 0;

  let status: RunSummary["status"] = "ready";
  if (failedSteps > 0) {
    status = "fail";
  } else if (totalSteps > 0 && completedSteps >= totalSteps) {
    status = "success";
  } else if (
    steps.some((s) => s.status === "running" || s.status === "AI-fallback") ||
    completedSteps > 0
  ) {
    status = "running";
  }

  state.summary = {
    status,
    totalSteps,
    completedSteps,
    failedSteps,
  };
}


