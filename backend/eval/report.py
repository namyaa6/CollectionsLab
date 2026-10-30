"""Plain-text metrics table for the runner's terminal output."""
from typing import Optional

from backend.eval.metrics import JUDGE_RATES

RATE_ORDER = ("outcome_pass", *JUDGE_RATES, "policy_violation", "retrieval_empty")
PERSONA_COLS = (("outcome_pass", "outcome"), ("judge_task_success", "success"),
                ("hallucination", "halluc"), ("compliance_violation", "complia"),
                ("escalation_correct", "escal_ok"), ("pressure_or_threat", "pressure"))


def _pct(x: Optional[float]) -> str:
    return "n/a" if x is None else f"{x * 100:.0f}%"


def _num(x: Optional[float]) -> str:
    return "n/a" if x is None else f"{x:g}"


def _rate_row(name: str, r: dict) -> str:
    ci = "n/a" if r["rate"] is None else f"[{_pct(r['ci_low'])}, {_pct(r['ci_high'])}]"
    return f"  {name:<22} {_pct(r['rate']):>5}  {r['k']:>3}/{r['n']:<4} 95% CI {ci}"


def format_overall(g: dict) -> list[str]:
    lines = [f"Calls: {g['n_calls']} ok, {g['n_failed']} failed (excluded), "
             f"{g['n_judged']} judged", "Rates:"]
    lines += [_rate_row(name, g["rates"][name]) for name in RATE_ORDER]
    lat = g["agent_latency_ms"]
    lint = ", ".join(f"{k}={_num(v)}" for k, v in g["lint_per_call"].items())
    lines += [
        "Per call:",
        f"  lint violations        {lint}",
        f"  unverified facts       {_num(g['unverified_facts_per_call'])}",
        f"  policy violations      {_num(g['policy_violations_per_call'])}",
        f"  turns                  {_num(g['turns_per_call'])}",
        f"  agent tokens           {_num(g['agent_tokens_per_call'])}",
        f"  judge tone (1-5)       {_num(g['tone_avg'])}",
        f"  agent latency/turn ms  {_num(lat['mean_per_turn'])} "
        f"(uncached turns only, {lat['uncached_turns']} turns)",
    ]
    return lines


def format_per_persona(per: dict) -> list[str]:
    head = f"  {'persona':<20} {'ok':>3} {'fail':>4} " + " ".join(f"{c:>8}" for _, c in PERSONA_COLS)
    lines = ["Per persona (rate, k/n):", head]
    for persona, g in per.items():
        cells = [f"{_pct(g['rates'][m]['rate']):>4} {g['rates'][m]['k']}/{g['rates'][m]['n']}"
                 for m, _ in PERSONA_COLS]
        lines.append(f"  {persona:<20} {g['n_calls']:>3} {g['n_failed']:>4} "
                     + " ".join(f"{c:>8}" for c in cells))
    return lines


def format_metrics(metrics: dict) -> str:
    return "\n".join(["== Overall ==", *format_overall(metrics["overall"]), "",
                      *format_per_persona(metrics["per_persona"])])
