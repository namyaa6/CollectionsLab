import type { RunSummary } from "../api";
import { pickRun } from "../landing";
import { href } from "../route";

interface Props {
  runs: RunSummary[];
  onCompare: (ids: number[]) => void;
}

/** Three guided entry points. Runs are found by prompt version, never by a fixed id. */
export default function StartHere({ runs, onCompare }: Props) {
  const v1 = pickRun(runs, "v1"), v2 = pickRun(runs, "v2"), v4 = pickRun(runs, "v4");
  if (!v1 && !v2) return null;
  return (
    <nav className="start-here" aria-label="Start here">
      <h2 className="section-label">Start here</h2>
      <div className="start-cards">
        {v1 && v4 && (
          <button className="start-card" onClick={() => onCompare([v1.id, v4.id])}>
            <span className="start-title">See the big picture →</span>
            <span className="start-desc">v1 vs v4 side by side, with confidence intervals.</span>
          </button>
        )}
        {v1 && (
          <a className="start-card" href={href.call(v1.id, 3)}>
            <span className="start-title">Hear the problem →</span>
            <span className="start-desc">v1, call 3: press Play to hear "₹" and digits read aloud.</span>
          </a>
        )}
        {v2 && (
          <a className="start-card" href={href.call(v2.id, 3)}>
            <span className="start-title">Catch a mistake →</span>
            <span className="start-desc">v2, call 3: states an amount before checking the invoice.</span>
          </a>
        )}
      </div>
    </nav>
  );
}
