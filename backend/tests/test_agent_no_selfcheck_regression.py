"""Pins the exact requests an agent turn makes when self_check is off (v1-v3).

Written against the code before the self-check feature existed. A v1 eval run can resume
later, so these must keep passing unchanged: same requests, same history, same turn fields.
"""
import pytest

from backend.agent.agent import run_agent_turn
from backend.agent.context import build_call_context
from backend.agent.tools import TOOL_SPECS, CallState
from backend.llm.fake import FakeLLMClient, text_reply, tool_reply
from backend.prompts import load_prompt, prompt_file_hash
from backend.rag.policy_index import PolicyIndex
from backend.scenarios.generator import generate_scenarios
from backend.sim.simulator import CONNECTED, simulate

V1_HASH = "9abc3a9de903adfac7e58cfbb2bee50768bd5b5b808961e60a2d798b88b6e500"
REQUEST_KEYS = {"model", "messages", "system", "tools", "temperature", "json_mode",
                "response_schema", "use_cache", "cache_salt"}


@pytest.fixture(scope="module")
def index():
    return PolicyIndex.from_file()


def scenario():
    return next(s for s in generate_scenarios(14, 42) if s.persona == "already_paid")


def test_turn_requests_history_and_fields_are_unchanged(index):
    state = CallState(invoice=scenario().invoice)
    inv_id = state.invoice.invoice_id
    client = FakeLLMClient([tool_reply("get_invoice", {"invoice_id": inv_id}),
                            text_reply("Hello, this is Asha.")])
    history = [{"role": "user", "text": CONNECTED}]
    turn = run_agent_turn(client, "agent-m", "SYS", history, state, index)

    assert len(client.calls) == 2  # no extra request of any kind
    first, second = client.calls
    for req in client.calls:
        assert set(req) == REQUEST_KEYS
        assert (req["model"], req["system"], req["tools"], req["temperature"]) == \
            ("agent-m", "SYS", TOOL_SPECS, 0.0)
        assert (req["json_mode"], req["response_schema"], req["use_cache"], req["cache_salt"]) == \
            (False, None, True, None)
    assert first["messages"] == [{"role": "user", "text": CONNECTED}]
    assert [m["role"] for m in second["messages"]] == ["user", "model", "tool"]
    assert second["messages"][1]["tool_calls"][0].name == "get_invoice"

    assert [m["role"] for m in history] == ["user", "model", "tool", "model"]
    assert history[3] == {"role": "model", "text": "Hello, this is Asha.", "tool_calls": []}
    assert turn.text == "Hello, this is Asha."
    assert [c["tool"] for c in turn.tool_calls] == ["get_invoice"]
    assert (turn.latency_ms, turn.input_tokens, turn.output_tokens) == (20, 10, 10)
    assert (turn.llm_calls, turn.cached, turn.error) == (2, False, None)
    old_fields = {"text", "tool_calls", "latency_ms", "input_tokens", "output_tokens",
                  "llm_calls", "cached", "error"}
    assert old_fields <= set(vars(turn)) <= old_fields | {"self_check"}
    assert getattr(turn, "self_check", None) is None  # a later optional field stays empty


def test_simulator_v1_request_sequence_is_unchanged(index):
    s = scenario()
    prompt = load_prompt("v1")
    client = FakeLLMClient([text_reply("Hello."), text_reply("Hi."),
                            tool_reply("end_call", {"reason": "d"}, text="Bye.")])
    t = simulate(s, client, prompt, "agent-m", "sim-m", index, seed=3)

    assert [c["model"] for c in client.calls] == ["agent-m", "sim-m", "agent-m"]
    assert all(c["response_schema"] is None and c["json_mode"] is False for c in client.calls)
    agent_system = f"{prompt.system}\n\n{build_call_context(s.invoice)}"
    assert client.calls[0]["system"] == client.calls[2]["system"] == agent_system
    assert client.calls[1]["tools"] is None and client.calls[1]["cache_salt"] == "seed=3"
    assert [x.speaker for x in t.turns] == ["agent", "debtor", "agent"]
    assert [x.text for x in t.turns] == ["Hello.", "Hi.", "Bye."]
    assert [x.llm_calls for x in t.turns] == [1, 1, 1]


def test_v1_prompt_file_and_flags_are_unchanged():
    assert prompt_file_hash("v1") == V1_HASH  # the resume key of a stored v1 run
    assert getattr(load_prompt("v1"), "self_check", False) is False
