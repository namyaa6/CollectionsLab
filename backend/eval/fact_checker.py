"""Fact checker: is every amount, day count and date the AGENT says backed by a known fact?

matched    = equals an invoice fact, a policy constant, SIM_DATE, or something the debtor said
             EARLIER in the call
unverified = not matched (possible hallucination; the judge decides)
unparsed   = looked like a number or date but could not be parsed
This module never decides whether a statement is true, only whether it is grounded.
"""
from datetime import date
from typing import Optional

from backend.eval.dates import DateHit
from backend.eval.fact_extract import extract_dates, extract_numbers
from backend.eval.models import FactItem, FactReport
from backend.scenarios.generator import SIM_DATE, Invoice
from backend.scenarios.personas import (
    INSTALLMENT_SPAN_DAYS,
    INSTALLMENT_THRESHOLD_INR,
    PROMISE_WINDOW_DAYS,
)
from backend.sim.transcript import Transcript

PartialDate = tuple[Optional[int], Optional[int], Optional[int]]  # (year, month, day)


def _full(d: date) -> PartialDate:
    return d.year, d.month, d.day


def _dates_match(a: PartialDate, b: PartialDate) -> bool:
    """Compare only the parts both sides state, so a debtor's "the tenth" matches November 10th."""
    return all(x is None or y is None or x == y for x, y in zip(a, b)) and a[2] == b[2]


def known_facts(invoice: Invoice) -> tuple[set, set, list[PartialDate]]:
    amounts = {invoice.amount_inr, invoice.gst_inr, invoice.outstanding_inr,
               invoice.amount_paid_inr, INSTALLMENT_THRESHOLD_INR}
    days = {invoice.days_overdue, PROMISE_WINDOW_DAYS, INSTALLMENT_SPAN_DAYS}
    dates = [_full(d) for d in (invoice.due_date, SIM_DATE, *invoice.broken_promises)]
    return amounts, days, dates


def _hit_key(h: DateHit) -> PartialDate:
    return h.year, h.month, h.day


def check_facts(t: Transcript, invoice: Invoice) -> FactReport:
    amounts, days, dates = known_facts(invoice)
    items: list[FactItem] = []
    for i, turn in enumerate(t.turns):
        text = turn.text
        if turn.speaker == "agent":
            for h in extract_numbers(text):
                pool = days if h.kind == "days" else amounts
                status = ("unparsed" if h.value is None
                          else "matched" if h.value in pool else "unverified")
                items.append(FactItem(turn=i, kind=h.kind, status=status, snippet=h.snippet,
                                      value=None if h.value is None else str(h.value)))
            for d in extract_dates(text):
                if not d.valid:
                    status = "unparsed"
                else:
                    status = ("matched" if any(_dates_match(_hit_key(d), k) for k in dates)
                              else "unverified")
                items.append(FactItem(turn=i, kind="date", status=status, snippet=d.snippet,
                                      value=None if not d.valid else d.label()))
        else:  # whatever the debtor says becomes known for the agent turns after it
            for h in extract_numbers(text):
                if h.value is not None:
                    (days if h.kind == "days" else amounts).add(h.value)
            dates += [_hit_key(d) for d in extract_dates(text) if d.valid]
    counts = {s: sum(1 for it in items if it.status == s) for s in ("matched", "unverified", "unparsed")}
    return FactReport(items=items, **counts)
