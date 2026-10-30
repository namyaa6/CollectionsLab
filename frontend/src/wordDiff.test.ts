import { describe, expect, it } from "vitest";
import { wordDiff } from "./wordDiff";

describe("wordDiff", () => {
  it("marks a replaced word as del + add between unchanged runs", () => {
    expect(wordDiff("You owe five hundred rupees.", "You owe five thousand rupees.")).toEqual([
      { op: "same", text: "You owe five" },
      { op: "del", text: "hundred" },
      { op: "add", text: "thousand" },
      { op: "same", text: "rupees." },
    ]);
  });

  it("handles identical, empty and fully new text", () => {
    expect(wordDiff("Thanks, bye.", "Thanks,  bye.")).toEqual([{ op: "same", text: "Thanks, bye." }]);
    expect(wordDiff("", "Hello there")).toEqual([{ op: "add", text: "Hello there" }]);
    expect(wordDiff("Old words", "")).toEqual([{ op: "del", text: "Old words" }]);
  });
});
