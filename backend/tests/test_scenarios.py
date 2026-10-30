import json
import re
import subprocess
import sys
from collections import Counter
from datetime import timedelta
from pathlib import Path

import pytest

from backend.scenarios.generator import SIM_DATE, generate_scenarios, main
from backend.scenarios.personas import (
    INSTALLMENT_THRESHOLD_INR,
    PERSONAS,
    expected_outcomes_for,
)

ROOT = Path(__file__).resolve().parents[2]
POLICY = (ROOT / "data" / "policy" / "collections_policy.md").read_text(encoding="utf-8")


def test_same_seed_identical_and_different_seed_differs():
    a = [s.model_dump(mode="json") for s in generate_scenarios(14, 42)]
    b = [s.model_dump(mode="json") for s in generate_scenarios(14, 42)]
    c = [s.model_dump(mode="json") for s in generate_scenarios(14, 7)]
    assert a == b
    assert a != c


def test_personas_module():
    assert len(PERSONAS) == 7
    for name, p in PERSONAS.items():
        assert p.name == name and p.behavior and p.expected_outcomes
    assert PERSONAS["disputes_amount"].expected_outcomes == ["dispute_logged"]


@pytest.mark.parametrize("seed", [1, 42, 99])
def test_fields_valid(seed):
    for s in generate_scenarios(21, seed):
        inv = s.invoice
        assert s.persona in PERSONAS
        assert inv.gst_inr == round((inv.amount_inr - inv.gst_inr) * 0.18)
        assert inv.due_date + timedelta(days=inv.days_overdue) == SIM_DATE
        assert inv.outstanding_inr == inv.amount_inr - inv.amount_paid_inr > 0
        if inv.status == "unpaid":
            assert inv.amount_paid_inr == 0
        else:
            assert 0 < inv.amount_paid_inr < inv.amount_inr
        assert all(inv.due_date < d < SIM_DATE for d in inv.broken_promises)
        assert s.expected_outcomes


def test_personas_evenly_distributed():
    counts = Counter(s.persona for s in generate_scenarios(14, 42))
    assert set(counts.values()) == {2} and len(counts) == 7
    counts = Counter(s.persona for s in generate_scenarios(10, 42))
    assert max(counts.values()) - min(counts.values()) <= 1


def test_payment_claim_only_for_already_paid():
    for s in generate_scenarios(21, 42):
        claim = s.invoice.payment_claim
        if s.persona == "already_paid":
            assert claim is not None
            assert claim.amount_inr == s.invoice.outstanding_inr
            assert len(claim.utr) == 12 and claim.utr.isdigit()
            assert s.invoice.due_date < claim.date < SIM_DATE
        else:
            assert claim is None


def test_expected_outcomes_for_threshold_boundary():
    t = INSTALLMENT_THRESHOLD_INR
    p = PERSONAS["stalling"]
    assert expected_outcomes_for(p, t - 1) == ["promise_to_pay"]
    assert expected_outcomes_for(p, t) == ["promise_to_pay"]
    assert set(expected_outcomes_for(p, t + 1)) == {"promise_to_pay", "installment_plan"}
    assert expected_outcomes_for(PERSONAS["hinglish_negotiator"], t) == ["promise_to_pay"]
    assert expected_outcomes_for(PERSONAS["cooperative"], t - 1) == ["promise_to_pay"]


def test_installment_only_above_threshold():
    scenarios = generate_scenarios(14, 42)
    for s in scenarios:
        allowed = "installment_plan" in PERSONAS[s.persona].expected_outcomes
        above = s.invoice.outstanding_inr > INSTALLMENT_THRESHOLD_INR
        assert ("installment_plan" in s.expected_outcomes) == (allowed and above)
        if s.persona == "disputes_amount":
            assert s.expected_outcomes == ["dispute_logged"]
    for name in ("stalling", "hinglish_negotiator"):
        flags = {s.invoice.outstanding_inr > INSTALLMENT_THRESHOLD_INR
                 for s in scenarios if s.persona == name}
        assert flags == {True, False}


def test_policy_headings_and_threshold():
    for heading in ["Identity Verification", "Calling Etiquette", "Installment Rules",
                    "No Discounts or Waivers", "No Threats or Legal Claims",
                    "Dispute Handling", "Payment Claim Handling",
                    "Escalation Triggers", "Language"]:
        assert f"## {heading}" in POLICY
    amounts = re.findall(r"INR ([\d,]+)", POLICY)
    assert amounts and all(int(a.replace(",", "")) == INSTALLMENT_THRESHOLD_INR for a in amounts)
    escalation = POLICY.split("## Escalation Triggers")[1].split("## ")[0]
    assert "repeated" not in escalation.lower()


def test_cli_prints_json(capsys):
    main(["--n", "14", "--seed", "42"])
    data = json.loads(capsys.readouterr().out)
    assert len(data) == 14 and "outstanding_inr" in data[0]["invoice"]


def test_cli_module_runs():
    r = subprocess.run([sys.executable, "-m", "backend.scenarios.generator", "--n", "3"],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0 and len(json.loads(r.stdout)) == 3
