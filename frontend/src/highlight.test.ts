import { describe, expect, it } from "vitest";
import {
  buildSegments, findQuote, findToolQuote, locateSnippet, normalizeWithMap, prepareMarks, snapToWords,
  type Mark,
} from "./highlight";
import { lintMarks, TURN } from "./testData";

describe("normalizeWithMap", () => {
  it("matches the backend _norm and maps back to the original text", () => {
    const text = "  Hello,  WORLD!! It's 4,838. ";
    const { norm, map } = normalizeWithMap(text);
    expect(norm).toBe("hello world it s 4 838");
    expect(text[map[norm.indexOf("world")]]).toBe("W");
    expect(map.length).toBe(norm.length);
  });
});

describe("findQuote", () => {
  const turns = [
    "Hello, is this Kavita Sheikh?",
    "Yes. Make it quick!",
    "I have recorded your promise to pay on the fifth of November.",
  ];

  it("ignores case and punctuation and returns original offsets", () => {
    const loc = findQuote(turns, "recorded your promise to pay, on the FIFTH of november");
    expect(loc).not.toBeNull();
    expect(turns[loc!.turn].slice(loc!.start, loc!.end)).toBe(
      "recorded your promise to pay on the fifth of November",
    );
  });

  it("strips a judge-style speaker prefix", () => {
    expect(findQuote(turns, "[1] DEBTOR: Yes. Make it quick")?.turn).toBe(1);
  });

  it("returns null for an empty quote, a missing quote or one spanning turns", () => {
    expect(findQuote(turns, "")).toBeNull();
    expect(findQuote(turns, "you will be sued")).toBeNull();
    expect(findQuote(turns, "Kavita Sheikh? Yes. Make it quick")).toBeNull();
  });
});

describe("findToolQuote", () => {
  const calls = [
    [],
    [{ tool: "log_promise_to_pay", args: { date: "2026-11-05", amount_inr: 4838 }, result: { status: "logged" } }],
  ];

  it("matches a quote in Python json.dumps spacing against the rendered tool line", () => {
    const quote = 'log_promise_to_pay({"date": "2026-11-05", "amount_inr": 4838}) -> {"status": "logged"}';
    expect(findToolQuote(calls, quote)).toEqual({ turn: 1, tool: 0 });
  });

  it("returns null when no tool line contains the quote", () => {
    expect(findToolQuote(calls, "escalate_to_human")).toBeNull();
    expect(findToolQuote(calls, "")).toBeNull();
  });
});

describe("locateSnippet", () => {
  it("finds a snippet whose newlines the backend replaced with spaces", () => {
    expect(locateSnippet("Pay Rs\n500 today", "Rs 500")).toEqual({ start: 4, end: 10 });
    expect(locateSnippet("nothing here", "Rs 500")).toBeNull();
  });
});

const slice = (m: { start: number; end: number }) => TURN.slice(m.start, m.end);

describe("snapToWords", () => {
  it("drops the partial padding words at either edge", () => {
    const [a, b, c] = lintMarks();
    expect(slice(snapToWords(TURN, a.start, a.end))).toBe("balance of ₹1,70,300");
    expect(slice(snapToWords(TURN, b.start, b.end))).toBe("balance of ₹1,70,300 which is");
    expect(slice(snapToWords(TURN, c.start, c.end))).toBe("invoice INV-2026-1022 for Narmada");
  });

  it("keeps a whole word that ends before punctuation", () => {
    const text = "Pay on the fifth of November.";
    expect(snapToWords(text, 11, 28)).toEqual({ start: 11, end: 28 });
  });

  it("widens to the whole word when only a partial word was marked", () => {
    expect(slice(snapToWords(TURN, TURN.indexOf("urrent"), TURN.indexOf("urrent") + 4))).toBe("currently");
  });
});

describe("prepareMarks", () => {
  it("merges overlapping marks of the same kind into one mark with both labels", () => {
    const merged = prepareMarks(TURN, lintMarks());
    expect(merged.map(slice)).toEqual(["invoice INV-2026-1022 for Narmada", "balance of ₹1,70,300 which is"]);
    expect(merged[1].label).toBe("L0 · L1");
  });

  it("merges same-kind marks separated only by whitespace, never marks of different kinds", () => {
    const text = "one two three";
    const marks: Mark[] = [
      { start: 0, end: 3, kind: "lint", label: "a" }, { start: 4, end: 7, kind: "lint", label: "b" },
      { start: 8, end: 13, kind: "fact", label: "c" },
    ];
    expect(prepareMarks(text, marks).map((m) => [text.slice(m.start, m.end), m.kind])).toEqual([
      ["three", "fact"], ["one two", "lint"],
    ]);
  });
});

describe("buildSegments", () => {
  it("gives overlapping characters to the higher-priority mark", () => {
    const text = "alpha beta gamma delta";
    const fact: Mark = { start: 0, end: 10, kind: "fact", label: "f" };
    const quote: Mark = { start: 6, end: 16, kind: "quote", label: "q" };
    expect(buildSegments(text, [fact, quote]).map((s) => [s.text, s.mark?.kind ?? null])).toEqual([
      ["alpha ", "fact"], ["beta gamma", "quote"], [" delta", null],
    ]);
  });

  it("joins back to exactly the original text and never splits a marked word", () => {
    const segs = buildSegments(TURN, lintMarks());
    expect(segs.map((s) => s.text).join("")).toBe(TURN);
    expect(segs.filter((s) => s.mark).map((s) => s.text)).toEqual([
      "invoice INV-2026-1022 for Narmada", "balance of ₹1,70,300 which is",
    ]);
    for (let k = 1; k < segs.length; k++) {
      const boundaryInsideWord = /[\p{L}\p{N}]$/u.test(segs[k - 1].text) && /^[\p{L}\p{N}]/u.test(segs[k].text);
      expect(boundaryInsideWord).toBe(false);
    }
  });

  it("returns one plain segment without marks", () => {
    expect(buildSegments("plain", [])).toEqual([{ text: "plain", mark: null }]);
  });
});
