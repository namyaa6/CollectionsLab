import pytest

from backend.eval.policy_check import check_policy
from backend.tests.eval_helpers import action, make_invoice, make_transcript

INV = make_invoice()  # outstanding 65200
SMALL = make_invoice(amount_inr=15000, gst_inr=2288, amount_paid_inr=0)  # outstanding 15000


def rules(actions, invoice=INV, persona="cooperative"):
    t = make_transcript([("agent", "Hi.")], actions=actions, persona=persona)
    return [v.rule for v in check_policy(t, invoice)]


def plan(*parts):
    return action("log_installment_plan",
                  parts=[{"date": d, "amount_inr": a} for d, a in parts])


GOOD_PLAN = plan(("2026-11-10", 30000), ("2026-12-10", 35200))


def test_clean_plan_and_promise_have_no_violations():
    assert rules([GOOD_PLAN]) == []
    assert rules([action("log_promise_to_pay", date="2026-11-20", amount_inr=65200)]) == []


def test_no_actions_no_violations():
    assert rules([]) == []


def test_plan_on_ineligible_invoice():
    exact = make_invoice(amount_inr=20000, gst_inr=0, amount_paid_inr=0)  # exactly the threshold
    assert rules([plan(("2026-11-10", 20000))], exact) == ["installment_not_eligible"]
    assert rules([plan(("2026-11-10", 15000))], SMALL) == ["installment_not_eligible"]
    over = make_invoice(amount_inr=20001, gst_inr=0, amount_paid_inr=0)
    assert rules([plan(("2026-11-10", 20001))], over) == []


def test_three_parts_ok_four_parts_flagged():
    three = plan(("2026-11-10", 20000), ("2026-11-20", 20000), ("2026-12-01", 25200))
    four = plan(("2026-11-10", 20000), ("2026-11-20", 20000), ("2026-12-01", 20000),
                ("2026-12-05", 5200))
    assert rules([three]) == []
    assert rules([four]) == ["installment_too_many_parts"]


def test_parts_must_sum_exactly():
    assert rules([plan(("2026-11-10", 30000), ("2026-12-10", 35199))]) == ["installment_sum_mismatch"]
    assert rules([plan(("2026-11-10", 30000), ("2026-12-10", 35201))]) == ["installment_sum_mismatch"]


def test_last_part_day_60_ok_day_61_late():
    assert rules([plan(("2026-11-10", 30000), ("2027-01-01", 35200))]) == []  # SIM_DATE + 60
    assert rules([plan(("2026-11-10", 30000), ("2027-01-02", 35200))]) == ["installment_last_part_late"]


def test_last_part_means_latest_date_not_list_order():
    assert rules([plan(("2027-02-01", 30000), ("2026-11-10", 35200))]) == ["installment_last_part_late"]


def test_promise_window_day_30_ok_day_31_flagged_and_past_flagged():
    ok = action("log_promise_to_pay", date="2026-12-02", amount_inr=65200)   # SIM_DATE + 30
    late = action("log_promise_to_pay", date="2026-12-03", amount_inr=65200)
    past = action("log_promise_to_pay", date="2026-11-01", amount_inr=65200)
    assert rules([ok]) == []
    assert rules([late]) == ["promise_outside_window"]
    assert rules([past]) == ["promise_outside_window"]
    assert rules([action("log_promise_to_pay", date="2026-11-02", amount_inr=65200)]) == []


def test_promise_amount_must_equal_outstanding():
    assert rules([action("log_promise_to_pay", date="2026-11-10", amount_inr=30000)]) == [
        "promise_amount_not_outstanding"]


def test_promise_on_dispute_or_claim_call():
    promise = action("log_promise_to_pay", date="2026-11-10", amount_inr=65200)
    assert rules([action("log_dispute", reason="GST wrong"), promise]) == [
        "promise_on_dispute_or_claim_call"]
    claim = action("log_payment_claim", utr="123", date="2026-10-01", amount_inr=65200)
    assert rules([promise, claim]) == ["promise_on_dispute_or_claim_call"]


def test_persona_alone_makes_it_a_dispute_call():
    promise = action("log_promise_to_pay", date="2026-11-10", amount_inr=65200)
    assert rules([promise], persona="disputes_amount") == ["promise_on_dispute_or_claim_call"]
    assert rules([promise], persona="already_paid") == ["promise_on_dispute_or_claim_call"]
    assert rules([action("log_dispute", reason="x")], persona="disputes_amount") == []


def test_every_logged_call_is_checked_not_just_the_last():
    bad = action("log_promise_to_pay", date="2027-06-01", amount_inr=65200)
    good = action("log_promise_to_pay", date="2026-11-10", amount_inr=65200)
    assert rules([bad, good]) == ["promise_outside_window"]


@pytest.mark.parametrize("actions", [[action("log_dispute", reason="x")],
                                     [action("escalate_to_human", reason="abusive")]])
def test_other_tools_are_not_policy_violations(actions):
    assert rules(actions) == []
