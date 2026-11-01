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

    def run(answers, n=8, extra=()):
        out = []
        code = label.main(["--db", str(path), "--labels", str(labels), "--n", str(n), *extra],
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


PRESSURE = ["y", "n", "n", "y", "y", "y", "4"]  # same as ONE_CALL but pressure yes, tone 4


def test_relabel_overwrites_only_the_given_positions_blind(env):
    env(ONE_CALL * 8)
    before = load_json(env.labels)
    code, text = env(PRESSURE * 2, extra=["--relabel", "5,2"])
    after = load_json(env.labels)
    assert code == 0 and after["sample"] == before["sample"]
    assert [l for l in text.splitlines() if l.startswith("Call ")] == ["Call 5 of 8", "Call 2 of 8"]
    changed = {before["sample"][4], before["sample"][1]}
    for key in before["sample"]:
        expected = before["labels"][key]
        if key in changed:
            expected = {**expected, "pressure_or_threat": True, "tone": 4}
        assert after["labels"][key] == expected, key
    for secret in (*VERSIONS, *VERSIONS.values(), "already_paid", "stalling", "cooperative",
                   UTR, "payment_claim", "expected", "task_success\": ", "judge"):
        assert secret not in text, secret


def test_relabel_quit_keeps_old_label_and_bad_input_fails(env):
    env(ONE_CALL * 8)
    before = load_json(env.labels)
    code, text = env(PRESSURE + ["y", "q"], extra=["--relabel", "1,3"])
    after = load_json(env.labels)
    assert code == 0 and "Call 3 keeps its previous label" in text
    assert after["labels"][before["sample"][0]]["pressure_or_threat"] is True
    assert after["labels"][before["sample"][2]] == before["labels"][before["sample"][2]]
    code, text = env([], extra=["--relabel", "0,9"])
    assert code == 1 and "between 1 and 8: [0, 9]" in text
    assert load_json(env.labels) == after
    with pytest.raises(SystemExit):
        env([], extra=["--relabel", "two"])


def test_relabel_without_labels_file_fails(env):
    code, text = env([], extra=["--relabel", "1"])
    assert code == 1 and "No labels file" in text and not env.labels.exists()


def test_no_judged_calls_exits_with_message(tmp_path):
    from backend import db
    path = tmp_path / "e.db"
    db.connect(path).close()
    out = []
    code = label.main(["--db", str(path), "--labels", str(tmp_path / "l.json")],
                      input_fn=scripted([]), out=out.append)
    assert code == 1 and "No judged calls" in out[0]
