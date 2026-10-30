import type { SelfCheck, ToolCall } from "../callTypes";
import { wordDiff } from "../wordDiff";

function shortJson(value: unknown, max = 70): string {
  const s = JSON.stringify(value) ?? "";
  return s.length > max ? s.slice(0, max - 1) + "…" : s;
}

/** <details> is a native HTML disclosure widget: open/closed state without any React state. */
export function ToolCallRow({ call, active }: { call: ToolCall; active: boolean }) {
  // `open` follows the judge selection: the quoted call opens; the user can still toggle any row.
  return (
    <details className={active ? "tool-row active" : "tool-row"} open={active || undefined}>
      <summary>
        <span className="tool-name">{call.tool}</span>
        <span className="tool-args">{shortJson(call.args)}</span>
      </summary>
      <div className="tool-body">
        <div className="tool-label">args</div>
        <pre>{JSON.stringify(call.args, null, 2)}</pre>
        <div className="tool-label">result</div>
        <pre>{JSON.stringify(call.result, null, 2)}</pre>
      </div>
    </details>
  );
}

/** v4 self-check: what the agent drafted, what was spoken, and why it changed. */
export function SelfCheckBlock({ check }: { check: SelfCheck }) {
  if (!check.revised) {
    return (
      <div className="self-check quiet">
        Self-check: {check.error ? <span className="warn-text">check failed ({check.error}), draft spoken as is</span> : "ok, draft spoken as is"}
        {check.issues.length > 0 && <span className="muted"> · noted: {check.issues.join("; ")}</span>}
      </div>
    );
  }
  return (
    <details className="self-check" open>
      <summary>Self-check revised this turn</summary>
      <div className="sc-label">Draft → final</div>
      <p className="sc-diff">
        {wordDiff(check.draft, check.final).map((p, i) => (
          <span key={i}>
            {i > 0 && " "}
            {p.op === "same" ? p.text : p.op === "del" ? <del>{p.text}</del> : <ins>{p.text}</ins>}
          </span>
        ))}
      </p>
      {check.issues.length > 0 && (
        <>
          <div className="sc-label">Issues found</div>
          <ul className="sc-issues">
            {check.issues.map((issue, i) => <li key={i}>{issue}</li>)}
          </ul>
        </>
      )}
    </details>
  );
}
