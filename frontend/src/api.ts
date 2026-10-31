// Typed client for the read-only M10 API (backend/main.py, shapes in backend/api_shapes.py).
// Types mirror the JSON exactly; nothing here recomputes a metric.
import type { CallDetail, CallRow } from "./callTypes";
import { compareWarnings, IS_STATIC, staticUrl, type SnapshotMeta } from "./staticApi";

/** One rate as stored by backend/eval/metrics.py rate(): Wilson 95% CI, null when n = 0. */
export interface Rate {
  k: number;
  n: number;
  rate: number | null;
  ci_low: number | null;
  ci_high: number | null;
}

export const RATE_NAMES = [
  "outcome_pass", "judge_task_success", "hallucination", "compliance_violation",
  "escalation_correct", "identity_verified", "pressure_or_threat", "policy_violation",
] as const;
export type RateName = (typeof RATE_NAMES)[number];

export const LINT_CATEGORIES = [
  "symbols_markdown", "long_turn", "digit_amount", "numeric_date", "code_token", "unspelled_contact",
] as const;
export type LintCategory = (typeof LINT_CATEGORIES)[number];

/** api_shapes.headline(): the 8 rates are Rate objects (or missing), the rest plain numbers. */
export type Headline = { [K in RateName]?: Rate | null } & {
  lint_total_per_call: number | null;
  tone_avg: number | null;
  turns_per_call: number | null;
};

export type RunStatus = "complete" | "partial" | "no_metrics";

export interface RunSummary {
  id: number;
  run_key: string;
  prompt_version: string;
  judge_version: string;
  models: { agent: string; sim: string; judge: string };
  n: number;
  seed: number;
  n_calls_stored: number;
  n_ok: number;
  n_failed: number;
  status: RunStatus;
  complete: boolean;
  updated_at: string;
  headline: Headline | null;
}

/** One group of metrics (overall, or one persona) from metrics._group(). */
export interface MetricGroup {
  n_calls: number;
  n_failed: number;
  n_judged: number;
  rates: Record<RateName | "retrieval_empty", Rate>;
  lint_per_call: Record<LintCategory | "total", number | null>;
  unverified_facts_per_call: number | null;
  policy_violations_per_call: number | null;
  turns_per_call: number | null;
  agent_tokens_per_call: number | null;
  tone_avg: number | null;
  agent_latency_ms: { mean_per_turn: number | null; uncached_turns: number };
}

export interface Metrics {
  overall: MetricGroup;
  per_persona: Record<string, MetricGroup>;
}

export interface RunDetail extends RunSummary {
  prompt_hash: string;
  judge_prompt_hash: string;
  created_at: string;
  metrics: Metrics | null;
}

export interface CompareResponse {
  runs: RunDetail[];
  warnings: string[];
}

/** kind tells the UI which help to show: start the API, create the DB, or just the message. */
export type ApiErrorKind = "unreachable" | "no_database" | "http";

export class ApiError extends Error {
  constructor(public kind: ApiErrorKind, message: string, public status?: number) {
    super(message);
  }
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  let res: Response;
  try {
    res = await fetch(IS_STATIC ? staticUrl(path) : path, { signal });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError("unreachable", "Could not connect to the API.");
  }
  if (res.ok) return (await res.json()) as T;

  // FastAPI errors are JSON {detail}. A non-JSON 5xx means the Vite proxy couldn't reach uvicorn.
  const body = await res.json().catch(() => null);
  const detail = body && typeof body.detail === "string" ? body.detail : null;
  if (!detail && res.status >= 500) {
    throw new ApiError("unreachable", "Could not connect to the API.", res.status);
  }
  if (res.status === 503 && detail === "database not found") {
    throw new ApiError("no_database", "The API is running but found no database.", 503);
  }
  throw new ApiError("http", detail ?? `Request failed (HTTP ${res.status}).`, res.status);
}

export function getRuns(signal?: AbortSignal): Promise<RunSummary[]> {
  return getJson("/api/runs", signal);
}

export function getRun(runId: number, signal?: AbortSignal): Promise<RunDetail> {
  return getJson(`/api/runs/${runId}`, signal);
}

export function getCalls(runId: number, signal?: AbortSignal): Promise<CallRow[]> {
  return getJson(`/api/runs/${runId}/calls`, signal);
}

export function getCall(runId: number, idx: number, signal?: AbortSignal): Promise<CallDetail> {
  return getJson(`/api/calls/${runId}/${idx}`, signal);
}

export const MAX_COMPARE = 10; // same limit as backend/main.py

export async function getCompare(ids: number[], signal?: AbortSignal): Promise<CompareResponse> {
  if (!IS_STATIC) return getJson(`/api/compare?run_ids=${ids.join(",")}`, signal);
  // No compare file in the snapshot: load each run and add the API's warnings here.
  const runs = await Promise.all([...new Set(ids)].map((id) => getRun(id, signal)));
  return { runs, warnings: compareWarnings(runs) };
}

/** Static mode only: when the snapshot was taken. */
export function getMeta(signal?: AbortSignal): Promise<SnapshotMeta> {
  return getJson("/api/meta", signal);
}
