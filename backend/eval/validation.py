"""Shared helpers for judge validation (hand labels, agreement, cross-judge).

Nothing here writes to the eval database: it is opened read-only, so these tools can run
while an eval run is in progress.
"""
import json
import os
import random
import sqlite3
import tempfile
from pathlib import Path
from typing import Optional

from backend import db
from backend.eval.judge import BOOL_FIELDS

LABELS_DIR = Path(__file__).resolve().parents[2] / "data" / "labels"
LABELS_PATH = LABELS_DIR / "labels.json"
SAMPLE_SIZE = 20


def say(text: str) -> None:
    print(text.encode("ascii", "replace").decode("ascii"))  # Windows consoles can't print the rupee sign


# ---------- storage ----------

def open_readonly(path: Path) -> sqlite3.Connection:
    # check_same_thread=False: FastAPI may open the connection (dependency) and use it (endpoint)
    # in different threadpool threads. Safe: read-only, and one connection per request.
    conn = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True,
                           check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def load_json(path: Path, default=None):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save_json(path: Path, data) -> None:
    """Atomic: write a temp file, then replace, so an interrupted save never corrupts labels."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def call_key(run_key: str, idx: int) -> str:
    return f"{run_key}:{idx}"  # run_key survives a DB rebuild, the integer run id does not


def load_ok_calls(conn: sqlite3.Connection) -> list[dict]:
    """Every ok call that has a judge verdict: {key, prompt_version, persona, idx}."""
    out = []
    for run in conn.execute("SELECT id, run_key, prompt_version FROM runs ORDER BY id"):
        for c in db.get_calls(conn, run["id"]):
            if c["status"] == "ok" and (c.get("judge") or {}).get("verdict"):
                out.append({"key": call_key(run["run_key"], c["idx"]), "idx": c["idx"],
                            "prompt_version": run["prompt_version"],
                            "persona": c["scenario"]["persona"]})
    return out


def fetch_call(conn: sqlite3.Connection, key: str) -> Optional[dict]:
    """The decoded call row for a key, plus 'prompt_version' and 'judge_model'; None if gone."""
    run_key, idx = key.rsplit(":", 1)
    run = conn.execute("SELECT id, prompt_version, models FROM runs WHERE run_key = ?",
                       (run_key,)).fetchone()
    if run is None:
        return None
    for c in db.get_calls(conn, run["id"]):
        if c["idx"] == int(idx):
            c["prompt_version"] = run["prompt_version"]
            c["judge_model"] = json.loads(run["models"]).get("judge")
            return c
    return None


# ---------- sampling ----------

def sample_calls(pool: list[dict], k: int = SAMPLE_SIZE, seed: int = 42) -> list[dict]:
    """Stratified by (prompt_version, persona), round-robin over shuffled groups, then the
    result is shuffled again so the order carries no information about the prompt version."""
    rng = random.Random(seed)
    groups: dict[tuple, list[dict]] = {}
    for c in sorted(pool, key=lambda c: c["key"]):
        groups.setdefault((c["prompt_version"], c["persona"]), []).append(c)
    queues = [groups[g] for g in sorted(groups)]
    for q in queues:
        rng.shuffle(q)
    rng.shuffle(queues)
    picked = []
    while len(picked) < k and any(queues):
        for q in queues:
            if q and len(picked) < k:
                picked.append(q.pop())
    rng.shuffle(picked)
    return picked


# ---------- agreement ----------

def flatten_verdict(verdict: dict) -> dict:
    """A judge verdict in the same flat shape as a hand label: {criterion: bool, tone: int}."""
    flat = {f: verdict[f]["value"] for f in BOOL_FIELDS}
    flat["tone"] = verdict["tone"]["score"]
    return flat


def cohen_kappa(a: list, b: list) -> Optional[float]:
    """None when undefined (no pairs, or chance agreement is already 1)."""
    n = len(a)
    if n == 0:
        return None
    observed = sum(x == y for x, y in zip(a, b)) / n
    chance = sum(a.count(c) / n * b.count(c) / n for c in set(a) | set(b))
    if chance == 1:
        return None
    return round((observed - chance) / (1 - chance), 4)


def _pairs(first: dict, second: dict, field: str) -> list[tuple]:
    return [(k, first[k][field], second[k][field]) for k in sorted(set(first) & set(second))
            if field in first[k] and field in second[k]]


def compare(first: dict, second: dict) -> dict:
    """Per boolean criterion over the keys both raters labelled."""
    out = {}
    for field in BOOL_FIELDS:
        pairs = _pairs(first, second, field)
        n = len(pairs)
        out[field] = {
            "n": n,
            "agree_pct": round(100 * sum(x == y for _, x, y in pairs) / n, 1) if n else None,
            "kappa": cohen_kappa([x for _, x, _ in pairs], [y for _, _, y in pairs]),
            "disagreements": [{"key": k, "first": x, "second": y} for k, x, y in pairs if x != y]}
    return out


def compare_tone(first: dict, second: dict) -> dict:
    """mean_diff is first minus second: judge-minus-human > 0 means the judge is more lenient."""
    pairs = _pairs(first, second, "tone")
    n = len(pairs)
    pct = lambda hits: round(100 * hits / n, 1) if n else None  # noqa: E731
    return {"n": n,
            "exact_pct": pct(sum(x == y for _, x, y in pairs)),
            "within1_pct": pct(sum(abs(x - y) <= 1 for _, x, y in pairs)),
            "mean_diff": round(sum(x - y for _, x, y in pairs) / n, 2) if n else None,
            "disagreements": [{"key": k, "first": x, "second": y} for k, x, y in pairs if x != y]}
