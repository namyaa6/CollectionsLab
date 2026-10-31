"""Static copy of the read-only API for the GitHub Pages dashboard: python -m backend.static_api

Reads what backend/eval/export.py wrote to data/results/ (no database, no LLM) and writes one
JSON file per GET endpoint, shaped by the same api_shapes helpers backend/main.py uses:

  runs.json                  GET /api/runs
  runs/{id}.json             GET /api/runs/{id}
  runs/{id}/calls.json       GET /api/runs/{id}/calls
  calls/{run_id}/{idx}.json  GET /api/calls/{run_id}/{idx}
  meta.json                  snapshot date for the dashboard banner

/api/compare is not written: its warnings depend on which runs are picked, so the frontend
loads runs/{id}.json for each and adds the same warnings itself (frontend/src/staticApi.ts).
"""
import argparse
import json
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Callable, Optional

from backend.api_shapes import call_row, run_detail, run_summary
from backend.eval.export import RESULTS_DIR
from backend.eval.validation import load_json, say

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "frontend" / "public" / "static-api"
MARKER = "meta.json"  # only a folder this script wrote is ever deleted


def run_from_export(data: dict) -> dict:
    """The stored-run fields api_shapes reads, rebuilt from an export file."""
    keys = ("id", "run_key", "prompt_version", "prompt_hash", "judge_version",
            "judge_prompt_hash", "seed", "models", "created_at", "updated_at", "metrics")
    return {**{k: data[k] for k in keys}, "n": data["n_requested"]}


def load_results(results: Path) -> list[tuple[dict, list[dict]]]:
    """(run, calls) for every run listed in index.json."""
    out = []
    for entry in load_json(results / "index.json", []):
        data = load_json(results / entry["file"])
        out.append((run_from_export(data), load_json(results / entry["calls_file"])))
    return out


def build(results: list[tuple[dict, list[dict]]]) -> dict[str, object]:
    """Relative file path -> JSON body, for every static endpoint."""
    files: dict[str, object] = {}
    summaries = []
    for run, calls in results:
        counts = dict(Counter(c["status"] for c in calls))
        summaries.append(run_summary(run, counts))
        files[f"runs/{run['id']}.json"] = run_detail(run, counts)
        files[f"runs/{run['id']}/calls.json"] = [call_row(c) for c in calls]
        for c in calls:
            files[f"calls/{run['id']}/{c['idx']}.json"] = {
                **c, "prompt_version": run["prompt_version"],
                "judge_version": run["judge_version"], "models": run["models"]}
    # same order as main.py: ORDER BY updated_at DESC, id DESC
    files["runs.json"] = sorted(summaries, key=lambda s: (s["updated_at"], s["id"]), reverse=True)
    dates = [run["updated_at"] for run, _ in results]
    files[MARKER] = {"snapshot_date": max(dates) if dates else None}
    return files


def write(files: dict[str, object], out: Path) -> int:
    """Replace out with the files; returns total bytes written."""
    if (out / MARKER).exists():
        shutil.rmtree(out)
    total = 0
    for rel, body in files.items():
        path = out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        path.write_text(text, encoding="utf-8")
        total += len(text.encode("utf-8"))
    return total


def main(argv: Optional[list[str]] = None, out: Callable[[str], None] = say) -> int:
    p = argparse.ArgumentParser(description="Write the static API files for the Pages dashboard")
    p.add_argument("--results", type=Path, default=RESULTS_DIR)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args(argv)
    results = load_results(args.results)
    if not results:
        out(f"No exported runs in {args.results}; run python -m backend.eval.export first.")
        return 1
    files = build(results)
    total = write(files, args.out)
    n_calls = sum(len(calls) for _, calls in results)
    out(f"Wrote {len(files)} files ({len(results)} runs, {n_calls} calls, "
        f"{total / 1e6:.2f} MB) to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
