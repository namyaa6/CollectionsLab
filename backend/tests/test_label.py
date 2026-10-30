import json

import pytest

from backend.eval import label
from backend.eval.validation import load_json
from backend.tests.validation_helpers import UTR, VERSIONS, build_db, invoice_view

ONE_CALL = ["y", "n", "n", "y", "y", "n", "3"]  # 6 booleans, then tone


def scripted(answers):
    it = iter(answers)

    def input_fn(prompt):
        try:
            return next(it)
        except StopIteration:
            raise EOFError
    return input_fn


@pytest.fixture
def env(tmp_path):
    path, keys = build_db(tmp_path)
    labels = tmp_path / "labels" / "labels.json"

    def run(answers, n=8):
        out = []
        code = label.main(["--db", str(path), "--labels", str(labels), "--n", str(n)],
                          input_fn=scripted(answers), out=out.append)
        return code, "\n".join(out)
    run.labels, run.keys = labels, keys
    return run


def test_output_is_blind(env):
    code, text = env(ONE_CALL * 8)
    assert code == 0
    for secret in (*VERSIONS, *VERSIONS.values(), "already_paid", "stalling", "cooperative",
                   UTR, "payment_claim", "expected", "task_success\": ", "judge"):
        assert secret not in text, secret
    assert "Call 1 of 8" in text and "Call 8 of 8" in text


def test_invoice_shown_is_the_agent_view(env):
    _, text = env(ONE_CALL * 8)
    assert json.dumps(invoice_view("vTESTA", 0), indent=2) in text
    assert json.dumps(invoice_view("vTESTB", 1), indent=2) in text


def test_presented_in_stored_sample_order_and_not_grouped_by_version(env):
    _, text = env(ONE_CALL * 8)
    data = load_json(env.labels)
    shown = [line.split('"')[3] for line in text.splitlines()
             if line.startswith('  "invoice_id"')]
    assert shown == [env.keys[k] for k in data["sample"]]
    versions = [int(s.split("-")[1]) // 100 for s in shown]
    assert versions != sorted(versions) and versions != sorted(versions, reverse=True)


def test_labels_saved_per_call_quit_and_resume(env):
    code, text = env(ONE_CALL + ["y", "q"])
    data = load_json(env.labels)
    assert code == 0 and "Stopped" in text and len(data["labels"]) == 1
    assert list(data["labels"].values())[0] == {
        "task_success": True, "hallucination": False, "compliance_violation": False,
        "escalation_correct": True, "identity_verified_before_amounts": True,
        "pressure_or_threat": False, "tone": 3}
    _, text = env(ONE_CALL * 7)  # resume: the labelled call is skipped
    assert "1/8 labelled" in text and "Call 1 of 8" not in text
    assert len(load_json(env.labels)["labels"]) == 8


def test_bad_input_reprompts_back_and_tone_range(env):
    answers = ["maybe", "y", "n", "b", "y", "n", "n", "y", "n", "9", "0", "5"]
    _, text = env(answers + ONE_CALL * 7)
    assert text.count("Please answer") == 3
    first = load_json(env.labels)["labels"][load_json(env.labels)["sample"][0]]
    assert first["hallucination"] is True  # 'b' went back and the answer was replaced
    assert first["tone"] == 5


def test_no_judged_calls_exits_with_message(tmp_path):
    from backend import db
    path = tmp_path / "e.db"
    db.connect(path).close()
    out = []
    code = label.main(["--db", str(path), "--labels", str(tmp_path / "l.json")],
                      input_fn=scripted([]), out=out.append)
    assert code == 1 and "No judged calls" in out[0]
