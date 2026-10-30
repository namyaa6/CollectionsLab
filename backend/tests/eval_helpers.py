"""Small handmade invoices and transcripts for the eval tests."""
from datetime import date
from typing import Optional

from backend.scenarios.generator import Invoice, Scenario
from backend.sim.transcript import Transcript, Turn

# outstanding = 104902 - 39702 = 65200
INVOICE_DATA = dict(
    invoice_id="INV-2026-1004", company="Rudra Textiles Pvt Ltd", contact_name="Arjun Chauhan",
    amount_inr=104902, gst_inr=16002, due_date=date(2026, 8, 16), days_overdue=78,
    status="partially_paid", amount_paid_inr=39702, dispute_history=[],
    broken_promises=[date(2026, 9, 14), date(2026, 10, 13)])


def make_invoice(**kw) -> Invoice:
    return Invoice(**{**INVOICE_DATA, **kw})


def make_scenario(persona: str = "cooperative", **inv_kw) -> Scenario:
    return Scenario(scenario_id=0, invoice=make_invoice(**inv_kw), persona=persona,
                    expected_outcomes=["promise_to_pay"])


def make_transcript(turns: list[tuple], actions: Optional[list[dict]] = None,
                    persona: str = "cooperative", expected=("promise_to_pay",),
                    scenario: Optional[Scenario] = None, scenario_id: int = 0,
                    seed: int = 42) -> Transcript:
    """turns: (speaker, text) or (speaker, text, tool_calls)."""
    built = [Turn(speaker=t[0], text=t[1], tool_calls=t[2] if len(t) > 2 else []) for t in turns]
    return Transcript(scenario_id=scenario_id, persona=persona, expected_outcomes=list(expected),
                      prompt_version="v1", agent_model="a", sim_model="s", seed=seed,
                      turns=built, actions=actions or [], end_reason="end_call", scenario=scenario)


def action(tool: str, **args) -> dict:
    return {"tool": tool, "args": args, "result": {"status": "logged"}}


def get_invoice_call(invoice: Invoice) -> dict:
    from backend.agent.tools import agent_view
    return {"tool": "get_invoice", "args": {"invoice_id": invoice.invoice_id},
            "result": agent_view(invoice)}
