"""Seeded scenario generator: invoice + persona + expected outcomes."""
import argparse
import json
import random
from datetime import date, timedelta
from typing import Literal, Optional

from pydantic import BaseModel, computed_field

from backend.scenarios.personas import (
    INSTALLMENT_THRESHOLD_INR,
    PERSONAS,
    expected_outcomes_for,
)

SIM_DATE = date(2026, 11, 2)
GST_RATE = 0.18

_PREFIXES = ["Sundaram", "Kaveri", "Anand", "Meghna", "Rudra", "Tulsi", "Vihaan",
             "Narmada", "Orion Peak", "Shivalik", "Lotus Bay", "Ganga Ridge"]
_TRADES = ["Textiles", "Logistics", "Foods", "Plastics", "Engineering", "Traders",
           "Packaging", "Electricals", "Agro", "Print Works"]
_FIRST = ["Rohan", "Meera", "Arjun", "Kavita", "Imran", "Sneha", "Vikram",
          "Pooja", "Farhan", "Lakshmi", "Nikhil", "Divya"]
_LAST = ["Iyer", "Nair", "Kulkarni", "Bhatt", "Reddy", "Sheikh", "Chauhan",
         "Menon", "Deshpande", "Pillai"]
_DISPUTES = ["GST charged at 18% but items are in the 12% category",
             "quantity billed exceeds quantity delivered",
             "duplicate line item on the invoice",
             "agreed discount was not applied to the invoice"]


class PaymentClaim(BaseModel):
    utr: str
    date: date
    amount_inr: int


class Invoice(BaseModel):
    invoice_id: str
    company: str
    contact_name: str
    amount_inr: int  # total including GST
    gst_inr: int
    due_date: date
    days_overdue: int
    status: Literal["unpaid", "partially_paid"]
    amount_paid_inr: int
    dispute_history: list[str]
    broken_promises: list[date]
    payment_claim: Optional[PaymentClaim] = None

    @computed_field
    @property
    def outstanding_inr(self) -> int:
        return self.amount_inr - self.amount_paid_inr


class Scenario(BaseModel):
    scenario_id: int
    invoice: Invoice
    persona: str
    expected_outcomes: list[str]


def _round100(x: float) -> int:
    return int(round(x / 100) * 100)


def _amounts(rng: random.Random, above: bool) -> tuple[int, int, int]:
    """Return (amount_inr, gst_inr, amount_paid_inr) for the target band."""
    partial = rng.random() < 0.3
    if partial:
        base = _round100(rng.uniform(40000, 250000))
    elif above:
        base = _round100(rng.uniform(22000, 250000))
    else:
        base = _round100(rng.uniform(4000, 16000))
    gst = round(base * GST_RATE)
    amount = base + gst
    if not partial:
        return amount, gst, 0
    if above:
        target = _round100(rng.uniform(INSTALLMENT_THRESHOLD_INR + 1000, amount * 0.9))
    else:
        target = _round100(rng.uniform(5000, INSTALLMENT_THRESHOLD_INR - 1000))
    return amount, gst, amount - target


def _invoice(rng: random.Random, idx: int, persona: str, above: bool) -> Invoice:
    amount, gst, paid = _amounts(rng, above)
    overdue = rng.randint(7, 90)
    due = SIM_DATE - timedelta(days=overdue)
    promises = []
    if persona == "stalling" or rng.random() < 0.2:
        k = rng.randint(1, 2)
        promises = sorted(due + timedelta(days=rng.randint(1, overdue - 1)) for _ in range(k))
    disputes = []
    if persona == "disputes_amount":
        disputes = [rng.choice(_DISPUTES)]
    claim = None
    if persona == "already_paid":
        claim = PaymentClaim(
            utr="".join(str(rng.randint(0, 9)) for _ in range(12)),
            date=due + timedelta(days=rng.randint(1, overdue - 1)),
            amount_inr=amount - paid,
        )
    return Invoice(
        invoice_id=f"INV-2026-{1000 + idx * 7 + rng.randint(0, 6)}",
        company=f"{rng.choice(_PREFIXES)} {rng.choice(_TRADES)} Pvt Ltd",
        contact_name=f"{rng.choice(_FIRST)} {rng.choice(_LAST)}",
        amount_inr=amount,
        gst_inr=gst,
        due_date=due,
        days_overdue=overdue,
        status="partially_paid" if paid else "unpaid",
        amount_paid_inr=paid,
        dispute_history=disputes,
        broken_promises=promises,
        payment_claim=claim,
    )


def generate_scenarios(n: int, seed: int) -> list[Scenario]:
    rng = random.Random(seed)
    names = list(PERSONAS)
    order = [names[i % len(names)] for i in range(n)]  # even distribution
    rng.shuffle(order)
    seen: dict[str, int] = {}
    scenarios = []
    for idx, persona in enumerate(order):
        k = seen.get(persona, 0)
        seen[persona] = k + 1
        # installment-eligible personas alternate above/below the threshold
        alternate = persona in ("stalling", "hinglish_negotiator")
        above = (k % 2 == 0) if alternate else rng.random() < 0.5
        inv = _invoice(rng, idx, persona, above)
        scenarios.append(Scenario(
            scenario_id=idx,
            invoice=inv,
            persona=persona,
            expected_outcomes=expected_outcomes_for(PERSONAS[persona], inv.outstanding_inr),
        ))
    return scenarios


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Generate seeded scenarios as JSON")
    parser.add_argument("--n", type=int, default=14)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    out = [s.model_dump(mode="json") for s in generate_scenarios(args.n, args.seed)]
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
