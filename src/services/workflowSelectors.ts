import { runStore, type RunState } from "./workflowRunStore";
import type { StepState } from "../types/workflow-events";

export type UIOrderedStep = Pick<StepState, "stepId" | "stepIndex" | "title" | "status" | "sourceFlags"> & {
  totalSteps: number;
  fallbackLabel?: string;
};

export function getRun(runId: string): RunState | undefined {
  return runStore.get(runId);
}

export function getSummary(runId: string) {
  const run = runStore.get(runId);
  return run?.summary;
}

export function getOrderedSteps(runId: string): UIOrderedStep[] {
  const run = runStore.get(runId);
  if (!run) return [];
  const steps = Array.from(run.steps.values());
  steps.sort((a, b) => a.stepIndex - b.stepIndex);
  return steps.map((s) => ({
    stepId: s.stepId,
    stepIndex: s.stepIndex,
    title: s.title,
    status: s.status,
    sourceFlags: s.sourceFlags,
    totalSteps: s.totalSteps,
    fallbackLabel:
      s.fallback && typeof s.fallback.attempt === "number" && typeof s.fallback.maxAttempts === "number"
        ? `${s.fallback.attempt}/${s.fallback.maxAttempts}`
        : undefined,
  }));
}

export function getStepById(runId: string, stepId: string): StepState | undefined {
  const run = runStore.get(runId);
  return run?.steps.get(stepId);
}


