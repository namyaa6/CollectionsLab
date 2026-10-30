"""Outcome check: pass if the summary outcome is expected and the logged outcomes don't contradict."""
from itertools import combinations

from backend.agent.summary_schema import CallSummary
from backend.eval.models import OutcomeResult

# Commitments (promise, installment) cannot coexist with each other or with a dispute /
# payment claim. "escalated" is deliberately absent: it may accompany anything.
_COMMIT = ("promise_to_pay", "installment_plan")
_RAISED = ("dispute_logged", "payment_claim_logged")
FORBIDDEN_PAIRS = frozenset(
    {frozenset(_COMMIT)} | {frozenset((c, r)) for c in _COMMIT for r in _RAISED})


def forbidden_in(logged: list[str]) -> list[list[str]]:
    return [sorted(p) for p in (frozenset(c) for c in combinations(set(logged), 2))
            if p in FORBIDDEN_PAIRS]


def check_outcome(summary: CallSummary, expected_outcomes: list[str]) -> OutcomeResult:
    in_expected = summary.outcome in expected_outcomes
    bad = forbidden_in(summary.logged_outcomes)
    return OutcomeResult(passed=in_expected and not bad, outcome=summary.outcome,
                         expected=expected_outcomes, in_expected=in_expected,
                         forbidden_pairs=bad)
