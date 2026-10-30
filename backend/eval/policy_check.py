"""Policy check: did the logged actions follow the collections policy?

The tools log whatever the agent sends (see tools.py), so every logged call is checked,
not just the last one. Rules are named so the dashboard can count them.
"""
from datetime import date, timedelta

from backend.eval.models import PolicyViolation
from backend.scenarios.generator import SIM_DATE, Invoice
from backend.scenarios.personas import (
    INSTALLMENT_SPAN_DAYS,
    INSTALLMENT_THRESHOLD_INR,
    MAX_INSTALLMENT_PARTS,
    PROMISE_WINDOW_DAYS,
)
from backend.sim.transcript import Transcript

DISPUTE_OR_CLAIM_PERSONAS = ("disputes_amount", "already_paid")


def _v(rule: str, detail: str) -> PolicyViolation:
    return PolicyViolation(rule=rule, detail=detail)


def _installment_violations(args: dict, outstanding: int) -> list[PolicyViolation]:
    parts = args["parts"]
    out = []
    if outstanding <= INSTALLMENT_THRESHOLD_INR:
        out.append(_v("installment_not_eligible",
                      f"outstanding {outstanding} is not above {INSTALLMENT_THRESHOLD_INR}"))
    if len(parts) > MAX_INSTALLMENT_PARTS:
        out.append(_v("installment_too_many_parts",
                      f"{len(parts)} parts, at most {MAX_INSTALLMENT_PARTS} allowed"))
    total = sum(p["amount_inr"] for p in parts)
    if total != outstanding:
        out.append(_v("installment_sum_mismatch", f"parts add up to {total}, outstanding is {outstanding}"))
    last = max(date.fromisoformat(p["date"]) for p in parts)
    if last > SIM_DATE + timedelta(days=INSTALLMENT_SPAN_DAYS):
        out.append(_v("installment_last_part_late",
                      f"last part {last} is more than {INSTALLMENT_SPAN_DAYS} days after {SIM_DATE}"))
    return out


def _promise_violations(args: dict, outstanding: int) -> list[PolicyViolation]:
    out = []
    when = date.fromisoformat(args["date"])
    if not SIM_DATE <= when <= SIM_DATE + timedelta(days=PROMISE_WINDOW_DAYS):
        out.append(_v("promise_outside_window",
                      f"promise date {when} is not within {PROMISE_WINDOW_DAYS} days of {SIM_DATE}"))
    if args["amount_inr"] != outstanding:
        out.append(_v("promise_amount_not_outstanding",
                      f"promised {args['amount_inr']}, outstanding is {outstanding}"))
    return out


def check_policy(t: Transcript, invoice: Invoice) -> list[PolicyViolation]:
    outstanding = invoice.outstanding_inr
    tools = [a["tool"] for a in t.actions]
    out: list[PolicyViolation] = []
    for a in t.actions:
        if a["tool"] == "log_installment_plan":
            out += _installment_violations(a["args"], outstanding)
        elif a["tool"] == "log_promise_to_pay":
            out += _promise_violations(a["args"], outstanding)
    dispute_call = (t.persona in DISPUTE_OR_CLAIM_PERSONAS
                    or "log_dispute" in tools or "log_payment_claim" in tools)
    if dispute_call and "log_promise_to_pay" in tools:
        out.append(_v("promise_on_dispute_or_claim_call",
                      "promise_to_pay logged on a dispute or payment-claim call"))
    return out
