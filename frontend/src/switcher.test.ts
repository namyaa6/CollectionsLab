import { describe, expect, it } from "vitest";
import type { RunSummary } from "./api";
import { switcherRuns } from "./switcher";

function run(id: number, prompt_version: string, judge_version: string, updated_at: string, seed = 42) {
  return { id, prompt_version, judge_version, updated_at, seed } as RunSummary;
}

const RUNS = [
  run(1, "v1", "j1", "2026-10-30T10:00"),
  run(2, "v2", "j1", "2026-10-30T11:00"),
  run(3, "v1", "j2", "2026-10-31T09:00"),
  run(4, "v2", "j2", "2026-10-31T09:30"),
  run(5, "v2", "j2", "2026-10-31T12:00"), // newer rerun of v2 · j2
  run(6, "v1", "j2", "2026-10-31T13:00", 7), // other seed: different scenario pool
];

const ids = (c: { runs: RunSummary[] }) => c.runs.map((r) => r.id);

describe("switcherRuns", () => {
  it("shows only the current judge by default and keeps the newest duplicate", () => {
    const c = switcherRuns(RUNS, 3, false);
    expect(ids(c)).toEqual([3, 5]);
    expect(c.hasOtherJudges).toBe(true);
    expect(c.labelJudge).toBe(true);
  });

  it("shows every judge when asked", () => {
    expect(ids(switcherRuns(RUNS, 1, true))).toEqual([1, 3, 2, 5]);
  });

  it("always keeps the current run, even when a newer duplicate exists", () => {
    expect(ids(switcherRuns(RUNS, 4, false))).toEqual([3, 4]);
  });

  it("does not label judges when only one judge version exists", () => {
    const c = switcherRuns(RUNS.slice(0, 2), 1, false);
    expect(ids(c)).toEqual([1, 2]);
    expect(c.labelJudge).toBe(false);
    expect(c.hasOtherJudges).toBe(false);
  });

  it("returns nothing when the current run is unknown", () => {
    expect(ids(switcherRuns(RUNS, 99, false))).toEqual([]);
  });
});
