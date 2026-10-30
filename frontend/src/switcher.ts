// Which runs the "same scenario in another run" switcher offers.
import type { RunSummary } from "./api";
import { sortRuns } from "./format";

export interface SwitcherChoice {
  runs: RunSummary[];
  /** True when runs with this seed were judged by more than one judge version: label "v1 · j2". */
  labelJudge: boolean;
  /** True when some runs are hidden because their judge differs (offer "show all judges"). */
  hasOtherJudges: boolean;
}

/**
 * Same idx = same scenario only when the pool came from the same seed, so other seeds are dropped.
 * By default only runs judged like the current one are shown. Where several runs share prompt
 * and judge version, the most recently updated wins, except that the current run is always kept.
 */
export function switcherRuns(all: RunSummary[], currentId: number, showAllJudges: boolean): SwitcherChoice {
  const current = all.find((r) => r.id === currentId);
  if (!current) return { runs: [], labelJudge: false, hasOtherJudges: false };

  const sameSeed = all.filter((r) => r.seed === current.seed);
  const hasOtherJudges = sameSeed.some((r) => r.judge_version !== current.judge_version);
  const pool = showAllJudges ? sameSeed : sameSeed.filter((r) => r.judge_version === current.judge_version);

  const best = new Map<string, RunSummary>();
  for (const r of pool) {
    const key = `${r.prompt_version}\u0000${r.judge_version}`;
    const kept = best.get(key);
    if (!kept || (kept.id !== currentId && (r.id === currentId || isNewer(r, kept)))) best.set(key, r);
  }
  return { runs: sortRuns([...best.values()]), labelJudge: hasOtherJudges, hasOtherJudges };
}

function isNewer(a: RunSummary, b: RunSummary): boolean {
  if (a.updated_at !== b.updated_at) return a.updated_at > b.updated_at; // ISO timestamps sort as text
  return a.id > b.id;
}
