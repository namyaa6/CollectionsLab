import type { Metrics, RunDetail } from "../api";

/** One compared run as the charts see it: a stable key, a label, its colour and its metrics. */
export interface Series {
  key: string;
  run: RunDetail;
  label: string;
  color: string;
  metrics: Metrics;
}
