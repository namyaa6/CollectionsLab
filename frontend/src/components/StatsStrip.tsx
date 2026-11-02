import type { ReactNode } from "react";
import type { RunSummary } from "../api";
import { pct } from "../format";
import { headlineStats } from "../landing";

const JUDGE_VALIDATION_URL = "https://github.com/namyaa6/CollectionsLab#judge-validation";

function Stat({ label, value, detail }: { label: string; value: ReactNode; detail: ReactNode }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      <div className="stat-detail">{detail}</div>
    </div>
  );
}

function signedPct(x: number): string {
  return `${x < 0 ? "−" : "+"}${Math.abs(Math.round(x * 100))}%`;
}

/** Four headline numbers. All but the judge agreement come from the loaded runs. */
export default function StatsStrip({ runs }: { runs: RunSummary[] }) {
  const s = headlineStats(runs);
  return (
    <div className="stats" role="list" aria-label="Headline results">
      {s.speech && (
        <div role="listitem">
          <Stat label="Speech problems per call"
            value={<>{s.speech.from.toFixed(2)} <span className="arrow">→</span> {s.speech.to.toFixed(2)}</>}
            detail={s.speech.change == null ? "v1 → v4" : `${signedPct(s.speech.change)} from v1 to v4`} />
        </div>
      )}
      {s.identity && (
        <div role="listitem">
          <Stat label="Confirms who it's talking to before money"
            value={<>{pct(s.identity.from.rate)} <span className="arrow">→</span> {pct(s.identity.to.rate)}</>}
            detail={`${s.identity.from.k}/${s.identity.from.n} → ${s.identity.to.k}/${s.identity.to.n} calls, v1 → v4`} />
        </div>
      )}
      <div role="listitem">
        <Stat label="Calls graded" value={s.callsGraded}
          detail={`${s.versions} prompt versions, code checks + AI judge`} />
      </div>
      <div role="listitem">
        <Stat label="Judge agreement with hand labels" value="85–100%"
          detail={<a href={JUDGE_VALIDATION_URL}>How the AI judge was checked →</a>} />
      </div>
    </div>
  );
}
