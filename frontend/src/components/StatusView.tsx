import { ApiError } from "../api";

export function Loading({ label }: { label: string }) {
  return (
    <div className="panel status" role="status">
      <span className="spinner" aria-hidden="true" />
      {label}
    </div>
  );
}

function Commands({ lines }: { lines: string[] }) {
  return (
    <pre className="commands">
      {lines.map((l) => (
        <code key={l}>{l}</code>
      ))}
    </pre>
  );
}

/** Explains what went wrong and, where we know the fix, the exact commands to run. */
export function ErrorPanel({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const kind = error instanceof ApiError ? error.kind : "http";
  const message = error instanceof Error ? error.message : String(error);

  return (
    <div className="panel error-panel" role="alert">
      {kind === "unreachable" && (
        <>
          <h2>Can't reach the API</h2>
          <p>The dashboard reads from the FastAPI server on port 8000. Start it from the project root:</p>
          <Commands lines={[".venv\\Scripts\\activate", "uvicorn backend.main:app --reload"]} />
        </>
      )}
      {kind === "no_database" && (
        <>
          <h2>No database yet</h2>
          <p>The API is running but found no runs database. Create one with an evaluation run:</p>
          <Commands lines={["python -m backend.eval.runner --prompt v1 --n 5 --seed 42"]} />
        </>
      )}
      {kind === "http" && (
        <>
          <h2>Something went wrong</h2>
          <p>{message}</p>
        </>
      )}
      <button className="btn" onClick={onRetry}>Retry</button>
    </div>
  );
}
