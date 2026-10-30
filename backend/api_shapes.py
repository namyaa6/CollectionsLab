"""Pure shaping helpers for the read-only API: stored rows in, JSON-ready dicts out.

Metrics are passed through exactly as the runner stored them; nothing here recomputes a rate.
"""
from backend.eval.judge import BOOL_FIELDS

HEADLINE_RATES = ("outcome_pass", "judge_task_success", "hallucination",
                  "compliance_violation", "escalation_correct", "identity_verified",
                  "pressure_or_threat", "policy_violation")


def headline(metrics: dict | None) -> dict | None:
    if not metrics:
        return None
    overall = metrics["overall"]
    out = {name: overall["rates"].get(name) for name in HEADLINE_RATES}
    out["lint_total_per_call"] = overall["lint_per_call"].get("total")
    out["tone_avg"] = overall.get("tone_avg")
    out["turns_per_call"] = overall.get("turns_per_call")
    return out


def run_status(run: dict, n_stored: int) -> tuple[str, bool]:
    """(status, complete). Same rule as export.build_export: the stored calls must cover the
    requested n and match the calls the stored metrics were computed from."""
    if run["metrics"] is None:  # never finished: partial if calls are stored, else nothing yet
        return ("partial" if n_stored else "no_metrics"), False
    overall = run["metrics"]["overall"]
    complete = n_stored >= run["n"] and overall["n_calls"] + overall["n_failed"] == n_stored
    return ("complete" if complete else "partial"), complete


def run_summary(run: dict, counts: dict[str, int]) -> dict:
    n_stored = sum(counts.values())
    status, complete = run_status(run, n_stored)
    return {"id": run["id"], "run_key": run["run_key"], "prompt_version": run["prompt_version"],
            "judge_version": run["judge_version"], "models": run["models"], "n": run["n"],
            "seed": run["seed"], "n_calls_stored": n_stored, "n_ok": counts.get("ok", 0),
            "n_failed": counts.get("failed", 0), "status": status, "complete": complete,
            "updated_at": run["updated_at"], "headline": headline(run["metrics"])}


def run_detail(run: dict, counts: dict[str, int]) -> dict:
    return {**run_summary(run, counts), "prompt_hash": run["prompt_hash"],
            "judge_prompt_hash": run["judge_prompt_hash"], "created_at": run["created_at"],
            "metrics": run["metrics"]}


def call_row(call: dict) -> dict:
    """One line of the calls table: no transcript, so the list stays small."""
    checks, judge = call.get("checks"), call.get("judge") or {}
    verdict = judge.get("verdict")
    return {
        "idx": call["idx"], "persona": call["scenario"]["persona"], "status": call["status"],
        "error": call["error"],
        "outcome": checks["outcome"]["outcome"] if checks else None,
        "passed": checks["outcome"]["passed"] if checks else None,
        "lint_total": sum(checks["voice_counts"].values()) if checks else None,
        "judge_flags": {f: verdict[f]["value"] for f in BOOL_FIELDS} if verdict else None,
        "tone": verdict["tone"]["score"] if verdict else None,
        "judge_version": judge.get("judge_version"),
    }


def compare_warnings(summaries: list[dict]) -> list[str]:
    warnings = []
    versions = sorted({s["judge_version"] for s in summaries})
    if len(versions) > 1:
        warnings.append("Runs were judged by different judge versions ("
                        + ", ".join(versions) + "); judge-based rates are not directly comparable.")
    for s in summaries:
        if s["status"] != "complete":
            warnings.append(f"Run {s['id']} is {s['status'].replace('_', ' ')}.")
    return warnings
