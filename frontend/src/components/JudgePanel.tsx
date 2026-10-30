import { JUDGE_BOOLS, type Criterion, type JudgeRecord } from "../callTypes";
import { CRITERION_LABELS, GOOD_VALUE } from "../format";

interface Props {
  judge: JudgeRecord | null;
  active: Criterion | null;
  located: boolean; // whether the active quote was found in one turn's text or one tool call
  onSelect: (c: Criterion | null) => void;
}

function VerdictPill({ c, judge }: { c: Criterion; judge: NonNullable<JudgeRecord["verdict"]> }) {
  if (c === "tone") return <span className="pill pill-neutral">{judge.tone.score} / 5</span>;
  const value = judge[c].value;
  const good = value === GOOD_VALUE[c];
  return <span className={good ? "pill pill-pass" : "pill pill-fail"}>{value ? "Yes" : "No"}</span>;
}

export default function JudgePanel({ judge, active, located, onSelect }: Props) {
  const verdict = judge?.verdict;
  return (
    <div className="panel side-card">
      <div className="card-head">
        <h3>LLM judge</h3>
        {judge && <span className="hint mono">{judge.judge_version}</span>}
      </div>
      {!verdict ? (
        <p className="muted small">{judge?.error ? `Judge failed: ${judge.error}` : "This call was not judged."}</p>
      ) : (
        <>
          <p className="hint side-note">Click a criterion to find its evidence in the transcript.</p>
          <ul className="criteria">
            {[...JUDGE_BOOLS, "tone" as const].map((c) => {
              const evidence = verdict[c].evidence.trim();
              const found = judge?.evidence_found?.[c];
              const isActive = active === c;
              return (
                <li key={c}>
                  <button
                    className={isActive ? "criterion active" : "criterion"}
                    disabled={!evidence}
                    onClick={() => onSelect(isActive ? null : c)}
                    aria-pressed={isActive}
                  >
                    <span className="crit-head">
                      <span className="crit-name">{CRITERION_LABELS[c]}</span>
                      <VerdictPill c={c} judge={verdict} />
                    </span>
                    {evidence ? <q className="crit-quote">{evidence}</q> : <span className="muted small">no quote</span>}
                    {found === false && (
                      <span className="crit-warn">⚠ Quote not found in the transcript (the judge may have paraphrased).</span>
                    )}
                    {isActive && found !== false && !located && (
                      <span className="crit-warn">Quote isn't inside a single turn or tool call (it may span turns or quote the policy), so it can't be highlighted.</span>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </div>
  );
}
