import copy

import pytest

from backend.eval.metrics import compute_metrics, rate, wilson
from backend.eval.report import format_metrics
from backend.eval.voice_linter import CATEGORIES
from backend.tests.eval_helpers import JUDGE_OK


def turn(speaker, latency=100, cached=False, tokens=(10, 5)):
    return {"speaker": speaker, "latency_ms": latency, "cached": cached,
            "input_tokens": tokens[0], "output_tokens": tokens[1], "llm_calls": 1}


def rec(persona="cooperative", status="ok", passed=True, judge=None, lint=None,
        unverified=0, policy=(), searches=0, empty=0, turns=None, facts=True):
    verdict = copy.deepcopy(JUDGE_OK)
    for k, v in (judge or {}).items():
        verdict[k]["value"] = v
    counts = {c: 0 for c in CATEGORIES} | (lint or {})
    return {
        "status": status, "scenario": {"persona": persona},
        "transcript": {"turns": turns or [turn("agent"), turn("debtor"), turn("agent")]},
        "checks": {"outcome": {"passed": passed}, "voice_counts": counts,
                   "facts": {"unverified": unverified} if facts else None,
                   "policy_violations": [{"rule": r} for r in policy] if policy is not None else None,
                   "retrieval": {"search_calls": searches, "empty_results": empty}},
        "judge": {"verdict": verdict},
    }


def test_wilson_known_values():
    assert wilson(0, 10) == (0.0, 0.2775)
    assert wilson(10, 10) == (0.7225, 1.0)
    low, high = wilson(5, 10)
    assert low == pytest.approx(0.2366, abs=1e-4) and high == pytest.approx(0.7634, abs=1e-4)
    assert wilson(0, 0) is None


def test_rate_with_no_data_is_none_not_zero():
    assert rate(0, 0) == {"k": 0, "n": 0, "rate": None, "ci_low": None, "ci_high": None}
    assert rate(1, 4)["rate"] == 0.25


def test_rates_and_averages():
    calls = [rec(passed=True, lint={"long_turn": 2}, unverified=1, policy=["x"]),
             rec(passed=False, judge={"hallucination": True}, lint={"digit_amount": 1})]
    g = compute_metrics(calls)["overall"]
    assert g["n_calls"] == 2 and g["n_failed"] == 0 and g["n_judged"] == 2
    assert g["rates"]["outcome_pass"]["k"] == 1 and g["rates"]["outcome_pass"]["n"] == 2
    assert g["rates"]["hallucination"]["rate"] == 0.5
    assert g["rates"]["identity_verified"]["rate"] == 1.0
    assert g["rates"]["policy_violation"]["k"] == 1
    assert g["lint_per_call"]["long_turn"] == 1.0 and g["lint_per_call"]["total"] == 1.5
    assert g["unverified_facts_per_call"] == 0.5 and g["policy_violations_per_call"] == 0.5
    assert g["turns_per_call"] == 3 and g["agent_tokens_per_call"] == 30 and g["tone_avg"] == 5


def test_failed_calls_excluded_everywhere_but_counted():
    bad = rec(status="failed", passed=False, judge={"hallucination": True}, lint={"long_turn": 9})
    g = compute_metrics([rec(), bad])["overall"]
    assert g["n_calls"] == 1 and g["n_failed"] == 1
    assert g["rates"]["outcome_pass"] == rate(1, 1)
    assert g["rates"]["hallucination"]["n"] == 1 and g["rates"]["hallucination"]["k"] == 0
    assert g["lint_per_call"]["long_turn"] == 0


def test_latency_excludes_cached_turns():
    turns = [turn("agent", 100), turn("agent", 999, cached=True), turn("debtor", 5000),
             turn("agent", 300)]
    lat = compute_metrics([rec(turns=turns)])["overall"]["agent_latency_ms"]
    assert lat == {"mean_per_turn": 200.0, "uncached_turns": 2}
    all_cached = [turn("agent", 100, cached=True)]
    lat = compute_metrics([rec(turns=all_cached)])["overall"]["agent_latency_ms"]
    assert lat == {"mean_per_turn": None, "uncached_turns": 0}


def test_retrieval_empty_rate_over_searches():
    g = compute_metrics([rec(searches=3, empty=1), rec(searches=1, empty=1), rec()])["overall"]
    assert g["rates"]["retrieval_empty"] == rate(2, 4)
    assert compute_metrics([rec()])["overall"]["rates"]["retrieval_empty"]["rate"] is None


def test_missing_invoice_shrinks_denominators():
    g = compute_metrics([rec(unverified=2), rec(facts=False, policy=None)])["overall"]
    assert g["unverified_facts_per_call"] == 2 and g["rates"]["policy_violation"]["n"] == 1


def test_per_persona_grouping():
    m = compute_metrics([rec("angry"), rec("angry", passed=False), rec("cooperative"),
                         rec("legal_threat", status="failed")])
    assert list(m["per_persona"]) == ["angry", "cooperative", "legal_threat"]
    assert m["per_persona"]["angry"]["rates"]["outcome_pass"] == rate(1, 2)
    assert m["per_persona"]["legal_threat"]["n_failed"] == 1
    assert m["per_persona"]["legal_threat"]["rates"]["outcome_pass"]["rate"] is None


def test_report_formats_rates_cis_and_na():
    out = format_metrics(compute_metrics([rec(), rec("angry", status="failed")]))
    assert "1 ok, 1 failed" in out and "95% CI [21%, 100%]" in out
    assert "n/a" in out and "angry" in out and "uncached turns only" in out
