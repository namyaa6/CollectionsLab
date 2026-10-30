// Types for the two call endpoints. They mirror the stored JSON (backend/api_shapes.py call_row,
// backend/sim/transcript.py, backend/eval/*, backend/agent/self_check.py) and recompute nothing.

export const JUDGE_BOOLS = [
  "task_success", "hallucination", "compliance_violation", "escalation_correct",
  "identity_verified_before_amounts", "pressure_or_threat",
] as const;
export type JudgeBool = (typeof JUDGE_BOOLS)[number];
export type Criterion = JudgeBool | "tone";

/** GET /api/runs/{id}/calls: one row per call, no transcript. */
export interface CallRow {
  idx: number;
  persona: string;
  status: "ok" | "failed";
  error: string | null;
  outcome: string | null;
  passed: boolean | null;
  lint_total: number | null;
  judge_flags: Record<JudgeBool, boolean> | null;
  tone: number | null;
  judge_version: string | null;
}

export interface ToolCall {
  tool: string;
  args: Record<string, unknown>;
  result: unknown;
}

/** v4+ only: the agent's draft, what was spoken, and what the check found. */
export interface SelfCheck {
  draft: string;
  final: string;
  revised: boolean;
  issues: string[];
  error: string | null;
}

export interface Turn {
  speaker: "agent" | "debtor";
  text: string;
  tool_calls: ToolCall[];
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  cached: boolean;
  error: string | null;
  self_check: SelfCheck | null;
}

export interface Transcript {
  turns: Turn[];
  end_reason: string;
  end_detail: string | null;
  totals: {
    agent_turns: number;
    debtor_turns: number;
    agent_latency_ms: number;
    agent_input_tokens: number;
    agent_output_tokens: number;
    debtor_input_tokens: number;
    debtor_output_tokens: number;
  };
}

/** `turn` indexes the full turns array (agent and debtor). */
export interface LintViolation { turn: number; category: string; snippet: string }
export interface FactItem { turn: number; kind: string; status: string; snippet: string; value: string }

export interface Checks {
  voice_violations: LintViolation[];
  voice_counts: Record<string, number>;
  facts: { matched: number; unverified: number; unparsed: number; items: FactItem[] };
  policy_violations: { rule: string; detail: string }[];
  outcome: { passed: boolean; outcome: string; expected: string[] };
}

export interface JudgeRecord {
  verdict:
    | ({ [K in JudgeBool]: { value: boolean; evidence: string } } & {
        tone: { score: number; evidence: string };
      })
    | null;
  evidence_found: Record<Criterion, boolean> | null;
  judge_version: string;
  error: string | null;
}

export interface CallSummary {
  outcome: string;
  promise_date: string | null;
  amount_inr: number | null;
  installment_plan: { date: string; amount_inr: number }[] | null;
  dispute_reason: string | null;
  payment_claim: { utr: string; date: string; amount_inr: number } | null;
  escalated: boolean;
  next_action: string | null;
  discrepancies: string[];
}

/** GET /api/calls/{run_id}/{idx}. Failed calls may have null transcript, checks, judge or summary. */
export interface CallDetail {
  run_id: number;
  idx: number;
  status: "ok" | "failed";
  error: string | null;
  scenario: { persona: string; expected_outcomes: string[]; invoice: Record<string, unknown> };
  transcript: Transcript | null;
  summary: CallSummary | null;
  checks: Checks | null;
  judge: JudgeRecord | null;
  latency_ms: number | null;
  tokens: number | null;
  prompt_version: string;
  judge_version: string;
  models: { agent: string; sim: string; judge: string };
}
