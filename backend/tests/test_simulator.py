import pytest

from backend.llm.fake import FakeLLMClient, text_reply, tool_reply
from backend.prompts import Prompt
from backend.rag.policy_index import PolicyIndex
from backend.scenarios.generator import SIM_DATE, generate_scenarios
from backend.sim.run_one import format_transcript
from backend.sim.simulator import debtor_system, simulate
from backend.sim.transcript import Transcript

PROMPT = Prompt("v1", "You are an agent.")


@pytest.fixture(scope="module")
def index():
    return PolicyIndex.from_file()


def scenario(persona="already_paid"):
    return next(s for s in generate_scenarios(14, 42) if s.persona == persona)


def run(script, index, **kw):
    client = FakeLLMClient(script)
    return simulate(scenario(), client, PROMPT, "agent-m", "sim-m", index, **kw), client


def test_stops_on_end_call(index):
    t, _ = run([text_reply("Hello."), text_reply("Hi."),
                tool_reply("end_call", {"reason": "done"}, text="Bye.")], index)
    assert t.end_reason == "end_call" and t.end_detail == "done"
    assert [x.speaker for x in t.turns] == ["agent", "debtor", "agent"]
    assert t.turns[-1].tool_calls[0]["tool"] == "end_call"


def test_stops_on_escalation(index):
    t, _ = run([text_reply("Hello."), text_reply("I will sue you."),
                tool_reply("escalate_to_human", {"reason": "legal threat"})], index)
    assert t.end_reason == "escalated" and t.actions[0]["tool"] == "escalate_to_human"


def test_turn_limit_enforced(index):
    t, client = run([text_reply("x")] * 10, index, max_debtor_turns=5)
    assert t.end_reason == "turn_limit"
    assert t.totals["debtor_turns"] == 5 and t.totals["agent_turns"] == 5
    assert len(client.calls) == 10  # no sixth agent turn


def test_default_limit_is_twelve_debtor_turns(index):
    t, _ = run([text_reply("x")] * 24, index)
    assert t.totals["debtor_turns"] == 12 and t.end_reason == "turn_limit"


def test_agent_speaks_first_and_histories_are_mirrored(index):
    _, client = run([text_reply("Hello."), text_reply("Hi there."),
                     tool_reply("end_call", {"reason": "d"})], index)
    first_agent, debtor, last_agent = client.calls
    assert first_agent["model"] == "agent-m" and debtor["model"] == "sim-m"
    assert debtor["messages"] == [{"role": "user", "text": "Hello."}]
    assert last_agent["messages"][-1] == {"role": "user", "text": "Hi there."}
    assert debtor["tools"] is None and first_agent["tools"]


def test_agent_system_has_prompt_and_context_but_no_secrets(index):
    s = scenario()
    _, client = run([tool_reply("end_call", {"reason": "d"})], index)
    system = client.calls[0]["system"]
    assert system.startswith(PROMPT.system) and s.invoice.invoice_id in system
    assert SIM_DATE.isoformat() in system
    assert str(s.invoice.amount_inr) not in system and "payment_claim" not in system


def test_debtor_gets_full_private_invoice():
    s = scenario()
    system = debtor_system(s)
    assert s.invoice.payment_claim.utr in system and str(s.invoice.amount_inr) in system


def test_empty_agent_reply_ends_as_agent_error(index):
    t, _ = run([text_reply("")], index)
    assert t.end_reason == "agent_error" and t.turns[0].error


def test_empty_debtor_reply_ends_as_debtor_error(index):
    t, _ = run([text_reply("Hello."), text_reply("")], index)
    assert t.end_reason == "debtor_error"


def test_totals_save_load_and_format(index, tmp_path):
    t, _ = run([text_reply("Hello."), text_reply("Hi."),
                tool_reply("end_call", {"reason": "d"}, text="Bye.")], index)
    assert t.totals["agent_input_tokens"] == 10 and t.totals["debtor_output_tokens"] == 5
    path = t.save(tmp_path, "t.json")
    assert Transcript.load(path).end_reason == "end_call"
    out = format_transcript(t)
    assert "AGENT : Hello." in out and "[tool] end_call" in out and "Ended: end_call" in out
