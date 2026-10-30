"""SQLite storage for eval runs and calls (data/collectionslab.db, gitignored).

JSON columns are stored as text and decoded on the way out. Each call row is written in
its own transaction, so an interrupted run loses at most the call in progress.
"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "collectionslab.db"
RUN_JSON = ("models", "scenarios", "metrics")
CALL_JSON = ("scenario", "transcript", "summary", "checks", "judge")

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY,
    run_key TEXT UNIQUE NOT NULL,
    prompt_version TEXT NOT NULL,
    prompt_hash TEXT NOT NULL,
    judge_version TEXT NOT NULL,
    judge_prompt_hash TEXT NOT NULL,
    n INTEGER NOT NULL DEFAULT 0,          -- largest n requested so far
    seed INTEGER NOT NULL,
    models TEXT NOT NULL,                  -- {"agent", "sim", "judge"}
    scenarios TEXT NOT NULL,               -- the full scenario pool the run draws from
    pool_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metrics TEXT
);
CREATE TABLE IF NOT EXISTS calls (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    idx INTEGER NOT NULL,                  -- position in the scenario pool
    status TEXT NOT NULL CHECK (status IN ('ok', 'failed')),
    error TEXT,
    scenario TEXT NOT NULL,
    transcript TEXT,
    summary TEXT,
    checks TEXT,
    judge TEXT,
    latency_ms INTEGER,
    tokens INTEGER,
    created_at TEXT NOT NULL,
    UNIQUE (run_id, idx)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _dumps(value) -> Optional[str]:
    return None if value is None else json.dumps(value, ensure_ascii=False)


def _decode(row: sqlite3.Row, json_cols: tuple[str, ...]) -> dict:
    out = dict(row)
    for col in json_cols:
        if out.get(col) is not None:
            out[col] = json.loads(out[col])
    return out


def connect(path: Path = DEFAULT_DB) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def find_or_create_run(conn: sqlite3.Connection, spec: dict) -> tuple[int, bool]:
    """spec has every runs column except id/n/timestamps/metrics. Returns (run_id, created)."""
    row = conn.execute("SELECT id FROM runs WHERE run_key = ?", (spec["run_key"],)).fetchone()
    if row:
        return row["id"], False
    cols = dict(spec, created_at=_now(), updated_at=_now())
    for c in RUN_JSON:
        if c in cols:
            cols[c] = _dumps(cols[c])
    with conn:
        cur = conn.execute(f"INSERT INTO runs ({', '.join(cols)}) VALUES "
                           f"({', '.join('?' * len(cols))})", list(cols.values()))
    return cur.lastrowid, True


def get_run(conn: sqlite3.Connection, run_id: int) -> dict:
    return _decode(conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone(), RUN_JSON)


def call_statuses(conn: sqlite3.Connection, run_id: int) -> dict[int, str]:
    rows = conn.execute("SELECT idx, status FROM calls WHERE run_id = ?", (run_id,))
    return {r["idx"]: r["status"] for r in rows}


def save_call(conn: sqlite3.Connection, run_id: int, idx: int, record: dict) -> None:
    """Insert, or replace the row for (run_id, idx): a retried failed call overwrites itself."""
    values = {c: _dumps(record.get(c)) for c in CALL_JSON}
    values.update(status=record["status"], error=record.get("error"),
                  latency_ms=record.get("latency_ms"), tokens=record.get("tokens"))
    with conn:
        conn.execute(
            f"INSERT INTO calls (run_id, idx, created_at, {', '.join(values)}) "
            f"VALUES (?, ?, ?, {', '.join('?' * len(values))}) "
            f"ON CONFLICT (run_id, idx) DO UPDATE SET created_at = excluded.created_at, "
            + ", ".join(f"{c} = excluded.{c}" for c in values),
            [run_id, idx, _now(), *values.values()])


def get_calls(conn: sqlite3.Connection, run_id: int, max_idx: Optional[int] = None) -> list[dict]:
    """Calls ordered by idx; max_idx keeps only idx < max_idx."""
    sql, args = "SELECT * FROM calls WHERE run_id = ?", [run_id]
    if max_idx is not None:
        sql, args = sql + " AND idx < ?", args + [max_idx]
    return [_decode(r, CALL_JSON) for r in conn.execute(sql + " ORDER BY idx", args)]


def update_run(conn: sqlite3.Connection, run_id: int, n: int, metrics: dict) -> None:
    """n only ever grows: a smaller --n reports without shrinking the run."""
    with conn:
        conn.execute("UPDATE runs SET n = MAX(n, ?), metrics = ?, updated_at = ? WHERE id = ?",
                     (n, _dumps(metrics), _now(), run_id))
