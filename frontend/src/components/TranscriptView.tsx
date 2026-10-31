import { useEffect, useRef } from "react";
import type { LintCategory } from "../api";
import type { Checks, Turn } from "../callTypes";
import { LINT_LABELS } from "../format";
import { locateSnippet, type Mark, type QuoteLocation, type ToolQuoteLocation } from "../highlight";
import MarkedText from "./MarkedText";
import { SelfCheckBlock, ToolCallRow } from "./TurnExtras";

export function scrollToTurn(i: number) {
  document.getElementById(`turn-${i}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
}

function lintLabel(category: string): string {
  return LINT_LABELS[category as LintCategory] ?? category;
}

/** Lint snippets and unverified facts for one turn, plus the active judge quote if it is here. */
function marksFor(i: number, text: string, checks: Checks | null, quote: QuoteLocation | null,
                  quoteLabel: string): Mark[] {
  const marks: Mark[] = [];
  for (const v of checks?.voice_violations ?? []) {
    if (v.turn !== i || v.category === "long_turn") continue; // long_turn's snippet is a summary
    const at = locateSnippet(text, v.snippet);
    if (at) marks.push({ ...at, kind: "lint", label: `Voice lint: ${lintLabel(v.category)}` });
  }
  for (const f of checks?.facts.items ?? []) {
    if (f.turn !== i || f.status !== "unverified") continue;
    const at = locateSnippet(text, f.snippet);
    if (at) marks.push({ ...at, kind: "fact", label: `Unverified ${f.kind}: ${f.value}` });
  }
  if (quote && quote.turn === i) marks.push({ start: quote.start, end: quote.end, kind: "quote", label: quoteLabel });
  return marks;
}

function TurnView({ i, turn, checks, quote, quoteLabel, activeTool, speaking }: {
  i: number; turn: Turn; checks: Checks | null; quote: QuoteLocation | null; quoteLabel: string;
  activeTool: number | null; speaking: boolean;
}) {
  const lint = (checks?.voice_violations ?? []).filter((v) => v.turn === i);
  const isAgent = turn.speaker === "agent";
  return (
    <div className={`turn ${isAgent ? "turn-agent" : "turn-debtor"}${speaking ? " turn-speaking" : ""}`} id={`turn-${i}`}>
      <div className="turn-meta">
        <span className="mono">#{i}</span> {isAgent ? "Agent" : "Debtor"}
        {isAgent && turn.latency_ms > 0 && <span> · {(turn.latency_ms / 1000).toFixed(1)}s</span>}
        {turn.cached && <span> · cached</span>}
      </div>
      <div className={lint.length > 0 ? "bubble has-lint" : "bubble"}>
        {turn.text.trim() === "" ? (
          <span className="muted">(no speech)</span>
        ) : (
          <MarkedText text={turn.text} marks={marksFor(i, turn.text, checks, quote, quoteLabel)} />
        )}
      </div>
      {turn.error && <div className="turn-error">Error: {turn.error}</div>}
      {lint.length > 0 && (
        <div className="chips">
          {lint.map((v, k) => (
            <span key={k} className="chip chip-lint" title={v.snippet}>{lintLabel(v.category)}</span>
          ))}
        </div>
      )}
      {turn.tool_calls.length > 0 && (
        <div className="tool-rows">
          {turn.tool_calls.map((c, k) => <ToolCallRow key={k} call={c} active={activeTool === k} />)}
        </div>
      )}
      {turn.self_check && <SelfCheckBlock check={turn.self_check} />}
    </div>
  );
}

export default function TranscriptView({ turns, checks, quote, toolQuote, quoteLabel, speaking }: {
  turns: Turn[]; checks: Checks | null; quote: QuoteLocation | null; toolQuote: ToolQuoteLocation | null;
  quoteLabel: string; speaking: number | null;
}) {
  // useRef holds a pointer to the real DOM element. Scrolling is a side effect on the page,
  // not something to render, so it runs in useEffect after React has drawn the highlight.
  const listRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!quote && !toolQuote) return;
    listRef.current?.querySelector("mark.m-quote, .tool-row.active")
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [quote, toolQuote]);
  useEffect(() => {
    if (speaking != null) scrollToTurn(speaking);
  }, [speaking]);

  return (
    <div className="turns" ref={listRef}>
      {turns.map((t, i) => (
        <TurnView key={i} i={i} turn={t} checks={checks} quote={quote} quoteLabel={quoteLabel}
          activeTool={toolQuote?.turn === i ? toolQuote.tool : null} speaking={speaking === i} />
      ))}
    </div>
  );
}
