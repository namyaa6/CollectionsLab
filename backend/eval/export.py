"""Export final run metrics and example transcripts: python -m backend.eval.export

Writes data/results/<prompt>_<run_key[:8]>.json per run plus index.json, for the README and
dashboard. Metrics are copied from what the runner stored, never recomputed. The database is
opened read-only. A run whose stored calls do not match its stored metrics is marked
"complete": false (for example an interrupted extension).
"""
import argparse
import random
import sys
from pathlib import Path
from typing import Callable, Optional

from backend import db
from backend.eval.validation import open_readonly, save_json, say

RESULTS_DIR = Path(__file__).resolve().parents[2] / "data" / "results"


def select_runs(conn, run_keys: Optional[list[str]] = None) -> list[dict]:
    """Runs with stored metrics: the given run keys (prefixes ok), else the latest per prompt."""
    runs = [db.get_run(conn, r["id"]) for r in conn.execute("SELECT id FROM runs ORDER BY id")]
    runs = [r for r in runs if r["metrics"] is not None]
    if run_keys:
        return [r for r in runs if any(r["run_key"].startswith(k) for k in run_keys)]
    latest: dict[str, dict] = {}
    for r in sorted(runs, key=lambda r: (r["updated_at"], r["id"])):
        latest[r["prompt_version"]] = r
    return [latest[v] for v in sorted(latest)]


def pick_examples(calls: list[dict], k: int, seed: int) -> list[dict]:
    """Up to k ok calls, from distinct personas, chosen with a seeded shuffle."""
    rng = random.Random(seed)
    by_persona: dict[str, list[dict]] = {}
    for c in calls:
        if c["status"] == "ok" and c.get("transcript"):
            by_persona.setdefault(c["scenario"]["persona"], []).append(c)
    personas = sorted(by_persona)
    rng.shuffle(personas)
    chosen = [rng.choice(by_persona[p]) for p in personas[:k]]
    return [{"idx": c["idx"], "persona": c["scenario"]["persona"], "scenario": c["scenario"],
             "transcript": c["transcript"], "summary": c["summary"], "checks": c["checks"],
             "judge": c["judge"]} for c in sorted(chosen, key=lambda c: c["idx"])]


def build_export(conn, run: dict, n_examples: int) -> dict:
    calls = db.get_calls(conn, run["id"])
    overall = run["metrics"]["overall"]
    complete = (len(calls) >= run["n"]
                and overall["n_calls"] + overall["n_failed"] == len(calls))
    return {"run_key": run["run_key"], "prompt_version": run["prompt_version"],
            "prompt_hash": run["prompt_hash"], "judge_version": run["judge_version"],
            "seed": run["seed"], "models": run["models"], "n_requested": run["n"],
            "n_calls_stored": len(calls), "complete": complete, "updated_at": run["updated_at"],
            "metrics": run["metrics"], "examples": pick_examples(calls, n_examples, run["seed"])}


def parse_args(argv: Optional[list[str]]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export run metrics + examples to data/results")
    p.add_argument("--db", type=Path, default=db.DEFAULT_DB)
    p.add_argument("--out", type=Path, default=RESULTS_DIR)
    p.add_argument("--run-key", action="append", help="export these runs (prefix ok) instead of "
                   "the latest per prompt version")
    p.add_argument("--examples", type=int, default=3)
    return p.parse_args(argv)


def main(argv: Optional[list[str]] = None, out: Callable[[str], None] = say) -> int:
    args = parse_args(argv)
    conn = open_readonly(args.db)
    runs = select_runs(conn, args.run_key)
    if not runs:
        out("No runs with stored metrics to export.")
        return 1
    index = []
    for run in runs:
        data = build_export(conn, run, args.examples)
        name = f"{run['prompt_version']}_{run['run_key'][:8]}.json"
        save_json(args.out / name, data)
        index.append({"file": name, "prompt_version": run["prompt_version"],
                      "run_key": run["run_key"], "n_calls_stored": data["n_calls_stored"],
                      "complete": data["complete"]})
        out(f"{name}: {data['n_calls_stored']} calls, {len(data['examples'])} examples"
            + ("" if data["complete"] else "  (INCOMPLETE)"))
    save_json(args.out / "index.json", index)
    return 0


if __name__ == "__main__":
    sys.exit(main())
