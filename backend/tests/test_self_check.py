import json

import pytest
from google.genai import types as gt

from backend.agent.agent import run_agent_turn
from backend.agent.self_check import render_for_check, replace_spoken
from backend.agent.tools import TOOL_SPECS, CallState
from backend.llm.fake import FakeLLMClient, text_reply, tool_reply
from backend.llm.types import LLMResponse
from backend.prompts import PROMPTS_DIR, load_prompt
from backend.rag.policy_index import PolicyIndex
from backend.scenarios.generator import generate_scenarios

CHECK = "You review drafts."


@pytest.fixture(scope="module")
def index():
    return PolicyIndex.from_file()


@pytest.fixture
def state():
    return CallState(invoice=generate_scenarios(7, 42)[0].invoice)


def hist():
    return [{"role": "user", "text": "[The call has connected.]"}]


def verdict(ok, revised="", issues=()):
    return text_reply(json.dumps({"ok": ok, "issues": list(issues), "revised": revised}))


def turn_with_check(client, state, index, history=None):
    return run_agent_turn(client, "m", "sys", history or hist(), state, index,
                          self_check=True, check_system=CHECK)


def test_passing_check_keeps_the_draft(index, state):
    client = FakeLLMClient([text_reply("Hello, this is Asha."), verdict(True, "Hello, this is Asha.")])
    turn = turn_with_check(client, state, index)
    assert turn.text == "Hello, this is Asha."
    sc = turn.self_check
    assert (sc["draft"], sc["final"], sc["revised"], sc["error"]) == \
        ("Hello, this is Asha.", "Hello, this is Asha.", False, None)


def test_revision_replaces_text_and_history_and_keeps_the_draft(index, state):
    client = FakeLLMClient([text_reply("You owe Rs 500."),
                            verdict(False, "Am I speaking with the contact?", ["amount before identity"])])
    history = hist()
    turn = turn_with_check(client, state, index, history)
    assert turn.text == "Am I speaking with the contact?"
    assert turn.self_check["draft"] == "You owe Rs 500." and turn.self_check["revised"]
    assert turn.self_check["issues"] == ["amount before identity"]
    assert history[-1]["text"] == "Am I speaking with the contact?"  # next turn sees what was said


def test_check_cost_is_added_to_the_turn_and_recorded_separately(index, state):
    client = FakeLLMClient([text_reply("Hi."), verdict(True, "Hi.")])
    turn = turn_with_check(client, state, index)
    assert (turn.llm_calls, turn.latency_ms, turn.input_tokens, turn.output_tokens) == (2, 20, 10, 10)
    sc = turn.self_check
    assert (sc["latency_ms"], sc["input_tokens"], sc["output_tokens"]) == (10, 5, 5)


def test_check_request_uses_schema_no_tools_and_sees_facts_not_secrets(index, state):
    inv_id = state.invoice.invoice_id
    client = FakeLLMClient([tool_reply("get_invoice", {"invoice_id": inv_id}),
                            text_reply("Draft reply."), verdict(True, "Draft reply.")])
    turn_with_check(client, state, index)
    req = client.calls[-1]
    assert req["system"] == CHECK and req["tools"] is None and req["temperature"] == 0.0
    assert req["response_schema"].__name__ == "SelfCheckVerdict"
    body = req["messages"][0]["text"]
    assert "DRAFT:\nDraft reply." in body and f'"invoice_id": "{inv_id}"' in body
    assert "get_invoice" in body and "sys" in body
    assert "payment_claim" not in body  # agent_view hides it, so the checker never sees it


def test_bad_json_or_error_falls_back_to_the_draft(index, state):
    for bad in (text_reply("not json"), LLMResponse(text="", finish_reason="SAFETY")):
        client = FakeLLMClient([text_reply("Hello."), bad])
        turn = turn_with_check(client, state, index)
        assert turn.text == "Hello." and turn.error is None
        assert turn.self_check["error"] and turn.self_check["revised"] is False


def test_failed_check_does_not_fail_the_turn_when_empty_revision(index, state):
    client = FakeLLMClient([text_reply("Hello."), verdict(False, "", ["bad"])])
    turn = turn_with_check(client, state, index)
    assert turn.text == "Hello." and turn.self_check["revised"] is False


def test_empty_or_errored_turn_is_not_checked(index, state):
    client = FakeLLMClient([text_reply("")])
    turn = turn_with_check(client, state, index)
    assert turn.error and turn.self_check is None and len(client.calls) == 1
    client = FakeLLMClient([tool_reply("search_policy", {"query": "x"}) for _ in range(2)])
    turn = run_agent_turn(client, "m", "sys", hist(), state, index, max_rounds=2,
                          self_check=True, check_system=CHECK)
    assert turn.error and turn.self_check is None and len(client.calls) == 2


