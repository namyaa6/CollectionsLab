// Static mode: the GitHub Pages build has no FastAPI behind it. It reads JSON files written by
// backend/static_api.py into public/static-api/, one per GET endpoint, shaped exactly like the
// API responses. The flag is fixed at build time (`npm run build:static`), not switched at runtime.
import type { RunSummary } from "./api";

export const IS_STATIC = import.meta.env.VITE_STATIC === "1";

/** "/api/runs/3/calls" -> "<base>static-api/runs/3/calls.json". */
export function staticUrl(apiPath: string, base: string = import.meta.env.BASE_URL): string {
  return `${base}static-api/${apiPath.replace(/^\/api\//, "")}.json`;
}

/** Port of backend/api_shapes.py compare_warnings(): warning strings only, no metric math. */
export function compareWarnings(runs: Pick<RunSummary, "id" | "judge_version" | "status">[]): string[] {
  const warnings: string[] = [];
  const versions = [...new Set(runs.map((r) => r.judge_version))].sort();
  if (versions.length > 1) {
    warnings.push(`Runs were judged by different judge versions (${versions.join(", ")}); `
      + "judge-based rates are not directly comparable.");
  }
  for (const r of runs) {
    if (r.status !== "complete") warnings.push(`Run ${r.id} is ${r.status.replace(/_/g, " ")}.`);
  }
  return warnings;
}

/** meta.json: the date of the newest run in the snapshot. */
export interface SnapshotMeta {
  snapshot_date: string | null;
}
