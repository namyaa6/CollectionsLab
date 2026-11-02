import { getRuns, MAX_COMPARE } from "../api";
import { pickRun } from "../landing";
import { useApi } from "../useApi";
import Hero, { useIntroPreference } from "./Hero";
import HowToRead from "./HowToRead";
import RunsTable from "./RunsTable";
import StartHere from "./StartHere";
import StatsStrip from "./StatsStrip";
import { ErrorPanel, Loading } from "./StatusView";
import VersionStrip from "./VersionStrip";

interface Props {
  selected: number[];
  onToggle: (id: number) => void;
  onClear: () => void;
  onCompare: () => void;
  /** Select exactly these runs and open Compare. */
  onCompareRuns: (ids: number[]) => void;
}

export default function RunsScreen({ selected, onToggle, onClear, onCompare, onCompareRuns }: Props) {
  const { data, loading, error, reload } = useApi(getRuns, "runs");
  const [showIntro, toggleIntro] = useIntroPreference();
  const atLimit = selected.length >= MAX_COMPARE;
  const v1 = data ? pickRun(data, "v1") : null;
  const v4 = data ? pickRun(data, "v4") : null;

  return (
    <section>
      <Hero showIntro={showIntro} onToggle={toggleIntro} />
      {showIntro && data && data.length > 0 && (
        <>
          <StatsStrip runs={data} />
          <StartHere runs={data} onCompare={onCompareRuns} />
          <VersionStrip />
        </>
      )}

      <div className="page-head runs-head">
        <div>
          <h2>Evaluation runs</h2>
          <p className="subtitle">Each row is one prompt version, tested on the same 14 simulated calls.</p>
        </div>
        <div className="actions">
          {selected.length > 0 && <button className="btn ghost" onClick={onClear}>Clear</button>}
          {v1 && v4 && (
            <button className="btn" onClick={() => onCompareRuns([v1.id, v4.id])}>Compare v1 vs v4</button>
          )}
          <div className="compare-action">
            <button className="btn primary" disabled={selected.length === 0} onClick={onCompare}>
              Compare {selected.length > 0 ? `${selected.length} run${selected.length > 1 ? "s" : ""}` : "runs"}
            </button>
            {selected.length === 0 && <span className="hint">Tick two runs to compare</span>}
          </div>
        </div>
      </div>

      {loading && !data && <Loading label="Loading runs…" />}
      {error != null && <ErrorPanel error={error} onRetry={reload} />}
      {data && !error && data.length === 0 && (
        <div className="panel status">No runs in the database yet.</div>
      )}
      {data && !error && data.length > 0 && (
        <div className="panel runs-panel">
          <div className="table-wrap">
            <RunsTable runs={data} selected={selected} onToggle={onToggle} atLimit={atLimit} />
          </div>
          <HowToRead atLimit={atLimit} />
        </div>
      )}
    </section>
  );
}
