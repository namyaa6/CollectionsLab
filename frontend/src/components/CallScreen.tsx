import { useMemo, useState } from "react";
import { getCall } from "../api";
import type { Criterion } from "../callTypes";
import { CRITERION_LABELS } from "../format";
import { findQuote, findToolQuote } from "../highlight";
import { href } from "../route";
import { useApi } from "../useApi";
import CallHeader from "./CallHeader";
import ChecksPanel from "./ChecksPanel";
import JudgePanel from "./JudgePanel";
import PlayControls from "./PlayControls";
import { ErrorPanel, Loading } from "./StatusView";
import TranscriptView from "./TranscriptView";
import "./Transcript.css";

interface Props {
  runId: number;
  idx: number;
  showAllJudges: boolean;
  onToggleAllJudges: (v: boolean) => void;
}

// App renders this with key={`${runId}/${idx}`}: a new key makes React start a fresh component,
// so the selected criterion and the loaded data never leak from one call into the next.
export default function CallScreen({ runId, idx, showAllJudges, onToggleAllJudges }: Props) {
  const call = useApi((signal) => getCall(runId, idx, signal), `call-${runId}-${idx}`);
  const [active, setActive] = useState<Criterion | null>(null);
  // Lifted here so the Play controls (which set it) and the transcript (which highlights it) share it.
  const [speaking, setSpeaking] = useState<number | null>(null);
  const c = call.data;

  // useMemo keeps the same location object between renders unless its inputs change, so the
  // transcript's scroll effect fires only when a different quote is selected.
  // The judge quotes spoken text or a tool call line; try spoken text first.
  const { quote, toolQuote } = useMemo(() => {
    const verdict = c?.judge?.verdict;
    if (!active || !verdict || !c?.transcript) return { quote: null, toolQuote: null };
    const turns = c.transcript.turns;
    const evidence = verdict[active].evidence;
    const inText = findQuote(turns.map((t) => t.text), evidence);
    return { quote: inText, toolQuote: inText ? null : findToolQuote(turns.map((t) => t.tool_calls), evidence) };
  }, [c, active]);

  return (
    <section>
      <nav className="crumbs">
        <a href={href.runs}>Runs</a> / <a href={href.calls(runId)}>Run #{runId}</a> / Call #{idx}
      </nav>
      {call.loading && <Loading label="Loading call…" />}
      {call.error != null && <ErrorPanel error={call.error} onRetry={call.reload} />}
      {c && !call.loading && !call.error && (
        <>
          <CallHeader call={c} runId={runId} idx={idx}
            showAllJudges={showAllJudges} onToggleAllJudges={onToggleAllJudges} />
          <div className="call-grid">
            <div className="panel transcript-panel">
              <div className="transcript-head">
                <h2>Transcript</h2>
                <span className="hint">
                  {c.transcript ? `${c.transcript.turns.length} turns` : ""}
                </span>
                <div className="legend hint">
                  <mark className="m-lint">voice lint</mark>
                  <mark className="m-fact">unverified fact</mark>
                  <mark className="m-quote">judge quote</mark>
                </div>
                <div className="transcript-actions">
                  {c.transcript && <PlayControls turns={c.transcript.turns} onSpeaking={setSpeaking} />}
                </div>
              </div>
              {c.transcript ? (
                <TranscriptView turns={c.transcript.turns} checks={c.checks} quote={quote} toolQuote={toolQuote}
                  quoteLabel={active ? `Judge evidence: ${CRITERION_LABELS[active]}` : ""} speaking={speaking} />
              ) : (
                <p className="muted">No transcript stored for this call.</p>
              )}
            </div>
            <aside className="call-side">
              <JudgePanel judge={c.judge} active={active} located={quote != null || toolQuote != null} onSelect={setActive} />
              <ChecksPanel checks={c.checks} summary={c.summary} />
            </aside>
          </div>
        </>
      )}
    </section>
  );
}
