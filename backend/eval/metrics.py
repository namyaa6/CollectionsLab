"""Run metrics, overall and per persona, from stored call records.

A call record is a dict as stored in the calls table: status, scenario, transcript,
checks, judge (JSON already decoded). Failed calls are counted in n_failed and excluded
from every metric. Missing data (no invoice, no searches) shrinks that metric's
denominator; it is never counted as zero.

Wilson score interval (95%, z = 1.96) instead of p +/- z*sqrt(p(1-p)/n): the normal
approximation gives impossible intervals like [-0.1, 0.3] or [1, 1] at small n or at 0%/100%,
which is exactly where a 5-call run lives.
"""
import math
from collections import defaultdict
from typing import Iterable, Optional

from backend.eval.voice_linter import CATEGORIES

Z95 = 1.96
JUDGE_RATES = {  # metric name -> judge field
    "judge_task_success": "task_success", "hallucination": "hallucination",
    "compliance_violation": "compliance_violation", "escalation_correct": "escalation_correct",
    "identity_verified": "identity_verified_before_amounts",
    "pressure_or_threat": "pressure_or_threat",
}


def wilson(k: int, n: int, z: float = Z95) -> Optional[tuple[float, float]]:
    if n == 0:
        return None
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return round(max(0.0, center - half), 4), round(min(1.0, center + half), 4)


def rate(k: int, n: int) -> dict:
    ci = wilson(k, n)
    return {"k": k, "n": n, "rate": round(k / n, 4) if n else None,
            "ci_low": ci[0] if ci else None, "ci_high": ci[1] if ci else None}


def _mean(values: Iterable[float]) -> Optional[float]:
    values = list(values)
    return round(sum(values) / len(values), 2) if values else None


def _agent_turns(call: dict) -> list[dict]:
    return [t for t in call["transcript"]["turns"] if t["speaker"] == "agent"]


def _group(calls: list[dict]) -> dict:
    ok = [c for c in calls if c["status"] == "ok"]
    checks = [c["checks"] for c in ok]
    verdicts = [c["judge"]["verdict"] for c in ok if c.get("judge") and c["judge"].get("verdict")]
    policy = [ch["policy_violations"] for ch in checks if ch.get("policy_violations") is not None]
    facts = [ch["facts"] for ch in checks if ch.get("facts") is not None]
    retrieval = [ch["retrieval"] for ch in checks]
    uncached = [t["latency_ms"] for c in ok for t in _agent_turns(c) if not t["cached"]]

    rates = {"outcome_pass": rate(sum(ch["outcome"]["passed"] for ch in checks), len(checks))}
    for name, field in JUDGE_RATES.items():
        rates[name] = rate(sum(v[field]["value"] for v in verdicts), len(verdicts))
    rates["policy_violation"] = rate(sum(1 for p in policy if p), len(policy))
    rates["retrieval_empty"] = rate(sum(r["empty_results"] for r in retrieval),
                                    sum(r["search_calls"] for r in retrieval))

    lint = {cat: _mean(ch["voice_counts"].get(cat, 0) for ch in checks) for cat in CATEGORIES}
    lint["total"] = _mean(sum(ch["voice_counts"].values()) for ch in checks)
    return {
        "n_calls": len(ok), "n_failed": len(calls) - len(ok), "n_judged": len(verdicts),
        "rates": rates,
        "lint_per_call": lint,
        "unverified_facts_per_call": _mean(f["unverified"] for f in facts),
        "policy_violations_per_call": _mean(len(p) for p in policy),
        "turns_per_call": _mean(len(c["transcript"]["turns"]) for c in ok),
        "agent_tokens_per_call": _mean(sum(t["input_tokens"] + t["output_tokens"]
                                           for t in _agent_turns(c)) for c in ok),
        "tone_avg": _mean(v["tone"]["score"] for v in verdicts),
        "agent_latency_ms": {"mean_per_turn": _mean(uncached), "uncached_turns": len(uncached)},
    }


def compute_metrics(calls: list[dict]) -> dict:
    by_persona: dict[str, list[dict]] = defaultdict(list)
    for c in calls:
        by_persona[c["scenario"]["persona"]].append(c)
    return {"overall": _group(calls),
            "per_persona": {p: _group(cs) for p, cs in sorted(by_persona.items())}}
