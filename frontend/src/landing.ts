// Pure logic for the Runs landing page: which run stands for each prompt version, the headline
// numbers, and the best/worst cells per column. Values are read from the stored headline;
// nothing here recomputes a metric (a percentage change is the only arithmetic).
import type { Rate, RateName, RunSummary } from "./api";
import { HIGHER_IS_BETTER } from "./format";

/** "j2" -> 2, so j10 sorts after j9; -1 when there is no number. */
export function judgeOrder(version: string): number {
  const m = version.match(/\d+/);
  return m ? Number(m[0]) : -1;
}

/** "j2" -> "Judge v2". */
export function judgeLabel(version: string): string {
  const m = version.match(/^j(\d+)$/);
  return m ? `Judge v${m[1]}` : `Judge ${version}`;
}

export function showJudgeColumn(runs: Pick<RunSummary, "judge_version">[]): boolean {
  return new Set(runs.map((r) => r.judge_version)).size > 1;
}

/**
 * The run that represents a prompt version: among its runs with metrics, the newest judge
 * version, then the most recently updated. The same rule as the results export, so the dev
 * dashboard and the static snapshot pick the same runs.
 */
export function pickRun(runs: RunSummary[], version: string): RunSummary | null {
  const candidates = runs.filter((r) => r.prompt_version === version && r.headline);
  candidates.sort((a, b) =>
    judgeOrder(b.judge_version) - judgeOrder(a.judge_version)
    || b.updated_at.localeCompare(a.updated_at) || b.id - a.id);
  return candidates[0] ?? null;
}

export interface HeadlineStats {
  /** Speech issues (voice-lint problems) per call, first -> last version. */
  speech: { from: number; to: number; change: number | null } | null;
  identity: { from: Rate; to: Rate } | null;
  /** Calls that finished and were graded, across one run per prompt version. */
  callsGraded: number;
  versions: number;
}

export function headlineStats(runs: RunSummary[], first = "v1", last = "v4"): HeadlineStats {
  const versions = [...new Set(runs.filter((r) => r.headline).map((r) => r.prompt_version))];
  const picked = versions.map((v) => pickRun(runs, v)).filter((r): r is RunSummary => r != null);
  const a = pickRun(runs, first)?.headline;
  const b = pickRun(runs, last)?.headline;
  let speech: HeadlineStats["speech"] = null;
  if (a?.lint_total_per_call != null && b?.lint_total_per_call != null) {
    const from = a.lint_total_per_call, to = b.lint_total_per_call;
    speech = { from, to, change: from > 0 ? (to - from) / from : null };
  }
  const idA = a?.identity_verified, idB = b?.identity_verified;
  return {
    speech,
    identity: idA && idB ? { from: idA, to: idB } : null,
    callsGraded: picked.reduce((sum, r) => sum + r.n_ok, 0),
    versions: picked.length,
  };
}

export type ColumnKey = RateName | "lint_total_per_call";

export function columnValue(run: RunSummary, key: ColumnKey): number | null {
  const h = run.headline;
  if (!h) return null;
  return key === "lint_total_per_call" ? h.lint_total_per_call : h[key]?.rate ?? null;
}

export function higherIsBetter(key: ColumnKey): boolean {
  return key !== "lint_total_per_call" && HIGHER_IS_BETTER.includes(key);
}

/**
 * Run ids holding the best and the worst value in a column. Ties all get the same mark, but
 * a mark is only given when it singles out a minority: if more than half of the runs share
 * the best (or worst) value, those cells stay unmarked. Empty when fewer than two distinct
 * values exist (nothing to tell apart).
 */
export function columnExtremes(runs: RunSummary[], key: ColumnKey): { best: Set<number>; worst: Set<number> } {
  const cells = runs.flatMap((r) => {
    const v = columnValue(r, key);
    return v == null ? [] : [{ id: r.id, v: Math.round(v * 1e6) / 1e6 }];
  });
  const values = cells.map((c) => c.v);
  const hi = Math.max(...values), lo = Math.min(...values);
  if (cells.length < 2 || hi === lo) return { best: new Set(), worst: new Set() };
  const [best, worst] = higherIsBetter(key) ? [hi, lo] : [lo, hi];
  const minority = (value: number) => {
    const ids = cells.filter((c) => c.v === value).map((c) => c.id);
    return new Set(ids.length > cells.length / 2 ? [] : ids);
  };
  return { best: minority(best), worst: minority(worst) };
}

/** What each column measures, shown as a header tooltip. */
export const COLUMN_HELP: Record<string, string> = {
  run: "Run number in the results database.",
  version: "Which version of the agent's instructions (prompt) was tested.",
  judge: "Which version of the AI judge's grading instructions scored the calls.",
  status: "Complete when every requested call finished and was scored.",
  calls: "Calls that finished, out of the calls requested.",
  identity_verified: "Share of calls where the agent confirmed it was talking to the right "
    + "person before mentioning money (AI judge). Higher is better.",
  judge_task_success: "Share of calls that ended in an outcome the policy allows (AI judge). "
    + "Higher is better.",
  hallucination: "Share of calls where the agent stated a fact that isn't in the invoice, "
    + "tool results or policy (AI judge). Lower is better.",
  compliance_violation: "Share of calls where the agent broke a policy rule (AI judge). "
    + "Lower is better.",
  policy_violation: "Share of calls where code checks found a broken policy rule, such as "
    + "installment limits or date windows. Lower is better.",
  lint_total_per_call: "Average problems per call that break text-to-speech: symbols, digits, "
    + "codes read aloud, long turns (code check). Lower is better.",
};
