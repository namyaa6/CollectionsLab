// Display helpers: labels, number formatting, run ordering and run colours.
import type { LintCategory, Rate, RateName, RunSummary } from "./api";

export const RATE_LABELS: Record<RateName, string> = {
  identity_verified: "Identity verified",
  judge_task_success: "Task success",
  outcome_pass: "Outcome pass",
  escalation_correct: "Escalation correct",
  hallucination: "Hallucination",
  compliance_violation: "Compliance violation",
  policy_violation: "Policy violation",
  pressure_or_threat: "Pressure / threat",
};

export const HIGHER_IS_BETTER: RateName[] = [
  "identity_verified", "judge_task_success", "outcome_pass", "escalation_correct",
];
export const LOWER_IS_BETTER: RateName[] = [
  "hallucination", "compliance_violation", "policy_violation", "pressure_or_threat",
];

export const LINT_LABELS: Record<LintCategory, string> = {
  symbols_markdown: "Symbols / markdown",
  long_turn: "Long turn",
  digit_amount: "Digit amount",
  numeric_date: "Numeric date",
  code_token: "Code token",
  unspelled_contact: "Unspelled contact",
};

/** Validated categorical palette (dataviz reference, light mode), in fixed order. */
const RUN_COLORS = [
  "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948",
];

export function runColor(index: number): string {
  return RUN_COLORS[index % RUN_COLORS.length];
}

export function pct(x: number | null | undefined, digits = 0): string {
  return x == null ? "—" : `${(x * 100).toFixed(digits)}%`;
}

export function num(x: number | null | undefined, digits = 2): string {
  return x == null ? "—" : x.toFixed(digits);
}

/** "13/30 · 95% CI 27–60%", or a note when the rate had no denominator. */
export function rateDetail(r: Rate | null | undefined): string {
  if (!r) return "not computed";
  if (r.rate == null) return `n/a (0 eligible calls)`;
  return `${r.k}/${r.n} · 95% CI ${pct(r.ci_low)}–${pct(r.ci_high)}`;
}

export function runLabel(run: Pick<RunSummary, "id" | "prompt_version" | "judge_version">): string {
  return `${run.prompt_version} · judge ${run.judge_version} · #${run.id}`;
}

export function personaLabel(p: string): string {
  const s = p.replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** Prompt version with natural ordering (v2 < v10), then id. Colours follow this order. */
export function sortRuns<T extends Pick<RunSummary, "id" | "prompt_version">>(runs: T[]): T[] {
  return [...runs].sort(
    (a, b) =>
      a.prompt_version.localeCompare(b.prompt_version, undefined, { numeric: true }) ||
      a.id - b.id,
  );
}
