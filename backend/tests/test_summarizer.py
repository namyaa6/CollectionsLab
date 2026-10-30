import json

import pytest
from pydantic import ValidationError

from backend.agent.summarizer import build_dialogue, derive_from_actions, pick_outcome, summarize
from backend.agent.summary_schema import CallSummary, LLMReading
from backend.llm.fake import FakeLLMClient, text_reply
from backend.sim.transcript import Transcript, Turn

PROMISE = {"tool": "log_promise_to_pay", "args": {"date": "2026-11-10", "amount_inr": 65200},
           "result": {"status": "logged"}}
CLAIM = {"tool": "log_payment_claim",
         "args": {"utr": "UTR123", "date": "2026-10-01", "amount_inr": 65200},
         "result": {"status": "logged"}}
ESCALATE = {"tool": "escalate_to_human", "args": {"reason": "abusive"}, "result": {"status": "escalated"}}
DISPUTE = {"tool": "log_dispute", "args": {"reason": "GST wrong"}, "result": {"status": "logged"}}
PLAN = {"tool": "log_installment_plan",
        "args": {"parts": [{"date": "2026-11-10", "amount_inr": 30000},
                           {"date": "2026-12-10", "amount_inr": 35200}]},
        "result": {"status": "logged"}}
END = {"tool": "end_call", "args": {"reason": "done"}, "result": {"status": "call_ended"}}


def make_transcript(actions: list[dict]) -> Transcript:
    turns = [
        Turn(speaker="agent", text="Hello, this is Asha.", tool_calls=[
            {"tool": "get_invoice", "args": {"invoice_id": "INV-SECRET-9"}, "result": {}}]),
        Turn(speaker="debtor", text="I will pay on the tenth."),
        Turn(speaker="agent", text="", tool_calls=actions),
    ]
    return Transcript(scenario_id=0, persona="cooperative", expected_outcomes=["promise_to_pay"],
                      prompt_version="v1", agent_model="a", sim_model="s", seed=1, turns=turns,
                      actions=actions, end_reason="end_call")


def reading(**kw) -> object:
    data = {"outcome": "promise_to_pay", "promise_date": "2026-11-10", "amount_inr": 65200,
            "escalated": False, "next_action": "Wait for payment."}
    data.update(kw)
    return text_reply(json.dumps(data))


def run(actions, llm_reply):
    client = FakeLLMClient([llm_reply])
    return summarize(make_transcript(actions), client, "judge-model"), client


def test_promise_agrees_with_llm():
    s, _ = run([PROMISE, END], reading())
    assert (s.outcome, s.promise_date, s.amount_inr) == ("promise_to_pay", "2026-11-10", 65200)
    assert s.logged_outcomes == ["promise_to_pay"] and s.discrepancies == [] and s.llm_used
    assert s.next_action == "Wait for payment."


def test_each_action_maps_to_its_field():
    fields, logged, _ = derive_from_actions([PLAN, DISPUTE, CLAIM, ESCALATE, END])
    assert [p.amount_inr for p in fields["installment_plan"]] == [30000, 35200]
    assert fields["dispute_reason"] == "GST wrong"
    assert fields["payment_claim"].utr == "UTR123"
    assert logged == ["installment_plan", "dispute_logged", "payment_claim_logged", "escalated"]


def test_precedence():
    assert pick_outcome(["promise_to_pay", "installment_plan"]) == "installment_plan"
    assert pick_outcome(["payment_claim_logged", "dispute_logged"]) == "dispute_logged"
    assert pick_outcome(["promise_to_pay", "escalated"]) == "escalated"
    assert pick_outcome([]) == "no_resolution"


def test_claim_and_promise_both_reported():
    s, _ = run([CLAIM, PROMISE], reading(outcome="payment_claim_logged", promise_date=None, amount_inr=None,
                                         payment_claim=CLAIM["args"]))
    assert s.outcome == "payment_claim_logged"
    assert s.logged_outcomes == ["payment_claim_logged", "promise_to_pay"]
    assert any("Multiple outcomes logged: payment_claim_logged, promise_to_pay" in d
               for d in s.discrepancies)


def test_promise_plus_escalation_is_not_flagged():
    s, _ = run([PROMISE, ESCALATE], reading(outcome="escalated", escalated=True))
    assert s.logged_outcomes == ["promise_to_pay", "escalated"] and s.escalated
    assert not any("Multiple" in d for d in s.discrepancies)


def test_escalation_plus_two_others_is_flagged():
    s, _ = run([PROMISE, DISPUTE, ESCALATE], reading(outcome="escalated", escalated=True,
                                                      dispute_reason="GST"))
    assert s.logged_outcomes == ["promise_to_pay", "dispute_logged", "escalated"]
    assert any("Multiple outcomes logged" in d for d in s.discrepancies)


def test_llm_hears_promise_but_none_logged():
    s, _ = run([END], reading())
    assert s.outcome == "no_resolution" and s.logged_outcomes == [] and s.promise_date is None
    assert any(d.startswith("outcome:") for d in s.discrepancies)
    assert any(d.startswith("promise_date:") for d in s.discrepancies)


def test_llm_date_and_amount_differ_actions_win():
    s, _ = run([PROMISE], reading(promise_date="2026-11-12", amount_inr=60000))
    assert (s.promise_date, s.amount_inr) == ("2026-11-10", 65200)
    assert any(d.startswith("promise_date:") for d in s.discrepancies)
    assert any(d.startswith("amount_inr:") for d in s.discrepancies)


def test_llm_says_escalated_but_not_logged():
    s, _ = run([PROMISE], reading(escalated=True))
    assert s.escalated is False
    assert any(d.startswith("escalated:") for d in s.discrepancies)


def test_repeated_tool_last_wins_and_is_noted():
    later = {**PROMISE, "args": {"date": "2026-11-20", "amount_inr": 65200}}
    s, _ = run([PROMISE, later], reading(promise_date="2026-11-20"))
    assert s.promise_date == "2026-11-20"
    assert any("more than once" in d for d in s.discrepancies)


def test_llm_prompt_has_dialogue_but_no_actions():
    _, client = run([PROMISE, END], reading())
    sent = client.calls[0]["messages"][0]["text"]
    assert "I will pay on the tenth." in sent
    assert "log_promise_to_pay" not in sent and "INV-SECRET-9" not in sent and "65200" not in sent
    assert client.calls[0]["response_schema"] is LLMReading and client.calls[0]["model"] == "judge-model"


def test_dialogue_skips_empty_turns():
    assert build_dialogue(make_transcript([END])).count("AGENT:") == 1


def test_invalid_llm_json_falls_back_to_actions():
    s, _ = run([PROMISE, END], text_reply("not json"))
    assert s.llm_used is False and s.outcome == "promise_to_pay" and s.promise_date == "2026-11-10"
    assert any("unavailable" in d for d in s.discrepancies)
    assert s.next_action


@pytest.mark.parametrize("bad", [
    {"amount_inr": 0}, {"amount_inr": -5}, {"promise_date": "10/11/2026"}, {"outcome": "paid"},
])
def test_schema_rejects_bad_values(bad):
    data = {"outcome": "promise_to_pay", "next_action": "x", **bad}
    with pytest.raises(ValidationError):
        CallSummary(**data)
