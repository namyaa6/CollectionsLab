import pytest

from backend.agent.agent import run_agent_turn
from backend.agent.context import AGENT_NAME, COMPANY_NAME, build_call_context
from backend.agent.tools import CallState
from backend.llm.fake import FakeLLMClient, text_reply, tool_reply
from backend.llm.types import LLMResponse, ToolCall
from backend.prompts import load_prompt
from backend.rag.policy_index import PolicyIndex
from backend.scenarios.generator import SIM_DATE, generate_scenarios


@pytest.fixture(scope="module")
def index():
    return PolicyIndex.from_file()


@pytest.fixture
def state():
    return CallState(invoice=generate_scenarios(7, 42)[0].invoice)


def hist():
    return [{"role": "user", "text": "[The call has connected.]"}]


def test_text_reply_ends_turn(index, state):
    client = FakeLLMClient([text_reply("Hello, this is Asha.")])
    turn = run_agent_turn(client, "m", "sys", hist(), state, index)
    assert (turn.text, turn.llm_calls, turn.error) == ("Hello, this is Asha.", 1, None)
    assert turn.tool_calls == []


def test_tool_call_executed_recorded_and_fed_back(index, state):
    inv_id = state.invoice.invoice_id
    client = FakeLLMClient([tool_reply("get_invoice", {"invoice_id": inv_id}),
                            text_reply("Your invoice is overdue.")])
    history = hist()
    turn = run_agent_turn(client, "m", "sys", history, state, index)
    assert turn.llm_calls == 2 and turn.text == "Your invoice is overdue."
    rec = turn.tool_calls[0]
    assert rec["tool"] == "get_invoice" and rec["result"]["invoice_id"] == inv_id
    tool_msg = [m for m in client.calls[1]["messages"] if m["role"] == "tool"][0]
    assert tool_msg["results"][0]["name"] == "get_invoice"
    assert (turn.input_tokens, turn.output_tokens, turn.latency_ms) == (10, 10, 20)
    assert len(history) == 4  # user, model(call), tool, model(text)


def test_state_changing_tool_updates_call_state(index, state):
    client = FakeLLMClient([tool_reply("log_dispute", {"reason": "wrong GST"}),
                            text_reply("Noted.")])
    run_agent_turn(client, "m", "sys", hist(), state, index)
    assert state.actions[0]["tool"] == "log_dispute"


def test_multiple_tool_calls_in_one_response(index, state):
    both = LLMResponse(tool_calls=[ToolCall("search_policy", {"query": "installments"}),
                                   ToolCall("log_dispute", {"reason": "x"})],
                       latency_ms=1, input_tokens=1, output_tokens=1)
    client = FakeLLMClient([both, text_reply("ok")])
    turn = run_agent_turn(client, "m", "sys", hist(), state, index)
    assert [c["tool"] for c in turn.tool_calls] == ["search_policy", "log_dispute"]


def test_speech_with_end_call_is_kept_and_turn_stops(index, state):
    resp = tool_reply("end_call", {"reason": "done"}, text="Thank you, goodbye.")
    turn = run_agent_turn(FakeLLMClient([resp]), "m", "sys", hist(), state, index)
    assert turn.text == "Thank you, goodbye." and state.ended and turn.error is None


def test_round_cap_stops_endless_tool_calls(index, state):
    client = FakeLLMClient([tool_reply("search_policy", {"query": "x"}) for _ in range(3)])
    turn = run_agent_turn(client, "m", "sys", hist(), state, index, max_rounds=3)
    assert turn.llm_calls == 3 and turn.error and turn.text == ""


def test_empty_reply_is_an_error(index, state):
    turn = run_agent_turn(FakeLLMClient([text_reply("")]), "m", "sys", hist(), state, index)
    assert turn.error and "empty reply" in turn.error


def test_bad_tool_args_return_error_to_model_not_crash(index, state):
    client = FakeLLMClient([tool_reply("log_promise_to_pay", {"date": "soon", "amount_inr": 5}),
                            text_reply("Sorry, which date?")])
    turn = run_agent_turn(client, "m", "sys", hist(), state, index)
    assert "error" in turn.tool_calls[0]["result"] and state.actions == []


def test_call_context_has_ids_and_date_but_no_amounts(state):
    inv = state.invoice
    ctx = build_call_context(inv)
    for needed in (inv.invoice_id, SIM_DATE.isoformat(), inv.company, inv.contact_name,
                   AGENT_NAME, COMPANY_NAME):
        assert needed in ctx
    for scenario in generate_scenarios(14, 42):
        i = scenario.invoice
        ctx = build_call_context(i)
        for secret in (str(i.amount_inr), str(i.gst_inr), "payment_claim", "UTR",
                       i.due_date.isoformat()):
            assert secret not in ctx
        if i.payment_claim:
            assert i.payment_claim.utr not in ctx


def test_call_context_roles_are_unambiguous(state):
    inv = state.invoice
    ctx = build_call_context(inv)
    assert f"{COMPANY_NAME} is the creditor" in ctx
    assert f"{inv.company} is the customer (the debtor) who owes" in ctx
    assert "not your employer and you do not represent it" in ctx
    assert f"on behalf of {inv.company}" not in ctx
    assert f"at {inv.company}" not in ctx.split("You are calling")[0]  # not the agent's employer


def test_load_prompt_v1_and_rejects_bad_versions():
    assert "collections agent" in load_prompt("v1").system
    with pytest.raises(ValueError):
        load_prompt("../v1")
    with pytest.raises(FileNotFoundError):
        load_prompt("v99")
