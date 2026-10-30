import { describe, expect, it } from "vitest";
import { href, parseHash } from "./route";

describe("parseHash", () => {
  it("round-trips every href", () => {
    expect(parseHash(href.runs)).toEqual({ name: "runs" });
    expect(parseHash(href.compare)).toEqual({ name: "compare" });
    expect(parseHash(href.calls(2))).toEqual({ name: "calls", runId: 2 });
    expect(parseHash(href.call(2, 3))).toEqual({ name: "call", runId: 2, idx: 3 });
  });

  it("falls back to runs for empty or malformed hashes", () => {
    expect(parseHash("")).toEqual({ name: "runs" });
    expect(parseHash("#/runs/abc/calls")).toEqual({ name: "runs" });
    expect(parseHash("#/runs/2/calls/x")).toEqual({ name: "calls", runId: 2 });
  });
});
