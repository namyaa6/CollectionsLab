import { getCompare, type RunDetail } from "../api";
import { HIGHER_IS_BETTER, LOWER_IS_BETTER, runColor, runLabel, sortRuns } from "../format";
import { useApi } from "../useApi";
import LintChart from "./LintChart";
import PersonaTable from "./PersonaTable";
import RateChart from "./RateChart";
import { StatusPill } from "./RunsScreen";
import type { Series } from "./series";
import { ErrorPanel, Loading } from "./StatusView";
import Warnings from "./Warnings";

function RunCard({ run, color }: { run: RunDetail; color: string }) {
  return (
    <div className="run-card" style={{ borderTopColor: color }}>
      <div className="run-card-head">
        <span className="swatch lg" style={{ background: color }} />
        <span className="version big">{run.prompt_version}</span>
        <span className="muted mono">#{run.id}</span>
        <StatusPill status={run.status} />
      </div>
      <dl>
        <dt>Judge</dt><dd className="mono">{run.judge_version}</dd>
        <dt>Calls</dt>
        <dd>{run.n_ok} ok{run.n_failed > 0 ? ` · ${run.n_failed} failed` : ""}{run.n > 0 ? ` / ${run.n}` : ""}</dd>
        <dt>Agent</dt><dd className="mono small">{run.models.agent}</dd>
        <dt>Judge model</dt><dd className="mono small">{run.models.judge}</dd>
      </dl>
      {!run.metrics && <p className="muted small">No metrics yet: excluded from charts.</p>}
    </div>
  );
}

export default function CompareScreen({ ids, onBack }: { ids: number[]; onBack: () => void }) {
  const key = [...ids].sort((a, b) => a - b).join(",");
  const { data, loading, error, reload } = useApi((signal) => getCompare(ids, signal), key);

  const runs = data ? sortRuns(data.runs) : [];
  const series: Series[] = runs.flatMap((run, i) =>
    run.metrics
      ? [{ key: `r${run.id}`, run, label: runLabel(run), color: runColor(i), metrics: run.metrics }]
      : [],
  );

  return (
    <section>
      <div className="page-head">
        <div>
          <h1>Compare runs</h1>
          <p className="subtitle">
            Overall rates with 95% Wilson confidence intervals. Where the whiskers of two runs
            don't overlap, the difference is unlikely to be noise.
          </p>
        </div>
        <div className="actions">
          <button className="btn ghost" onClick={onBack}>← Back to runs</button>
        </div>
      </div>

      {loading && <Loading label="Loading comparison…" />}
      {error != null && <ErrorPanel error={error} onRetry={reload} />}
      {data && !loading && !error && (
        <>
          <Warnings warnings={data.warnings} />
          <div className="run-cards">
            {runs.map((run, i) => (
              <RunCard key={run.id} run={run} color={runColor(i)} />
            ))}
          </div>
          {series.length === 0 ? (
            <div className="panel status">None of the selected runs has metrics yet.</div>
          ) : (
            <>
              <div className="chart-grid">
                <RateChart title="Higher is better" hint="Share of calls · 95% CI"
                  metrics={HIGHER_IS_BETTER} series={series} />
                <RateChart title="Lower is better" hint="Share of calls · 95% CI · axis fits the data"
                  metrics={LOWER_IS_BETTER} series={series} />
              </div>
              <LintChart series={series} />
              <PersonaTable series={series} />
            </>
          )}
        </>
      )}
    </section>
  );
}
