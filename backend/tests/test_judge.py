import json

import pytest

from backend.eval.judge import (
    JUDGE_PROMPT_PATH, JudgeVerdict, build_judge_input, calendar_block, evidence_found,
    judge_call, load_judge_prompt, render_for_judge,
)
from backend.eval.runner import build_spec
from backend.scenarios.generator import SIM_DATE
from backend.llm.fake import FakeLLMClient, text_reply
from backend.tests.eval_helpers import JUDGE_OK, get_invoice_call, make_invoice, make_transcript

J1_PATH = JUDGE_PROMPT_PATH.with_name("judge_prompt_j1.yaml")  # frozen copy of the j1 rubric
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
    assert prompt.version == "j2" and len(prompt.file_hash) == 64
    assert "evidence" in prompt.system and "tone" in prompt.system


def test_j2_differs_from_frozen_j1_and_adds_the_new_rules(prompt):
    j1 = load_judge_prompt(J1_PATH)
    assert j1.version == "j1" and prompt.version != j1.version
    assert prompt.file_hash != j1.file_hash and prompt.system != j1.system
    assert "inclusive" in prompt.system and "CALENDAR" in prompt.system
    assert "Never quote the policy or the invoice" in prompt.system


def test_j2_and_j1_get_different_run_keys(prompt):
    models = {"agent": "a", "sim": "s", "judge": "j"}
    k2 = build_spec("v1", 1, models, prompt)["run_key"]
    k1 = build_spec("v1", 1, models, load_judge_prompt(J1_PATH))["run_key"]
    assert k1 != k2


def test_calendar_block_has_call_date_plus_30_and_60():
    cal = calendar_block()
    assert SIM_DATE.isoformat() == "2026-11-02"
    assert "Call date: 2026-11-02" in cal
    assert "Call date + 30 days: 2026-12-02" in cal
    assert "Call date + 60 days: 2027-01-01" in cal
    inv = make_invoice()
    assert build_judge_input(transcript(inv), inv, POLICY).startswith(cal)


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
    assert out["error"] is None and out["judge_version"] == "j2"
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
