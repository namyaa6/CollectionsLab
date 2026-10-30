import pytest

from backend.eval.fact_checker import check_facts
from backend.tests.eval_helpers import make_invoice, make_transcript

INV = make_invoice()  # outstanding 65200, amount 104902, gst 16002, paid 39702, 78 days overdue


def statuses(agent_text, *, before=()):
    """Status of every item in one agent turn, optionally after earlier debtor turns."""
    turns = [("debtor", d) for d in before] + [("agent", agent_text)]
    report = check_facts(make_transcript(turns), INV)
    return [(i.kind, i.status) for i in report.items]


@pytest.mark.parametrize("text", [
    "You owe ₹65,200.", "The total is 104,902 rupees.",
    "The GST was 16,002 rupees.", "You already paid 39,702 rupees.",
    "Sixty-five thousand two hundred rupees is outstanding.",
    "Installments need more than 20,000 rupees.",
])
def test_invoice_and_policy_amounts_match(text):
    assert statuses(text) == [("amount", "matched")]


@pytest.mark.parametrize("text", [
    "It was due on August 16th, 2026.", "You missed September 14th.", "You missed 13 October.",
    "Today is November 2nd, 2026.", "Pay by 2026-11-02.",
])
def test_invoice_dates_match(text):
    assert statuses(text) == [("date", "matched")]


@pytest.mark.parametrize("text", [
    "It is 78 days overdue.", "It is seventy-eight days overdue.",
    "Within 30 days.", "Within sixty days.",
])
def test_day_counts_match(text):
    assert statuses(text) == [("days", "matched")]


def test_invented_amount_date_and_days_are_unverified():
    assert statuses("You owe 70,000 rupees since August 20th, 99 days ago.") == [
        ("amount", "unverified"), ("days", "unverified"), ("date", "unverified")]


def test_debtor_proposed_date_is_matched_even_in_a_different_form():
    out = statuses("Thank you for November 10th, 2026.",
                   before=["I can pay by the tenth of this month."])
    assert out == [("date", "matched")]


def test_agent_date_is_unverified_when_debtor_never_said_it():
    assert statuses("Thank you for November 10th, 2026.") == [("date", "unverified")]


def test_debtor_proposed_amount_is_matched():
    assert statuses("Thanks for offering 30,000 rupees.", before=["I can pay 30000 rupees now."]) == [
        ("amount", "matched")]
    assert statuses("Thanks for offering 30,000 rupees.") == [("amount", "unverified")]


def test_debtor_saying_it_later_does_not_count():
    t = make_transcript([("agent", "Is 30,000 rupees fine?"), ("debtor", "Yes, 30,000 rupees.")])
    assert [i.status for i in check_facts(t, INV).items] == ["unverified"]


def test_debtor_month_mismatch_is_not_matched():
    out = statuses("Thank you for December 10th.", before=["I can pay on 10 November."])
    assert out == [("date", "unverified")]


def test_years_in_spoken_dates_are_one_date_not_amounts():
    for text in ["November 10th, 2026", "10th of November 2026"]:
        report = check_facts(make_transcript(
            [("debtor", "I'll pay on November 10th."), ("agent", f"Noted, {text}.")]), INV)
        assert [(i.kind, i.status) for i in report.items] == [("date", "matched")]


def test_unparsed_items_and_counts():
    report = check_facts(make_transcript([
        ("agent", "You owe lakhs of rupees, due on 31/02, plus ₹65,200 and 99,999 rupees.")]), INV)
    assert (report.matched, report.unverified, report.unparsed) == (1, 1, 2)
    assert {i.status for i in report.items if i.value is None} == {"unparsed"}


def test_debtor_numbers_are_never_reported():
    report = check_facts(make_transcript([("debtor", "Pay 999,999 rupees on 5 May.")]), INV)
    assert report.items == []


def test_item_has_turn_and_snippet():
    report = check_facts(make_transcript([("agent", "Hi."), ("debtor", "Hello."),
                                          ("agent", "You owe ₹70,000.")]), INV)
    [item] = report.items
    assert (item.turn, item.snippet, item.value) == (2, "₹70,000", "70000")
