"""Judge vs hand labels (and vs a second judge): python -m backend.eval.agreement

Per boolean criterion: % agreement and Cohen's kappa. Tone: exact, within-1 and mean
difference (first named minus second, so "judge vs hand" > 0 means the judge is more lenient).
Only numbers computed from the stored labels and verdicts are printed.
"""
import argparse
import sys
from pathlib import Path
from typing import Callable, Optional

from backend.eval.validation import (LABELS_PATH, compare, compare_tone, fetch_call,
                                     flatten_verdict, load_json, open_readonly, say)


def judge_labels(results: dict) -> dict:
    """{key: flat labels} from {key: judge_call result}, skipping calls with no verdict."""
    return {k: flatten_verdict(r["verdict"]) for k, r in results.items() if r.get("verdict")}


def analyze(hand: dict, judge: dict, cross: Optional[dict] = None) -> dict:
    pairs = {"main judge vs hand": (judge, hand)}
    if cross is not None:
        pairs["second judge vs hand"] = (cross, hand)
        pairs["second judge vs main judge"] = (cross, judge)
    return {name: {"criteria": compare(a, b), "tone": compare_tone(a, b)}
            for name, (a, b) in pairs.items()}


def _fmt(value, suffix="") -> str:
    return "undefined" if value is None else f"{value}{suffix}"


def format_report(report: dict, info: dict) -> list[str]:
    """info[key] = {prompt_version, persona, evidence: {criterion: quote}} for disagreements."""
    lines = []
    for name, res in report.items():
        lines += [f"\n== {name} ==", "criterion                          n   agree   kappa"]
        for crit, r in res["criteria"].items():
            lines.append(f"{crit:32} {r['n']:3}  {_fmt(r['agree_pct'], '%'):>6}  "
                         f"{_fmt(r['kappa']):>9}")
        t = res["tone"]
        lines.append(f"tone (n={t['n']}): exact {_fmt(t['exact_pct'], '%')}, within-1 "
                     f"{_fmt(t['within1_pct'], '%')}, mean diff {_fmt(t['mean_diff'])} "
                     f"({name.split(' vs ')[0]} minus {name.split(' vs ')[1]})")
        lines.append("disagreements:")
        rows = [(c, d) for c, r in res["criteria"].items() for d in r["disagreements"]]
        rows += [("tone", d) for d in t["disagreements"]]
        for crit, d in rows:
            meta = info.get(d["key"], {})
            quote = meta.get("evidence", {}).get(crit, "")
            lines.append(f"  {crit} [{meta.get('prompt_version', '?')}/{meta.get('persona', '?')}] "
                         f"{d['first']} vs {d['second']}" + (f' | judge: "{quote}"' if quote else ""))
        if not rows:
            lines.append("  none")
    return lines


def parse_args(argv: Optional[list[str]]) -> argparse.Namespace:
    from backend.db import DEFAULT_DB
    p = argparse.ArgumentParser(description="Agreement between hand labels and the judge(s)")
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--labels", type=Path, default=LABELS_PATH)
    p.add_argument("--cross", type=Path, help="data/labels/cross_judge_<model>.json")
    return p.parse_args(argv)


def main(argv: Optional[list[str]] = None, out: Callable[[str], None] = say) -> int:
    args = parse_args(argv)
    data = load_json(args.labels)
    if not data or not data["labels"]:
        out("No hand labels yet. Run: python -m backend.eval.label")
        return 1
    hand = data["labels"]
    conn = open_readonly(args.db)
    results, info = {}, {}
    for key in hand:
        call = fetch_call(conn, key)
        if call is None or not (call.get("judge") or {}).get("verdict"):
            continue
        results[key] = call["judge"]
        v = call["judge"]["verdict"]
        info[key] = {"prompt_version": call["prompt_version"], "persona": call["scenario"]["persona"],
                     "evidence": {**{f: v[f]["evidence"] for f in v if f != "tone"},
                                  "tone": v["tone"]["evidence"]}}
    cross = None
    if args.cross:
        stored = load_json(args.cross)
        if stored is None:
            out(f"Cross-judge file not found: {args.cross}")
            return 1
        cross = judge_labels(stored["results"])
        out(f"Second judge: {stored['judge_model']} ({len(cross)} verdicts)")
    out(f"Hand labels: {len(hand)}; judged calls found in the DB: {len(results)}")
    for line in format_report(analyze(hand, judge_labels(results), cross), info):
        out(line)
    out("\nKappa is noisy at this n; read it next to the sample size and the disagreements.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
