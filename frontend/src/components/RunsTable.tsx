import type { RateName, RunStatus, RunSummary } from "../api";
import { num, pct, promptDescription, rateDetail, RATE_LABELS } from "../format";
import { COLUMN_HELP, columnExtremes, judgeLabel, showJudgeColumn, type ColumnKey } from "../landing";
import { href } from "../route";

const RATE_COLUMNS: RateName[] = [
  "identity_verified", "judge_task_success", "hallucination", "compliance_violation", "policy_violation",
];
const TINTED: ColumnKey[] = [...RATE_COLUMNS, "lint_total_per_call"];

const STATUS_TEXT: Record<RunStatus, string> = {
  complete: "Complete", partial: "Partial", no_metrics: "No metrics",
};

export function StatusPill({ status }: { status: RunStatus }) {
  return <span className={`pill pill-${status}`}>{STATUS_TEXT[status]}</span>;
}

type Extremes = Record<string, { best: Set<number>; worst: Set<number> }>;

/** A rate or lint cell. Best/worst get a tint AND an arrow, tooltip and screen-reader text. */
function Cell({ run, col, text, detail, extremes }: {
  run: RunSummary; col: ColumnKey; text: string; detail: string; extremes: Extremes;
}) {
  const mark = extremes[col].best.has(run.id) ? "best" : extremes[col].worst.has(run.id) ? "worst" : null;
  return (
    <td className={mark ? `num tint-${mark}` : "num"}
      title={mark ? `${detail} · ${mark} in this column` : detail}>
      {text}
      {mark && <span className="tint-mark" aria-hidden="true">{mark === "best" ? " ▲" : " ▼"}</span>}
      {mark && <span className="sr-only"> ({mark} in this column)</span>}
    </td>
  );
}

function RunRow({ run, checked, disabled, onToggle, withJudge, extremes }: {
  run: RunSummary; checked: boolean; disabled: boolean; onToggle: () => void;
  withJudge: boolean; extremes: Extremes;
}) {
  const h = run.headline;
  return (
    <tr className={checked ? "selected" : undefined} onClick={disabled ? undefined : onToggle}>
      <td className="check" onClick={(e) => e.stopPropagation()}>
        <input type="checkbox" checked={checked} disabled={disabled} onChange={onToggle}
          aria-label={`Select run ${run.id}`} />
      </td>
      <td className="mono muted">#{run.id}</td>
      <td>
        <span className="version">{run.prompt_version}</span>
        {promptDescription(run.prompt_version) && (
          <div className="version-desc">{promptDescription(run.prompt_version)}</div>
        )}
      </td>
      {withJudge && <td className="small">{judgeLabel(run.judge_version)}</td>}
      <td><StatusPill status={run.status} /></td>
      <td className="num">
        {run.n_ok}
        <span className="muted"> ok</span>
        {run.n_failed > 0 && <span className="warn-text"> · {run.n_failed} failed</span>}
        {run.n > 0 && <span className="muted"> / {run.n}</span>}
      </td>
      {h ? (
        <>
          {RATE_COLUMNS.map((c) => (
            <Cell key={c} run={run} col={c} text={pct(h[c]?.rate)} detail={rateDetail(h[c])}
              extremes={extremes} />
          ))}
          <Cell run={run} col="lint_total_per_call" text={num(h.lint_total_per_call)}
            detail="mean per call" extremes={extremes} />
        </>
      ) : (
        <td colSpan={RATE_COLUMNS.length + 1} className="muted no-metrics">No metrics yet</td>
      )}
      <td className="row-action" onClick={(e) => e.stopPropagation()}>
        {run.n_calls_stored > 0 && <a className="btn ghost sm" href={href.calls(run.id)}>Calls →</a>}
      </td>
    </tr>
  );
}

function Th({ label, help, num: isNum }: { label: string; help: string; num?: boolean }) {
  return <th className={isNum ? "num" : undefined} title={help} scope="col">{label}</th>;
}

export default function RunsTable({ runs, selected, onToggle, atLimit }: {
  runs: RunSummary[]; selected: number[]; onToggle: (id: number) => void; atLimit: boolean;
}) {
  const withJudge = showJudgeColumn(runs);
  const extremes: Extremes = Object.fromEntries(TINTED.map((c) => [c, columnExtremes(runs, c)]));
  return (
    <table className="runs">
      <thead>
        <tr>
          <th className="check" />
          <Th label="Run" help={COLUMN_HELP.run} />
          <Th label="Prompt version" help={COLUMN_HELP.version} />
          {withJudge && <Th label="Judge" help={COLUMN_HELP.judge} />}
          <Th label="Status" help={COLUMN_HELP.status} />
          <Th label="Calls" help={COLUMN_HELP.calls} num />
          {RATE_COLUMNS.map((c) => <Th key={c} label={RATE_LABELS[c]} help={COLUMN_HELP[c]} num />)}
          <Th label="Speech issues / call" help={COLUMN_HELP.lint_total_per_call} num />
          <th className="row-action" />
        </tr>
      </thead>
      <tbody>
        {runs.map((run) => {
          const checked = selected.includes(run.id);
          return (
            <RunRow key={run.id} run={run} checked={checked} disabled={!checked && atLimit}
              onToggle={() => onToggle(run.id)} withJudge={withJudge} extremes={extremes} />
          );
        })}
      </tbody>
    </table>
  );
}
