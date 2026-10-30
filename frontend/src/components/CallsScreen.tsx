import { useState } from "react";
import { getCalls, getRun } from "../api";
import type { CallRow, JudgeBool } from "../callTypes";
import { GOOD_VALUE, num, personaLabel, promptDescription, words } from "../format";
import { href, navigate } from "../route";
import { useApi } from "../useApi";
import "./Calls.css";
import { StatusPill } from "./RunsScreen";
import { ErrorPanel, Loading } from "./StatusView";

const FLAG_CHIPS: { key: JudgeBool; label: string }[] = [
  { key: "hallucination", label: "Hallucination" },
  { key: "compliance_violation", label: "Compliance" },
  { key: "identity_verified_before_amounts", label: "Identity" },
  { key: "pressure_or_threat", label: "Pressure" },
];

/** Chips for the judge flags that went the bad way (no chips when the call was not judged). */
export function badFlags(flags: CallRow["judge_flags"]): string[] {
  if (!flags) return [];
  return FLAG_CHIPS.filter((c) => flags[c.key] !== GOOD_VALUE[c.key]).map((c) => c.label);
}

function isFlagged(row: CallRow): boolean {
  return row.status === "failed" || row.passed === false || badFlags(row.judge_flags).length > 0;
}

export function PassPill({ passed }: { passed: boolean | null }) {
  if (passed == null) return <span className="muted">—</span>;
  return <span className={passed ? "pill pill-pass" : "pill pill-fail"}>{passed ? "Pass" : "Fail"}</span>;
}

function CallRowView({ runId, row }: { runId: number; row: CallRow }) {
  return (
    <tr onClick={() => navigate(href.call(runId, row.idx))}>
      <td className="mono"><a href={href.call(runId, row.idx)} onClick={(e) => e.stopPropagation()}>#{row.idx}</a></td>
      <td className="persona-name">{personaLabel(row.persona)}</td>
      <td>{row.status === "failed" ? <span className="warn-text">call failed</span> : words(row.outcome ?? "—")}</td>
      <td><PassPill passed={row.passed} /></td>
      <td className="num">{row.lint_total ?? "—"}</td>
      <td className="num">{row.tone == null ? "—" : num(row.tone, 0)}</td>
      <td>
        <div className="chips">
          {row.judge_flags == null && <span className="muted small">not judged</span>}
          {badFlags(row.judge_flags).map((label) => (
            <span key={label} className="chip chip-bad">{label}</span>
          ))}
        </div>
      </td>
    </tr>
  );
}

export default function CallsScreen({ runId }: { runId: number }) {
  const run = useApi((signal) => getRun(runId, signal), `run-${runId}`);
  const calls = useApi((signal) => getCalls(runId, signal), `calls-${runId}`);
  const [persona, setPersona] = useState("all");
  const [flaggedOnly, setFlaggedOnly] = useState(false);

  // The visible rows are computed from data + filters on every render, never stored in state:
  // stored copies could go stale when the data or a filter changes.
  const rows = (calls.data ?? []).filter(
    (r) => (persona === "all" || r.persona === persona) && (!flaggedOnly || isFlagged(r)),
  );
  const personas = [...new Set((calls.data ?? []).map((r) => r.persona))].sort();
  const r = run.data;

  return (
    <section>
      <nav className="crumbs"><a href={href.runs}>Runs</a> / Run #{runId}</nav>
      <div className="page-head">
        <div>
          <h1>
            Calls {r && <span className="version big">{r.prompt_version}</span>}{" "}
            {r && <span className="muted mono h-sub">judge {r.judge_version} · #{r.id}</span>}
          </h1>
          <p className="subtitle">
            {r && promptDescription(r.prompt_version) ? `${promptDescription(r.prompt_version)}. ` : ""}
            Every run plays the same scenario pool, so call #3 here is the same debtor as call #3 in any
            run with the same seed. Open a call to read its transcript.
          </p>
        </div>
        {r && <div className="actions"><StatusPill status={r.status} /></div>}
      </div>

      {calls.loading && !calls.data && <Loading label="Loading calls…" />}
      {calls.error != null && <ErrorPanel error={calls.error} onRetry={calls.reload} />}
      {calls.data && !calls.error && (
        <div className="panel table-wrap">
          <div className="filters">
            <label>
              Persona{" "}
              <select value={persona} onChange={(e) => setPersona(e.target.value)}>
                <option value="all">All personas</option>
                {personas.map((p) => <option key={p} value={p}>{personaLabel(p)}</option>)}
              </select>
            </label>
            <label className="inline">
              <input type="checkbox" checked={flaggedOnly} onChange={(e) => setFlaggedOnly(e.target.checked)} />
              Flagged only
            </label>
            <span className="muted small">{rows.length} of {calls.data.length} calls</span>
          </div>
          <table className="calls">
            <thead>
              <tr>
                <th>Call</th><th>Persona</th><th>Outcome</th><th>Check</th>
                <th className="num">Lint</th><th className="num">Tone</th><th>Judge flags</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => <CallRowView key={row.idx} runId={runId} row={row} />)}
              {rows.length === 0 && (
                <tr><td colSpan={7} className="muted no-metrics">No calls match these filters.</td></tr>
              )}
            </tbody>
          </table>
          <p className="table-note">
            Flagged = outcome check failed, the call failed, or the judge found hallucination, a
            compliance problem, amounts before identity, or pressure.
          </p>
        </div>
      )}
    </section>
  );
}
