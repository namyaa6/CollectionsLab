import {
  Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { LINT_CATEGORIES } from "../api";
import { LINT_LABELS, num } from "../format";
import { legendText } from "./RateChart";
import type { Series } from "./series";

type Row = { category: string } & Record<string, number | null | string>;

export default function LintChart({ series }: { series: Series[] }) {
  const rows: Row[] = LINT_CATEGORIES.map((c) => {
    const row: Row = { category: LINT_LABELS[c] };
    for (const s of series) row[s.key] = s.metrics.overall.lint_per_call[c];
    return row;
  });

  return (
    <div className="panel chart-card">
      <div className="card-head">
        <h3>Voice lint violations per call</h3>
        <span className="hint">Lower is better · mean per call, by category (no CI computed)</span>
      </div>
      <div className="lint-totals">
        {series.map((s) => (
          <div key={s.key} className="lint-total">
            <span className="swatch" style={{ background: s.color }} />
            <span className="muted">{s.run.prompt_version} #{s.run.id} total</span>
            <strong>{num(s.metrics.overall.lint_per_call.total)}</strong>
          </div>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}
          barGap={2} barCategoryGap="24%">
          <CartesianGrid vertical={false} stroke="var(--grid)" />
          <XAxis dataKey="category" tickLine={false} axisLine={{ stroke: "var(--axis)" }}
            tick={{ fill: "var(--ink-2)", fontSize: 12 }} interval={0} />
          <YAxis domain={[0, (max: number) => Math.max(1, Math.ceil(max))]} allowDecimals={false}
            tickLine={false} axisLine={false}
            tick={{ fill: "var(--ink-3)", fontSize: 12 }} />
          <Tooltip cursor={{ fill: "var(--hover)" }}
            formatter={(v) => (typeof v === "number" ? num(v) : "—")}
            contentStyle={{ borderRadius: 8, border: "1px solid var(--border)", fontSize: 12 }} />
          <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
            formatter={legendText} />
          {series.map((s) => (
            <Bar key={s.key} dataKey={s.key} name={s.label} fill={s.color}
              radius={[4, 4, 0, 0]} maxBarSize={36} isAnimationActive={false} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
