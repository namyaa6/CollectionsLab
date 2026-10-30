import pytest

from backend.agent.summary_schema import CallSummary
from backend.eval.outcome_check import check_outcome, forbidden_in


def summary(outcome, logged):
    return CallSummary(outcome=outcome, next_action="x", logged_outcomes=logged)


def test_pass_when_outcome_expected_and_nothing_forbidden():
    r = check_outcome(summary("promise_to_pay", ["promise_to_pay"]), ["promise_to_pay", "escalated"])
    assert r.passed and r.in_expected and r.forbidden_pairs == []


def test_fail_when_outcome_not_expected():
    r = check_outcome(summary("promise_to_pay", ["promise_to_pay"]), ["escalated"])
    assert not r.passed and not r.in_expected


def test_fail_on_forbidden_combination_even_if_outcome_expected():
    r = check_outcome(summary("dispute_logged", ["promise_to_pay", "dispute_logged"]),
                      ["dispute_logged"])
    assert r.in_expected and not r.passed
    assert r.forbidden_pairs == [["dispute_logged", "promise_to_pay"]]


@pytest.mark.parametrize("logged", [
    ["promise_to_pay", "installment_plan"], ["promise_to_pay", "dispute_logged"],
    ["promise_to_pay", "payment_claim_logged"], ["installment_plan", "dispute_logged"],
    ["installment_plan", "payment_claim_logged"],
])
def test_forbidden_pairs(logged):
    assert len(forbidden_in(logged)) == 1


@pytest.mark.parametrize("logged", [
    [], ["promise_to_pay"], ["escalated"], ["promise_to_pay", "escalated"],
    ["dispute_logged", "escalated"], ["dispute_logged", "payment_claim_logged"],
])
def test_allowed_combinations(logged):
    assert forbidden_in(logged) == []


def test_no_resolution_expected_only_when_listed():
    assert check_outcome(summary("no_resolution", []), ["promise_to_pay"]).passed is False
