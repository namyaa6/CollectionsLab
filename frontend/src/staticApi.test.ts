import { describe, expect, it } from "vitest";
import { compareWarnings, IS_STATIC, staticUrl } from "./staticApi";

describe("staticUrl", () => {
  it("maps each API path to its file under static-api/", () => {
    expect(staticUrl("/api/runs", "./")).toBe("./static-api/runs.json");
    expect(staticUrl("/api/runs/3", "./")).toBe("./static-api/runs/3.json");
    expect(staticUrl("/api/runs/3/calls", "./")).toBe("./static-api/runs/3/calls.json");
    expect(staticUrl("/api/calls/3/12", "/x/")).toBe("/x/static-api/calls/3/12.json");
    expect(staticUrl("/api/meta", "./")).toBe("./static-api/meta.json");
  });

  it("is off in tests and the normal build", () => {
    expect(IS_STATIC).toBe(false);
  });
});

// Same cases and strings as backend/api_shapes.py compare_warnings().
describe("compareWarnings", () => {
  it("is empty for complete runs by one judge", () => {
    const runs = [{ id: 1, judge_version: "j2", status: "complete" as const },
      { id: 2, judge_version: "j2", status: "complete" as const }];
    expect(compareWarnings(runs)).toEqual([]);
  });

  it("flags mixed judges and incomplete runs", () => {
    const runs = [{ id: 2, judge_version: "j2", status: "partial" as const },
      { id: 1, judge_version: "j1", status: "complete" as const },
      { id: 3, judge_version: "j1", status: "no_metrics" as const }];
    expect(compareWarnings(runs)).toEqual([
      "Runs were judged by different judge versions (j1, j2); judge-based rates are not directly comparable.",
      "Run 2 is partial.",
      "Run 3 is no metrics.",
    ]);
  });
});
