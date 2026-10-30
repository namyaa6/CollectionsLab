import json

import pytest

from backend.eval.judge import (
    JudgeVerdict, build_judge_input, evidence_found, judge_call, load_judge_prompt,
    render_for_judge,
)
from backend.llm.fake import FakeLLMClient, text_reply
from backend.tests.eval_helpers import JUDGE_OK, get_invoice_call, make_invoice, make_transcript

POLICY = "## Escalation Triggers\nEscalate on legal threats."


def transcript(invoice):
    return make_transcript([
        ("agent", "Hello, am I speaking with Arjun?", [get_invoice_call(invoice)]),
        ("debtor", "Yes. I will pay next week."),
        ("agent", "Thank you. Bye.", [{"tool": "end_call", "args": {"reason": "done"},
                                       "result": {"status": "call_ended"}}]),
    ], persona="disputes_amount", expected=("dispute_logged",))


@pytest.fixture
def prompt():
    return load_judge_prompt()


def test_prompt_file_is_versioned_and_hashed(prompt):
    assert prompt.version == "j1" and len(prompt.file_hash) == 64
    assert "evidence" in prompt.system and "tone" in prompt.system


def test_render_numbers_turns_and_shows_tool_calls():
    out = render_for_judge(transcript(make_invoice()))
    assert out.startswith("[0] AGENT: Hello")
    assert "[tool] get_invoice(" in out and '"outstanding_inr": 65200' in out
    assert "[2] AGENT: Thank you. Bye." in out and "[tool] end_call(" in out


def test_input_has_policy_and_visible_invoice_but_nothing_the_judge_must_not_see():
    inv = make_invoice(payment_claim={"utr": "123456789012", "date": "2026-10-01",
                                      "amount_inr": 65200})
    text = build_judge_input(transcript(inv), inv, POLICY)
    assert POLICY in text and '"invoice_id": "INV-2026-1004"' in text
    for hidden in ("123456789012", "payment_claim", "disputes_amount", "dispute_logged",
                   "expected", "voice_violations", "policy_violations", "passed"):
        assert hidden not in text


def test_judge_call_parses_verdict_and_checks_evidence(prompt):
    inv = make_invoice()
    client = FakeLLMClient([text_reply(json.dumps(JUDGE_OK))])
    out = judge_call(transcript(inv), inv, client, "judge-m", prompt, POLICY)
    assert out["error"] is None and out["judge_version"] == "j1"
    assert out["verdict"]["task_success"]["value"] is True
    assert out["verdict"]["tone"]["score"] == 5
    assert all(out["evidence_found"].values())
    req = client.calls[0]
    assert req["model"] == "judge-m" and req["response_schema"] is JudgeVerdict
    assert req["system"] == prompt.system


def test_invented_evidence_is_flagged():
    t = transcript(make_invoice())
    bad = dict(JUDGE_OK, hallucination={"value": True, "evidence": "you owe ten lakh"})
    found = evidence_found(JudgeVerdict.model_validate(bad), t)
    assert found["hallucination"] is False and found["task_success"] is True


def test_evidence_match_ignores_case_and_punctuation():
    t = transcript(make_invoice())
    v = dict(JUDGE_OK, task_success={"value": True, "evidence": "yes  i WILL pay, next week"})
    assert evidence_found(JudgeVerdict.model_validate(v), t)["task_success"]


@pytest.mark.parametrize("score", [0, 6])
def test_tone_out_of_range_is_an_error(prompt, score):
    inv = make_invoice()
    bad = dict(JUDGE_OK, tone={"score": score, "evidence": ""})
    out = judge_call(transcript(inv), inv, FakeLLMClient([text_reply(json.dumps(bad))]),
                     "judge-m", prompt, POLICY)
    assert out["verdict"] is None and "unusable" in out["error"]


def test_missing_field_is_an_error(prompt):
    inv = make_invoice()
    bad = {k: v for k, v in JUDGE_OK.items() if k != "hallucination"}
    out = judge_call(transcript(inv), inv, FakeLLMClient([text_reply(json.dumps(bad))]),
                     "judge-m", prompt, POLICY)
    assert out["verdict"] is None and out["error"]