def test_speech_with_end_call_is_checked_and_actions_stay(index, state):
    client = FakeLLMClient([tool_reply("end_call", {"reason": "done"}, text="Thanks, bye."),
                            verdict(True, "Thanks, bye.")])
    turn = turn_with_check(client, state, index)
    assert state.ended and turn.text == "Thanks, bye." and turn.self_check["final"] == "Thanks, bye."


def test_explicit_false_makes_the_same_requests_as_the_default(index):
    def run(**kw):
        st = CallState(invoice=generate_scenarios(7, 42)[0].invoice)
        client = FakeLLMClient([tool_reply("get_invoice", {"invoice_id": st.invoice.invoice_id}),
                                text_reply("Hello.")])
        turn = run_agent_turn(client, "m", "sys", hist(), st, index, **kw)
        return client.calls, vars(turn)

    default_calls, default_turn = run()
    off_calls, off_turn = run(self_check=False, check_system="ignored")
    assert default_calls == off_calls and default_turn == off_turn
    assert all(c["tools"] == TOOL_SPECS and c["response_schema"] is None for c in off_calls)
    assert off_turn["self_check"] is None and off_turn["llm_calls"] == 2


def test_replace_spoken_edits_raw_content_and_keeps_function_calls():
    raw = gt.Content(role="model", parts=[
        gt.Part(text="thinking", thought=True),
        gt.Part(text="Old draft."),
        gt.Part.from_function_call(name="end_call", args={"reason": "d"})])
    history = [{"role": "user", "text": "hi"}, {"role": "model", "raw": raw}]
    replace_spoken(history, 1, "New text.")
    parts = history[1]["raw"].parts
    assert [p.text for p in parts if p.text and not p.thought] == ["New text."]
    assert any(p.thought for p in parts) and any(p.function_call for p in parts)
    assert raw.parts[1].text == "Old draft."  # original object is not mutated


def test_replace_spoken_moves_text_to_last_spoken_message_when_several():
    history = [{"role": "user", "text": "hi"},
               {"role": "model", "text": "First.", "tool_calls": [{"name": "x", "args": {}}]},
               {"role": "tool", "results": []},
               {"role": "model", "text": "Second.", "tool_calls": []}]
    replace_spoken(history, 1, "Only this.")
    assert [m.get("text") for m in history if m["role"] == "model"] == ["", "Only this."]


def test_render_reads_raw_content_and_separates_past_from_this_turn():
    raw = gt.Content(role="model", parts=[gt.Part(text="Earlier line."),
                                          gt.Part(text="secret thought", thought=True)])
    history = [{"role": "user", "text": "hello"}, {"role": "model", "raw": raw},
               {"role": "user", "text": "yes it is me"},
               {"role": "model", "text": "", "tool_calls": [{"name": "log_dispute", "args": {}}]}]
    body = render_for_check("SYS", history, 3, "the draft")
    assert "AGENT: Earlier line." in body and "CUSTOMER: yes it is me" in body
    assert "secret thought" not in body and "called log_dispute" in body


def test_prompt_versions_and_flags():
    v1, v2, v3, v4 = (load_prompt(v) for v in ("v1", "v2", "v3", "v4"))
    assert not any(p.self_check for p in (v1, v2, v3))
    assert v4.self_check and v4.self_check_prompt
    assert v4.system == v3.system
    voice = v2.system.split("VOICE RULES")[1]
    assert voice.strip() in v3.system
    assert v2.system.startswith(v1.system) and "VOICE RULES" not in v1.system
    for needed in ("log the dispute", "payment or a promise on this call", "UTR",
                   "get_invoice", "search_policy"):
        assert needed in v3.system
    assert "IDENTITY FIRST" not in v2.system


def test_self_check_flag_must_be_a_real_bool_with_a_prompt(tmp_path):
    def write(body):
        (tmp_path / "v9.yaml").write_text("system: hi\n" + body, encoding="utf-8")
        return load_prompt("v9", tmp_path)

    with pytest.raises(ValueError):
        write("self_check: 'yes'\nself_check_prompt: p\n")
    with pytest.raises(ValueError):
        write("self_check: true\n")
    assert write("self_check: true\nself_check_prompt: p\n").self_check is True
    assert PROMPTS_DIR.joinpath("v4.yaml").exists()
