import { describe, expect, it } from "vitest";
import type { Headline, Rate, RunSummary } from "./api";
import {
  columnExtremes, headlineStats, judgeLabel, pickRun, showJudgeColumn,
} from "./landing";

function rate(k: number, n = 14): Rate {
  return { k, n, rate: k / n, ci_low: 0, ci_high: 1 };
}

function run(id: number, version: string, judge: string, updated: string,
  h: Partial<Headline> | null = {}, nOk = 14): RunSummary {
  return {
    id, run_key: `key${id}`, prompt_version: version, judge_version: judge,
    models: { agent: "a", sim: "s", judge: "j" }, n: 14, seed: 42, n_calls_stored: nOk,
    n_ok: nOk, n_failed: 0, status: "complete", complete: true, updated_at: updated,
    headline: h && { lint_total_per_call: null, tone_avg: null, turns_per_call: null, ...h },
  };
}

// Mirrors the real data: j1 runs #1-#2 and j2 runs #4-#7 (the j2 ones are newer).
const RUNS = [
  run(1, "v1", "j1", "2026-10-30T12:00", { lint_total_per_call: 8.93, identity_verified: rate(7) }),
  run(2, "v2", "j1", "2026-10-30T13:00", { lint_total_per_call: 0.36 }),
  run(3, "v3", "j1", "2026-10-30T13:10", null, 10),  // partial, no metrics
  run(4, "v1", "j2", "2026-10-31T14:34", { lint_total_per_call: 8.93, identity_verified: rate(6) }),
  run(5, "v2", "j2", "2026-10-31T14:35", { lint_total_per_call: 0.36, identity_verified: rate(13) }),
  run(6, "v3", "j2", "2026-10-31T14:42", { lint_total_per_call: 0.36, identity_verified: rate(14) }),
  run(7, "v4", "j2", "2026-10-31T14:43", { lint_total_per_call: 0.29, identity_verified: rate(14) }),
];

describe("pickRun", () => {
  it("prefers the newest judge version, then the latest update", () => {
    expect(pickRun(RUNS, "v1")?.id).toBe(4);
    const older = run(8, "v1", "j10", "2026-10-01T00:00", {});  // j10 beats j2 even though older
    expect(pickRun([...RUNS, older], "v1")?.id).toBe(8);
    const sameJudge = run(9, "v4", "j2", "2026-11-01T00:00", {});
    expect(pickRun([...RUNS, sameJudge], "v4")?.id).toBe(9);
  });

  it("skips runs without metrics and returns null for a missing version", () => {
    expect(pickRun(RUNS, "v3")?.id).toBe(6);
    expect(pickRun(RUNS.filter((r) => r.id !== 6), "v3")).toBeNull();
    expect(pickRun(RUNS, "v9")).toBeNull();
  });
});

describe("headlineStats", () => {
  it("reads v1 -> v4 from the representative runs only", () => {
    const s = headlineStats(RUNS);
    expect(s.speech?.from).toBe(8.93);
    expect(s.speech?.to).toBe(0.29);
    expect(s.speech?.change).toBeCloseTo(-0.9675, 3);
    expect(s.identity?.from.k).toBe(6);  // run 4 (j2), not run 1 (j1)
    expect(s.identity?.to.k).toBe(14);
    expect(s.callsGraded).toBe(56);  // runs 4-7 only: no j1 duplicates, no partial run
    expect(s.versions).toBe(4);
  });

  it("leaves a stat out when a version is missing", () => {
    const s = headlineStats(RUNS.filter((r) => r.prompt_version !== "v4"));
    expect(s.speech).toBeNull();
    expect(s.identity).toBeNull();
    expect(s.callsGraded).toBe(42);
  });
});

describe("columnExtremes", () => {
  it("marks best and worst by direction, ignoring runs without metrics", () => {
    const ex = columnExtremes(RUNS.slice(3), "identity_verified");  // higher is better
    expect([...ex.best].sort()).toEqual([6, 7]);  // tie for 14/14: both tinted
    expect([...ex.worst]).toEqual([4]);
    const lint = columnExtremes(RUNS.slice(3), "lint_total_per_call");  // lower is better
    expect([...lint.best]).toEqual([7]);
    expect([...lint.worst]).toEqual([4]);
  });

  it("marks every tied run when the tie is a minority", () => {
    // lint: 8.93 (runs 1, 4), 0.36 (2, 5, 6), 0.29 (7): 2 of 6 tie for worst
    const ex = columnExtremes(RUNS, "lint_total_per_call");
    expect([...ex.worst].sort()).toEqual([1, 4]);
    expect([...ex.best]).toEqual([7]);
    // identity in the final runs: 6, 13, 14, 14 of 14; 2 of 4 tie for best (not a majority)
    const id = columnExtremes(RUNS.slice(3), "identity_verified");
    expect([...id.best].sort()).toEqual([6, 7]);
    expect([...id.worst]).toEqual([4]);
  });

  it("leaves a value unmarked when more than half the runs share it", () => {
    // hallucination like the final runs: v1 0/14, v2 1/14, v3 0/14, v4 0/14
    const runs = [run(4, "v1", "j2", "t", { hallucination: rate(0) }),
      run(5, "v2", "j2", "t", { hallucination: rate(1) }),
      run(6, "v3", "j2", "t", { hallucination: rate(0) }),
      run(7, "v4", "j2", "t", { hallucination: rate(0) })];
    const ex = columnExtremes(runs, "hallucination");
    expect(ex.best.size).toBe(0);  // 3 of 4 share 0%: not singled out
    expect([...ex.worst]).toEqual([5]);  // only v2's 7%
  });

  it("marks nothing when all values are equal or fewer than two exist", () => {
    const same = [run(1, "v1", "j2", "t", { hallucination: rate(0) }),
      run(2, "v2", "j2", "t", { hallucination: rate(0) })];
    expect(columnExtremes(same, "hallucination").best.size).toBe(0);
    expect(columnExtremes(same.slice(0, 1), "hallucination").worst.size).toBe(0);
  });
});

describe("judge helpers", () => {
  it("labels and hides the judge column when only one version exists", () => {
    expect(judgeLabel("j2")).toBe("Judge v2");
    expect(judgeLabel("custom")).toBe("Judge custom");
    expect(showJudgeColumn(RUNS)).toBe(true);
    expect(showJudgeColumn(RUNS.slice(3))).toBe(false);
  });
});
