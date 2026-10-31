import { getRuns, MAX_COMPARE, type RateName, type RunStatus, type RunSummary } from "../api";
import { num, pct, promptDescription, rateDetail, RATE_LABELS } from "../format";
import { href } from "../route";
import { useApi } from "../useApi";
import { ErrorPanel, Loading } from "./StatusView";

interface Props {
  selected: number[];
  onToggle: (id: number) => void;
  onClear: () => void;
  onCompare: () => void;
}

const COLUMNS: RateName[] = [
  "identity_verified", "judge_task_success", "hallucination", "compliance_violation", "policy_violation",
];

const STATUS_TEXT: Record<RunStatus, string> = {
  complete: "Complete", partial: "Partial", no_metrics: "No metrics",
};

export function StatusPill({ status }: { status: RunStatus }) {
  return <span className={`pill pill-${status}`}>{STATUS_TEXT[status]}</span>;
}

function RunRow({ run, checked, disabled, onToggle }: {
  run: RunSummary; checked: boolean; disabled: boolean; onToggle: () => void;
}) {
  const h = run.headline;
  return (
    <tr className={checked ? "selected" : undefined} onClick={disabled ? undefined : onToggle}>
      <td className="check" onClick={(e) => e.stopPropagation()}>
        <input
          type="checkbox"
          checked={checked}
          disabled={disabled}
          onChange={onToggle}
          aria-label={`Select run ${run.id}`}
        />
      </td>
      <td className="mono muted">#{run.id}</td>
      <td>
        <span className="version">{run.prompt_version}</span>
        {promptDescription(run.prompt_version) && (
          <div className="version-desc">{promptDescription(run.prompt_version)}</div>
        )}
      </td>
      <td className="mono">{run.judge_version}</td>
      <td><StatusPill status={run.status} /></td>
      <td className="num">
        {run.n_ok}
        <span className="muted"> ok</span>
        {run.n_failed > 0 && <span className="warn-text"> · {run.n_failed} failed</span>}
        {run.n > 0 && <span className="muted"> / {run.n}</span>}
      </td>
      {h ? (
        <>
          {COLUMNS.map((name) => (
            <td key={name} className="num" title={rateDetail(h[name])}>{pct(h[name]?.rate)}</td>
          ))}
          <td className="num">{num(h.lint_total_per_call)}</td>
        </>
      ) : (
        <td colSpan={COLUMNS.length + 1} className="muted no-metrics">No metrics yet</td>
      )}
      <td className="row-action" onClick={(e) => e.stopPropagation()}>
        {run.n_calls_stored > 0 && <a className="btn ghost sm" href={href.calls(run.id)}>Calls →</a>}
      </td>
    </tr>
  );
}

export default function RunsScreen({ selected, onToggle, onClear, onCompare }: Props) {
  const { data, loading, error, reload } = useApi(getRuns, "runs");
  const atLimit = selected.length >= MAX_COMPARE;

  return (
    <section>
      <div className="page-head">
        <div>
          <h1>Evaluation runs</h1>
          <p className="subtitle">
            Each run plays one prompt version against simulated debtors, then scores every call with
            code checks and an LLM judge. Select runs to compare them.
          </p>
        </div>
        <div className="actions">
          {selected.length > 0 && <button className="btn ghost" onClick={onClear}>Clear</button>}
          <button className="btn primary" disabled={selected.length === 0} onClick={onCompare}>
            Compare {selected.length > 0 ? `${selected.length} run${selected.length > 1 ? "s" : ""}` : "runs"}
          </button>
        </div>
      </div>

      {loading && !data && <Loading label="Loading runs…" />}
      {error != null && <ErrorPanel error={error} onRetry={reload} />}
      {data && !error && data.length === 0 && (
        <div className="panel status">No runs in the database yet.</div>
      )}
      {data && !error && data.length > 0 && (
        <div className="panel table-wrap">
          <table className="runs">
            <thead>
              <tr>
                <th className="check" />
                <th>Run</th>
                <th>Prompt</th>
                <th>Judge</th>
                <th>Status</th>
                <th className="num">Calls</th>
                {COLUMNS.map((name) => (
                  <th key={name} className="num">{RATE_LABELS[name]}</th>
                ))}
                <th className="num">Lint / call</th>
                <th className="row-action" />
              </tr>
            </thead>
            <tbody>
              {data.map((run) => {
                const checked = selected.includes(run.id);
                return (
                  <RunRow
                    key={run.id}
                    run={run}
                    checked={checked}
                    disabled={!checked && atLimit}
                    onToggle={() => onToggle(run.id)}
                  />
                );
              })}
            </tbody>
          </table>
          <p className="table-note">
            Rates are shares of calls; hover a rate for k/n and its 95% confidence interval.
            {atLimit && ` At most ${MAX_COMPARE} runs can be compared at once.`}
          </p>
        </div>
      )}
    </section>
  );
}
