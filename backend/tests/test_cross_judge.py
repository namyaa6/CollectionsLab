import json

import pytest

from backend import db
from backend.eval import cross_judge
from backend.eval.judge import JudgeVerdict
from backend.eval.validation import load_json, save_json
from backend.llm.fake import FakeLLMClient, text_reply
from backend.llm.types import QuotaExhaustedError
from backend.tests.eval_helpers import JUDGE_OK
from backend.tests.validation_helpers import build_db

SECOND = {**JUDGE_OK, "tone": {"score": 2, "evidence": "Thank you"}}


def reply(_request=None):
    return text_reply(json.dumps(SECOND))


def quota(_request):
    raise QuotaExhaustedError("daily limit")


@pytest.fixture
def env(tmp_path):
    path, keys = build_db(tmp_path)
    sample = list(keys)[:3]
    labels = tmp_path / "labels" / "labels.json"
    save_json(labels, {"seed": 42, "sample": sample, "labels": {}})

    def run(client, *extra, input_fn=lambda p: "y"):
        out = []
        code = cross_judge.main(["--judge-model", "second-m", "--db", str(path),
                                 "--labels", str(labels), *extra],
                                client=client, input_fn=input_fn, out=out.append)
        return code, "\n".join(out)
    run.path, run.labels, run.sample = path, labels, sample
    run.out_file = labels.parent / "cross_judge_second-m.json"
    return run


def test_judges_the_labelled_sample_with_the_given_model(env):
    before = env.path.read_bytes()
    client = FakeLLMClient([reply] * 3)
    code, _ = env(client, "--yes")
    assert code == 0 and len(client.calls) == 3
    assert {c["model"] for c in client.calls} == {"second-m"}
    assert all(c["response_schema"] is JudgeVerdict for c in client.calls)
    stored = load_json(env.out_file)
    assert stored["judge_model"] == "second-m" and list(stored["results"]) == env.sample
    assert stored["results"][env.sample[0]]["verdict"]["tone"]["score"] == 2
    assert env.path.read_bytes() == before  # the eval database is untouched


def test_main_verdicts_are_not_overwritten(env):
    env(FakeLLMClient([reply] * 3), "--yes")
    conn = db.connect(env.path)
    tones = [c["judge"]["verdict"]["tone"]["score"] for r in conn.execute("SELECT id FROM runs")
             for c in db.get_calls(conn, r["id"])]
    assert 2 not in tones


def test_declining_the_confirmation_makes_no_calls(env):
    client = FakeLLMClient([])
    code, out = env(client, input_fn=lambda p: "n")
    assert code == 1 and "No calls were made" in out and not client.calls
    assert not env.out_file.exists()


def test_quota_stop_saves_progress_and_rerun_resumes(env):
    code, out = env(FakeLLMClient([reply, quota]), "--yes")
    assert code == 2 and "Progress saved" in out
    assert list(load_json(env.out_file)["results"]) == env.sample[:1]
    client = FakeLLMClient([reply] * 2)
    code, _ = env(client, "--yes")
    assert code == 0 and len(client.calls) == 2  # only the two missing calls
    assert list(load_json(env.out_file)["results"]) == env.sample


def test_nothing_to_do_when_all_judged(env):
    env(FakeLLMClient([reply] * 3), "--yes")
    client = FakeLLMClient([])
    code, out = env(client)
    assert code == 0 and not client.calls and "Live requests needed: 0" in out


def test_without_labels_file_uses_the_seeded_sample(tmp_path):
    path, keys = build_db(tmp_path)
    labels = tmp_path / "none" / "labels.json"
    client = FakeLLMClient([reply] * 5)
    code = cross_judge.main(["--judge-model", "second-m", "--db", str(path), "--labels",
                             str(labels), "--n", "5", "--yes"], client=client, out=lambda s: None)
    assert code == 0 and len(client.calls) == 5
    assert set(load_json(labels.parent / "cross_judge_second-m.json")["results"]) <= set(keys)


def test_output_file_name_is_sanitised(tmp_path):
    assert cross_judge.output_path(tmp_path / "labels.json", "models/gemini 3.8").name == \
        "cross_judge_models_gemini_3.8.json"
