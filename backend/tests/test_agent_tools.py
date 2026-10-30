import json

import pytest

from backend.agent.tools import (
    AGENT_VISIBLE_INVOICE_FIELDS, MUTATING_TOOLS, TOOL_NAMES, TOOL_SPECS,
    CallState, agent_view, execute_tool,
)
from backend.rag.policy_index import PolicyIndex
from backend.scenarios.generator import generate_scenarios

SCENARIOS = generate_scenarios(14, 42)
INDEX = PolicyIndex.from_file()
VALID_ARGS = {
    "get_invoice": lambda inv: {"invoice_id": inv.invoice_id},
    "search_policy": lambda inv: {"query": "installment plan rules"},
    "log_promise_to_pay": lambda inv: {"date": "2026-11-20", "amount_inr": 5000},
    "log_installment_plan": lambda inv: {"parts": [{"date": "2026-11-20", "amount_inr": 5000}]},
    "log_dispute": lambda inv: {"reason": "GST is wrong"},
    "log_payment_claim": lambda inv: {"utr": "123456789012", "date": "2026-10-20", "amount_inr": 5000},
    "escalate_to_human": lambda inv: {"reason": "legal threat"},
    "end_call": lambda inv: {"reason": "done"},
}


def scenario(persona):
    return next(s for s in SCENARIOS if s.persona == persona)


@pytest.fixture
def state():
    return CallState(invoice=SCENARIOS[0].invoice)


def run(state, name, args=None):
    return execute_tool(state, name, args if args is not None else VALID_ARGS[name](state.invoice), INDEX)


def test_promise_to_pay_is_logged(state):
    assert run(state, "log_promise_to_pay") == {"status": "logged"}
    assert state.actions == [{"tool": "log_promise_to_pay",
                              "args": {"date": "2026-11-20", "amount_inr": 5000},
                              "result": {"status": "logged"}}]
    assert not state.ended


def test_installment_plan_is_logged(state):
    parts = [{"date": "2026-11-20", "amount_inr": 6000.0}, {"date": "2026-12-20", "amount_inr": 4000}]
    run(state, "log_installment_plan", {"parts": parts})
    assert state.actions[0]["args"]["parts"] == [
        {"date": "2026-11-20", "amount_inr": 6000}, {"date": "2026-12-20", "amount_inr": 4000}]


def test_dispute_and_payment_claim_are_logged(state):
    run(state, "log_dispute")
    run(state, "log_payment_claim")
    assert [a["tool"] for a in state.actions] == ["log_dispute", "log_payment_claim"]
    assert state.actions[1]["args"] == {"utr": "123456789012", "date": "2026-10-20", "amount_inr": 5000}


def test_escalate_sets_flags(state):
    run(state, "escalate_to_human")
    assert (state.escalated, state.ended, state.end_reason) == (True, True, "legal threat")


def test_end_call_sets_ended_but_not_escalated(state):
    run(state, "end_call")
    assert (state.escalated, state.ended, state.end_reason) == (False, True, "done")


@pytest.mark.parametrize("name,args", [
    ("log_promise_to_pay", {"date": "next week", "amount_inr": 5000}),
    ("log_promise_to_pay", {"date": "2026-11-20", "amount_inr": -5}),
    ("log_promise_to_pay", {"date": "2026-11-20", "amount_inr": "5000"}),
    ("log_promise_to_pay", {"date": "2026-11-20"}),
    ("log_promise_to_pay", {"date": "2026-11-20", "amount_inr": 5000, "extra": 1}),
    ("log_installment_plan", {"parts": []}),
    ("log_installment_plan", {"parts": [{"date": "2026-11-20"}]}),
    ("log_dispute", {"reason": "  "}),
    ("log_payment_claim", {"utr": "", "date": "2026-10-20", "amount_inr": 5000}),
    ("end_call", {}),
])
def test_malformed_args_return_error_and_log_nothing(state, name, args):
    assert "error" in run(state, name, args)
    assert state.actions == [] and not state.ended


def test_unknown_tool_is_an_error(state):
    assert "error" in run(state, "delete_everything", {})


def test_get_invoice_only_returns_this_calls_invoice():
    a, b = SCENARIOS[0], SCENARIOS[1]
    assert a.invoice.invoice_id != b.invoice.invoice_id
    state_a = CallState(invoice=a.invoice)
    assert run(state_a, "get_invoice", {"invoice_id": a.invoice.invoice_id})["invoice_id"] == a.invoice.invoice_id
    assert run(state_a, "get_invoice", {"invoice_id": b.invoice.invoice_id}) == {"error": "invoice not found"}
    assert b.invoice.company not in json.dumps(run(state_a, "get_invoice", {"invoice_id": b.invoice.invoice_id}))


def test_agent_view_matches_the_allowlist(state):
    view = agent_view(state.invoice)
    assert tuple(view) == AGENT_VISIBLE_INVOICE_FIELDS
    assert view["outstanding_inr"] == state.invoice.outstanding_inr
    json.dumps(view)  # JSON-safe (dates are strings)


def test_payment_claim_never_appears_in_any_tool_result():
    sc = scenario("already_paid")
    claim = sc.invoice.payment_claim
    assert claim is not None
    st = CallState(invoice=sc.invoice)
    results = [run(st, name) for name in VALID_ARGS if name not in ("escalate_to_human", "end_call")]
    results.append(run(st, "get_invoice"))
    results.append(run(st, "search_policy", {"query": "payment claim UTR"}))
    results.append(run(st, "escalate_to_human"))
    blob = json.dumps(results)
    assert "payment_claim" not in blob
    assert claim.utr not in blob


@pytest.mark.parametrize("closer", ["end_call", "escalate_to_human"])
def test_logging_tools_are_refused_after_the_call_ended(state, closer):
    run(state, closer)
    before = list(state.actions)
    for name in sorted(MUTATING_TOOLS):
        assert run(state, name) == {"error": "call has ended"}
    assert state.actions == before
    assert "error" not in run(state, "get_invoice")
    assert run(state, "search_policy")["results"]


def test_search_policy_returns_sections():
    st = CallState(invoice=SCENARIOS[0].invoice)
    out = run(st, "search_policy", {"query": "I already paid, what UTR do I ask for"})
    assert out["results"][0]["section"] == "Payment Claim Handling"
    assert st.actions == []  # read-only tools are not logged as actions


def test_tool_specs_match_the_dispatch_table():
    names = [t.name for t in TOOL_SPECS]
    assert len(names) == len(set(names)) == 8
    assert set(names) == TOOL_NAMES == set(VALID_ARGS)
    for t in TOOL_SPECS:
        assert t.description
        assert t.parameters["type"] == "object"
        assert set(t.parameters["required"]) == set(t.parameters["properties"])
