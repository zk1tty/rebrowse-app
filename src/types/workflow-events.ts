import { z } from "zod";

// -----------------------------
// Schema/version constants
// -----------------------------
export const CURRENT_SCHEMA_VERSION = 1 as const;

// -----------------------------
// Shared primitives
// -----------------------------
export const StatusSchema = z.enum([
  "ready",
  "running",
  "AI-fallback",
  "success",
  "fail",
]);
export type Status = z.infer<typeof StatusSchema>;

export const SourceFlagsSchema = z.object({
  workflowUse: z.boolean().optional(),
  browserUse: z.boolean().optional(),
});
export type SourceFlags = z.infer<typeof SourceFlagsSchema>;

// -----------------------------
// StepState (client-side minimal required fields)
// -----------------------------
export const StepStateSchema = z.object({
  stepId: z.string(),
  staticStepKey: z.string(),
  stepIndex: z.number().int().nonnegative(),
  totalSteps: z.number().int().positive(),
  title: z.string(),
  status: StatusSchema,
  sourceFlags: SourceFlagsSchema.default({}),
  fallback: z
    .object({
      attempt: z.number().int().nonnegative(),
      maxAttempts: z.number().int().positive(),
      sessionId: z.string().optional(),
    })
    .optional(),
});
export type StepState = z.infer<typeof StepStateSchema>;

// -----------------------------
// Snapshot schema (server → client)
// -----------------------------
export const SnapshotSchema = z.object({
  type: z.literal("Snapshot"),
  schemaVersion: z.number().int().positive(),
  runId: z.string(),
  seq: z.number().int().nonnegative(),
  ts: z.number().int().nonnegative(),
  summary: z.object({
    status: StatusSchema,
    totalSteps: z.number().int().nonnegative(),
    completedSteps: z.number().int().nonnegative(),
    failedSteps: z.number().int().nonnegative(),
  }),
  steps: z.array(StepStateSchema),
});
export type Snapshot = z.infer<typeof SnapshotSchema>;

// -----------------------------
// Event schemas (server → client)
// -----------------------------
const EventBase = z.object({
  schemaVersion: z.number().int().positive().default(CURRENT_SCHEMA_VERSION),
  runId: z.string(),
  seq: z.number().int().nonnegative(),
  ts: z.number().int().nonnegative(),
  eventId: z.string().optional(),
  // Optional informational fields
  message: z.string().optional(),
  details: z.unknown().optional(),
});

const StepRef = z.object({
  stepId: z.string(),
  // These may be omitted on terminal events per example payloads
  stepIndex: z.number().int().nonnegative().optional(),
  totalSteps: z.number().int().positive().optional(),
  title: z.string().optional(),
  sourceFlags: SourceFlagsSchema.optional(),
});

const FallbackInfo = z.object({
  attempt: z.number().int().nonnegative(),
  maxAttempts: z.number().int().positive(),
  sessionId: z.string().nullable().optional(),
});

export const RunStartedEventSchema = EventBase.extend({
  type: z.literal("RunStarted"),
});

export const RunEndedEventSchema = EventBase.extend({
  type: z.literal("RunEnded"),
  status: z.enum(["success", "fail"]),
});

export const StepStartedEventSchema = EventBase.merge(StepRef).extend({
  type: z.literal("StepStarted"),
  status: StatusSchema, // expected "running"
});

export const StepFinishedSuccessEventSchema = EventBase.merge(StepRef).extend({
  type: z.literal("StepFinishedSuccess"),
  status: z.literal("success"),
});

export const StepFinishedFailEventSchema = EventBase.merge(StepRef).extend({
  type: z.literal("StepFinishedFail"),
  status: z.literal("fail"),
});

export const FallbackStartedEventSchema = EventBase.merge(StepRef).extend({
  type: z.literal("FallbackStarted"),
  status: z.literal("AI-fallback"),
  fallback: FallbackInfo,
});

export const FallbackRetryProgressEventSchema = EventBase.merge(StepRef).extend({
  type: z.literal("FallbackRetryProgress"),
  status: z.literal("AI-fallback"),
  fallback: FallbackInfo,
});

export const FallbackFinishedSuccessEventSchema = EventBase.merge(StepRef).extend({
  type: z.literal("FallbackFinishedSuccess"),
  status: z.literal("success"),
  fallback: FallbackInfo.optional(),
});

export const FallbackFinishedFailEventSchema = EventBase.merge(StepRef).extend({
  type: z.literal("FallbackFinishedFail"),
  status: z.literal("fail"),
  fallback: FallbackInfo.optional(),
});

export const EventSchema = z.discriminatedUnion("type", [
  RunStartedEventSchema,
  RunEndedEventSchema,
  StepStartedEventSchema,
  StepFinishedSuccessEventSchema,
  StepFinishedFailEventSchema,
  FallbackStartedEventSchema,
  FallbackRetryProgressEventSchema,
  FallbackFinishedSuccessEventSchema,
  FallbackFinishedFailEventSchema,
]);

export type RunStartedEvent = z.infer<typeof RunStartedEventSchema>;
export type RunEndedEvent = z.infer<typeof RunEndedEventSchema>;
export type StepStartedEvent = z.infer<typeof StepStartedEventSchema>;
export type StepFinishedSuccessEvent = z.infer<typeof StepFinishedSuccessEventSchema>;
export type StepFinishedFailEvent = z.infer<typeof StepFinishedFailEventSchema>;
export type FallbackStartedEvent = z.infer<typeof FallbackStartedEventSchema>;
export type FallbackRetryProgressEvent = z.infer<typeof FallbackRetryProgressEventSchema>;
export type FallbackFinishedSuccessEvent = z.infer<typeof FallbackFinishedSuccessEventSchema>;
export type FallbackFinishedFailEvent = z.infer<typeof FallbackFinishedFailEventSchema>;
export type WorkflowEvent = z.infer<typeof EventSchema>;

// -----------------------------
// Parsing helpers with schemaVersion guard
// -----------------------------
export function parseSnapshot(input: unknown): { ok: true; data: Snapshot } | { ok: false; error: unknown } {
  const result = SnapshotSchema.safeParse(input);
  if (!result.success) return { ok: false, error: result.error };
  if (result.data.schemaVersion !== CURRENT_SCHEMA_VERSION) {
    return { ok: false, error: new Error(`Unsupported snapshot schemaVersion: ${result.data.schemaVersion}`) };
  }
  return { ok: true, data: result.data };
}

export function parseEvent(input: unknown): { ok: true; data: WorkflowEvent } | { ok: false; error: unknown } {
  const result = EventSchema.safeParse(input);
  if (!result.success) return { ok: false, error: result.error };
  if (result.data.schemaVersion !== CURRENT_SCHEMA_VERSION) {
    return { ok: false, error: new Error(`Unsupported event schemaVersion: ${result.data.schemaVersion}`) };
  }
  return { ok: true, data: result.data };
}


