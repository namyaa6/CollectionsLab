import {
  Bar, BarChart, CartesianGrid, ErrorBar, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { Rate, RateName } from "../api";
import { pct, rateDetail, RATE_LABELS } from "../format";
import type { Series } from "./series";

interface Props {
  title: string;
  hint: string;
  metrics: RateName[];
  series: Series[];
}

/** One row per metric; per run: the bar value, the [below, above] CI distances, the raw Rate. */
type Row = { metric: string } & Record<string, number | null | [number, number] | Rate | string>;

function buildRows(metrics: RateName[], series: Series[]): Row[] {
  return metrics.map((m) => {
    const row: Row = { metric: RATE_LABELS[m] };
    for (const s of series) {
      const r = s.metrics.overall.rates[m];
      row[s.key] = r?.rate ?? null; // null draws no bar: n = 0 is "not applicable", not 0%
      row[`${s.key}_err`] =
        r && r.rate != null && r.ci_low != null && r.ci_high != null
          ? [r.rate - r.ci_low, r.ci_high - r.rate]
          : [0, 0];
      row[`${s.key}_raw`] = r ?? null;
    }
    return row;
  });
}

function RateTooltip({ row, series }: { row: Row | undefined; series: Series[] }) {
  if (!row) return null;
  return (
    <div className="chart-tooltip">
      <div className="tt-title">{row.metric}</div>
      {series.map((s) => {
        const r = row[`${s.key}_raw`] as Rate | null;
        return (
          <div key={s.key} className="tt-row">
            <span className="swatch" style={{ background: s.color }} />
            <span className="tt-label">{s.run.prompt_version} #{s.run.id}</span>
            <strong>{pct(r?.rate)}</strong>
            <span className="muted">{rateDetail(r)}</span>
          </div>
        );
      })}
    </div>
  );
}

/** Top of the y-axis: the highest CI upper bound, rounded up to the next 25%, so small rates stay visible. */
function axisMax(metrics: RateName[], series: Series[]): number {
  const highs = series.flatMap((s) => metrics.map((m) => s.metrics.overall.rates[m]?.ci_high ?? 0));
  return Math.min(1, Math.max(0.25, Math.ceil(Math.max(0, ...highs) * 4) / 4));
}

export const legendText = (value: string) => <span style={{ color: "var(--ink-2)" }}>{value}</span>;

export default function RateChart({ title, hint, metrics, series }: Props) {
  const rows = buildRows(metrics, series);
  const top = axisMax(metrics, series);
  const ticks = [0, 0.25, 0.5, 0.75, 1].filter((t) => t <= top);
  return (
    <div className="panel chart-card">
      <div className="card-head">
        <h3>{title}</h3>
        <span className="hint">{hint}</span>
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}
          barGap={2} barCategoryGap="24%">
          <CartesianGrid vertical={false} stroke="var(--grid)" />
          <XAxis dataKey="metric" tickLine={false} axisLine={{ stroke: "var(--axis)" }}
            tick={{ fill: "var(--ink-2)", fontSize: 12 }} interval={0} />
          <YAxis domain={[0, top]} ticks={ticks} tickFormatter={(v) => pct(v)}
            tickLine={false} axisLine={false} tick={{ fill: "var(--ink-3)", fontSize: 12 }} />
          <Tooltip cursor={{ fill: "var(--hover)" }}
            content={({ active, label }) =>
              active ? <RateTooltip row={rows.find((r) => r.metric === label)} series={series} /> : null
            } />
          <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
            formatter={legendText} />
          {series.map((s) => (
            <Bar key={s.key} dataKey={s.key} name={s.label} fill={s.color}
              radius={[4, 4, 0, 0]} maxBarSize={44} isAnimationActive={false}
              minPointSize={(v) => (v === 0 ? 2 : 0)}>
              <ErrorBar dataKey={`${s.key}_err`} width={6} strokeWidth={1.5} stroke="var(--ink-1)"
                isAnimationActive={false} />
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
      <table className="mini">
        <thead>
          <tr>
            <th />
            {series.map((s) => (
              <th key={s.key} className="num">
                <span className="swatch" style={{ background: s.color }} />
                {s.run.prompt_version} #{s.run.id}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {metrics.map((m) => (
            <tr key={m}>
              <td>{RATE_LABELS[m]}</td>
              {series.map((s) => {
                const r = s.metrics.overall.rates[m];
                return (
                  <td key={s.key} className="num" title={rateDetail(r)}>
                    <strong>{pct(r?.rate)}</strong>
                    <span className="kn">{r && r.rate != null ? `${r.k}/${r.n}` : ""}</span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
