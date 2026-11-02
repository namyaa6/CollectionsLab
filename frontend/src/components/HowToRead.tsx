import { MAX_COMPARE } from "../api";

/** Collapsible guide under the runs table (native <details>: no React state needed). */
export default function HowToRead({ atLimit }: { atLimit: boolean }) {
  return (
    <details className="how-to-read">
      <summary>How to read this table</summary>
      <ul>
        <li>Each rate is the share of the run's calls with that result. Hover a number for the
          exact count (k/n) and its 95% confidence interval; with 14 calls, small differences are
          often just noise.</li>
        <li>Higher is better for identity verified and task success; lower is better for
          hallucination, compliance violation, policy violation and speech issues. Hover any
          column header for what it measures.</li>
        <li>In each column, the best value is tinted green with ▲ and the worst red with ▼.
          Ties share the mark, but a value shared by more than half the runs isn't marked.</li>
        <li>"AI judge" columns are scored by a language model; "code" columns by exact rules.
          Click a row to select it, then Compare; "Calls →" opens the transcripts.</li>
      </ul>
      {atLimit && <p className="muted small">At most {MAX_COMPARE} runs can be compared at once.</p>}
    </details>
  );
}
