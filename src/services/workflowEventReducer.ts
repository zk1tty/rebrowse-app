import {
  type WorkflowEvent,
  type StepState,
} from "../types/workflow-events";
import { getOrCreateRun, updateLastSeq, recomputeRunSummary } from "./workflowRunStore";

function ensureStep(stateSteps: Map<string, StepState>, evt: WorkflowEvent): StepState {
  const stepId = (evt as any).stepId as string | undefined;
  if (!stepId) {
    // Non-step events (RunStarted/RunEnded) should not call ensureStep
    throw new Error("ensureStep called without stepId");
  }
  const existing = stateSteps.get(stepId);
  if (existing) {
    // Update known metadata if present on the event (non-destructive)
    const e = evt as any;
    if (typeof e.stepIndex === "number") existing.stepIndex = e.stepIndex;
    if (typeof e.totalSteps === "number") existing.totalSteps = e.totalSteps;
    if (typeof e.title === "string") existing.title = e.title;
    if (e.sourceFlags) {
      existing.sourceFlags = { ...existing.sourceFlags, ...e.sourceFlags };
    }
    if (e.fallback) {
      existing.fallback = { ...existing.fallback, ...e.fallback };
    }
    return existing;
  }

  // Bootstrap step from event; staticStepKey is unknown from events, use stepId as a stable placeholder
  const e = evt as any;
  const inferredIndex = (() => {
    if (typeof e.stepIndex === "number") return e.stepIndex;
    const n = Number(stepId);
    return Number.isFinite(n) && n > 0 ? n : 0;
  })();
  const bootstrap: StepState = {
    stepId,
    staticStepKey: stepId,
    stepIndex: inferredIndex,
    totalSteps: typeof e.totalSteps === "number" ? e.totalSteps : 0,
    title: typeof e.title === "string" ? e.title : "",
    status: (e.status as StepState["status"]) ?? "ready",
    sourceFlags: e.sourceFlags ?? {},
    fallback: e.fallback,
  };
  stateSteps.set(stepId, bootstrap);
  return bootstrap;
}

function isTerminal(status: StepState["status"]): boolean {
  return status === "success" || status === "fail";
}

export function applyWorkflowEvent(event: WorkflowEvent): void {
  const run = getOrCreateRun(event.runId);

  // Dedupe/out-of-order guard
  if (event.seq <= run.lastSeq) {
    return;
  }

  switch (event.type) {
    case "RunStarted": {
      // No step changes; only seq tracking handled below
      break;
    }
    case "RunEnded": {
      // Summary handling will be done in a separate step
      break;
    }
    case "StepStarted": {
      const step = ensureStep(run.steps, event);
      if (!isTerminal(step.status)) {
        step.status = "running";
      }
      break;
    }
    case "StepFinishedSuccess": {
      const step = ensureStep(run.steps, event);
      if (!isTerminal(step.status)) {
        step.status = "success";
      }
      break;
    }
    case "StepFinishedFail": {
      const step = ensureStep(run.steps, event);
      // Fail always wins
      step.status = "fail";
      break;
    }
    case "FallbackStarted": {
      const step = ensureStep(run.steps, event);
      if (!isTerminal(step.status)) {
        step.status = "AI-fallback";
      }
      break;
    }
    case "FallbackRetryProgress": {
      const step = ensureStep(run.steps, event);
      if (!isTerminal(step.status)) {
        step.status = "AI-fallback";
      }
      break;
    }
    case "FallbackFinishedSuccess": {
      const step = ensureStep(run.steps, event);
      if (!isTerminal(step.status)) {
        step.status = "success";
      }
      break;
    }
    case "FallbackFinishedFail": {
      const step = ensureStep(run.steps, event);
      step.status = "fail";
      break;
    }
    default: {
      // Unknown type: ignore
      break;
    }
  }

  updateLastSeq(event.runId, event.seq);
  recomputeRunSummary(event.runId);
}


