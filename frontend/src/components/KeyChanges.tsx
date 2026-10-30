import { RATE_NAMES, type Rate, type RateName } from "../api";
import { HIGHER_IS_BETTER, num, pct, RATE_LABELS } from "../format";
import type { Series } from "./series";
import "./KeyChanges.css";

const MAX_TILES = 4;

type Verdict = "clear" | "noise" | "no_ci";

interface Change {
  label: string;
  from: string;
  to: string;
  delta: string;
  detail: string;
  improved: boolean;
  verdict: Verdict;
  score: number; // ranking only: rate points for rates, relative change for lint
}

/** The two 95% intervals do not overlap: the only case we call a change "clear". */
function ciSeparated(a: Rate, b: Rate): boolean {
  if (a.ci_low == null || a.ci_high == null || b.ci_low == null || b.ci_high == null) return false;
  return b.ci_low > a.ci_high || b.ci_high < a.ci_low;
}

function rateChange(name: RateName, a: Rate | undefined, b: Rate | undefined): Change | null {
  if (!a || !b || a.rate == null || b.rate == null || a.rate === b.rate) return null;
  const diff = b.rate - a.rate;
  const points = Math.round(diff * 100);
  return {
    label: RATE_LABELS[name],
    from: pct(a.rate),
    to: pct(b.rate),
    delta: `${points > 0 ? "+" : ""}${points} pts`,
    detail: `${a.k}/${a.n} → ${b.k}/${b.n}`,
    improved: HIGHER_IS_BETTER.includes(name) ? diff > 0 : diff < 0,
    verdict: ciSeparated(a, b) ? "clear" : "noise",
    score: Math.abs(diff),
  };
}

function lintChange(first: Series, last: Series): Change | null {
  const a = first.metrics.overall.lint_per_call.total;
  const b = last.metrics.overall.lint_per_call.total;
  if (a == null || b == null || a === b) return null;
  const rel = a > 0 ? (b - a) / a : null;
  return {
    label: "Lint violations / call",
    from: num(a),
    to: num(b),
    delta: rel == null ? "" : `${rel > 0 ? "+" : ""}${Math.round(rel * 100)}%`,
    detail: `mean over ${first.metrics.overall.n_calls} → ${last.metrics.overall.n_calls} calls`,
    improved: b < a,
    verdict: "no_ci",
    score: rel == null ? 1 : Math.min(1, Math.abs(rel)),
  };
}

function keyChanges(first: Series, last: Series): Change[] {
  const fr = first.metrics.overall.rates;
  const lr = last.metrics.overall.rates;
  const all = [
    ...RATE_NAMES.map((m) => rateChange(m, fr[m], lr[m])),
    lintChange(first, last),
  ].filter((c): c is Change => c != null);
  return all.sort((x, y) => y.score - x.score).slice(0, MAX_TILES);
}

const VERDICT_TEXT: Record<Verdict, string> = {
  clear: "Clear change · CIs don't overlap",
  noise: "Within noise · CIs overlap",
  no_ci: "No CI computed",
};

function Tile({ c }: { c: Change }) {
  return (
    <div className={`kc-tile ${c.verdict === "clear" ? "kc-clear" : ""}`}>
      <div className="kc-label">{c.label}</div>
      <div className="kc-values">
        <span className="kc-from">{c.from}</span>
        <span className="kc-arrow" aria-hidden="true">→</span>
        <span className="kc-to">{c.to}</span>
        {c.delta && <span className="kc-delta">({c.delta})</span>}
      </div>
      <div className="kc-detail">{c.detail}</div>
      <div className="kc-tags">
        <span className={c.improved ? "kc-dir good" : "kc-dir bad"}>
          {c.improved ? "▲ Better" : "▼ Worse"}
        </span>
        <span className={`kc-verdict ${c.verdict}`}>{VERDICT_TEXT[c.verdict]}</span>
      </div>
    </div>
  );
}

/** Headline differences between the first and last compared runs (in sorted order). */
export default function KeyChanges({ series }: { series: Series[] }) {
  if (series.length < 2) return null;
  const first = series[0];
  const last = series[series.length - 1];
  const changes = keyChanges(first, last);

  return (
    <div className="panel key-changes">
      <div className="card-head">
        <h3>
          Key changes <span className="kc-runs">
            <span className="swatch" style={{ background: first.color }} />{first.run.prompt_version}
            <span className="muted"> → </span>
            <span className="swatch" style={{ background: last.color }} />{last.run.prompt_version}
          </span>
        </h3>
        <span className="hint">Largest moves between the first and last run · "clear" only when 95% CIs don't overlap</span>
      </div>
      {changes.length === 0 ? (
        <p className="muted">No metric changed between these runs.</p>
      ) : (
        <div className="kc-grid">
          {changes.map((c) => <Tile key={c.label} c={c} />)}
        </div>
      )}
    </div>
  );
}
