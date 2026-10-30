import { getRuns } from "../api";
import type { CallDetail } from "../callTypes";
import { END_REASON_LABELS, personaLabel, words } from "../format";
import { href } from "../route";
import { switcherRuns } from "../switcher";
import { useApi } from "../useApi";
import { PassPill } from "./CallsScreen";

interface SwitcherProps {
  runId: number;
  idx: number;
  showAllJudges: boolean;
  onToggleAllJudges: (v: boolean) => void;
}

/** Same idx in another run = same debtor and invoice, played by a different prompt. */
function ScenarioSwitcher({ runId, idx, showAllJudges, onToggleAllJudges }: SwitcherProps) {
  const runs = useApi(getRuns, "runs");
  if (!runs.data) return null;
  const choice = switcherRuns(runs.data, runId, showAllJudges);
  const current = runs.data.find((r) => r.id === runId);
  const lastIdx = current ? current.n_calls_stored - 1 : idx;

  return (
    <div className="switcher">
      <span className="switcher-label">Same scenario in</span>
      <div className="segmented" role="group" aria-label="Same scenario in another run">
        {choice.runs.map((r) => (
          <a
            key={r.id}
            href={href.call(r.id, idx)}
            className={r.id === runId ? "seg active" : "seg"}
            aria-current={r.id === runId ? "page" : undefined}
            title={`Run #${r.id}`}
          >
            {r.prompt_version}{choice.labelJudge && <span className="seg-judge"> · {r.judge_version}</span>}
          </a>
        ))}
      </div>
      {choice.hasOtherJudges && (
        <label className="inline small muted">
          <input type="checkbox" checked={showAllJudges} onChange={(e) => onToggleAllJudges(e.target.checked)} />
          show all judges
        </label>
      )}
      <span className="switcher-nav">
        <a className={idx > 0 ? "btn ghost sm" : "btn ghost sm disabled"} href={idx > 0 ? href.call(runId, idx - 1) : undefined}>
          ← Prev
        </a>
        <a className={idx < lastIdx ? "btn ghost sm" : "btn ghost sm disabled"}
          href={idx < lastIdx ? href.call(runId, idx + 1) : undefined}>
          Next →
        </a>
      </span>
    </div>
  );
}

export default function CallHeader({ call, ...switcher }: { call: CallDetail } & SwitcherProps) {
  const t = call.transcript;
  const expected = call.scenario.expected_outcomes.map(words).join(" or ");
  const actual = call.checks?.outcome.outcome ?? call.summary?.outcome;
  return (
    <div className="panel call-header">
      <div className="call-title">
        <h1>
          Call #{call.idx} <span className="persona-tag">{personaLabel(call.scenario.persona)}</span>
        </h1>
        <span className="version">{call.prompt_version}</span>
        <span className="muted mono small">judge {call.judge_version} · run #{call.run_id}</span>
        <span className="call-pass"><PassPill passed={call.checks?.outcome.passed ?? null} /></span>
      </div>
      <dl className="call-facts">
        <div><dt>Expected</dt><dd>{expected || "—"}</dd></div>
        <div><dt>Actual</dt><dd>{actual ? words(actual) : "—"}</dd></div>
        <div>
          <dt>Ended</dt>
          <dd title={t?.end_detail ?? undefined}>{t ? END_REASON_LABELS[t.end_reason] ?? words(t.end_reason) : "—"}</dd>
        </div>
        {/* Stored latency_ms and tokens cover the agent's turns only (backend/eval/pipeline.py). */}
        <div><dt>Agent latency</dt><dd>{call.latency_ms == null ? "—" : `${(call.latency_ms / 1000).toFixed(1)}s`}</dd></div>
        <div><dt>Agent tokens</dt><dd>{call.tokens?.toLocaleString() ?? "—"}</dd></div>
        {t && (
          <div>
            <dt>Simulator tokens</dt>
            <dd>{(t.totals.debtor_input_tokens + t.totals.debtor_output_tokens).toLocaleString()}</dd>
          </div>
        )}
      </dl>
      {t?.end_detail && <p className="end-detail muted small">“{t.end_detail}”</p>}
      {call.status === "failed" && <div className="turn-error">This call failed: {call.error ?? "no error message"}</div>}
      <ScenarioSwitcher {...switcher} />
    </div>
  );
}
