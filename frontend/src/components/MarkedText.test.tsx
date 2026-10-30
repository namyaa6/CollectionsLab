import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { lintMarks, TURN } from "../testData";
import MarkedText from "./MarkedText";

const stripTags = (html: string) => html.replace(/<[^>]+>/g, "");

describe("MarkedText", () => {
  it("renders exactly the original text: no whitespace added between or inside marks", () => {
    const html = renderToStaticMarkup(<MarkedText text={TURN} marks={lintMarks()} />);
    const plain = renderToStaticMarkup(<>{TURN}</>); // same HTML escaping, no marks
    expect(stripTags(html)).toBe(plain);
    expect(html).toContain('<mark class="m-lint" title="L2">invoice INV-2026-1022 for Narmada</mark>');
    expect(html).toContain("<mark class=\"m-lint\" title=\"L0 · L1\">balance of ₹1,70,300 which is</mark>");
  });

  it("renders back-to-back marks of different kinds with nothing between them", () => {
    const text = "alpha beta";
    const html = renderToStaticMarkup(
      <MarkedText text={text} marks={[
        { start: 0, end: 5, kind: "fact", label: "f" }, { start: 6, end: 10, kind: "lint", label: "l" },
        { start: 3, end: 8, kind: "quote", label: "q" },
      ]} />,
    );
    expect(stripTags(html)).toBe(text);
  });
});
