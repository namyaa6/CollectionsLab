import type { RateName } from "../api";
import { pct, personaLabel, rateDetail, RATE_LABELS } from "../format";
import type { Series } from "./series";

const METRICS: RateName[] = [
  "judge_task_success", "identity_verified", "hallucination", "compliance_violation", "policy_violation",
];

export default function PersonaTable({ series }: { series: Series[] }) {
  // Union of personas across runs, so a persona missing from one run still gets a row.
  const personas = [...new Set(series.flatMap((s) => Object.keys(s.metrics.per_persona)))].sort();

  return (
    <div className="panel chart-card">
      <div className="card-head">
        <h3>By debtor persona</h3>
        <span className="hint">Rate with k/n · hover for 95% CI</span>
      </div>
      <div className="table-wrap">
        <table className="persona">
          <thead>
            <tr>
              <th rowSpan={2}>Persona</th>
              {METRICS.map((m) => (
                <th key={m} colSpan={series.length} className="group">{RATE_LABELS[m]}</th>
              ))}
            </tr>
            <tr>
              {METRICS.flatMap((m) =>
                series.map((s, i) => (
                  <th key={`${m}-${s.key}`} className={i === 0 ? "num group-start" : "num"}>
                    <span className="swatch" style={{ background: s.color }} />
                    {s.run.prompt_version}
                  </th>
                )),
              )}
            </tr>
          </thead>
          <tbody>
            {personas.map((p) => (
              <tr key={p}>
                <td className="persona-name">{personaLabel(p)}</td>
                {METRICS.flatMap((m) =>
                  series.map((s, i) => {
                    const r = s.metrics.per_persona[p]?.rates[m];
                    return (
                      <td key={`${m}-${s.key}`} className={i === 0 ? "num group-start" : "num"}
                        title={`${s.label}: ${rateDetail(r)}`}>
                        <span className="cell-rate">{pct(r?.rate)}</span>
                        <span className="kn">{r && r.rate != null ? `${r.k}/${r.n}` : ""}</span>
                      </td>
                    );
                  }),
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
