import pytest

from backend.eval import validation as v
from backend.tests.validation_helpers import build_db


def test_kappa_perfect_chance_and_worked_example():
    assert v.cohen_kappa([True, False, True, False], [True, False, True, False]) == 1.0
    assert v.cohen_kappa([True, True, False, False], [True, False, True, False]) == 0.0
    # 10 items: both yes 4, both no 4, a yes/b no 1, a no/b yes 1 -> po .8, pe .5, kappa .6
    a = [True] * 5 + [False] * 5
    b = [True] * 4 + [False] + [True] + [False] * 4
    assert v.cohen_kappa(a, b) == 0.6


def test_kappa_is_none_when_undefined():
    assert v.cohen_kappa([], []) is None
    assert v.cohen_kappa([False] * 4, [False] * 4) is None  # both constant: chance agreement is 1


def test_compare_counts_agreement_and_lists_disagreements():
    first = {"k1": {"task_success": True, "tone": 4}, "k2": {"task_success": False, "tone": 4}}
    second = {"k1": {"task_success": True, "tone": 3}, "k2": {"task_success": True, "tone": 4},
              "k3": {"task_success": True}}
    r = v.compare(first, second)["task_success"]
    assert r["n"] == 2 and r["agree_pct"] == 50.0
    assert r["disagreements"] == [{"key": "k2", "first": False, "second": True}]
    assert v.compare(first, second)["hallucination"]["n"] == 0


def test_compare_tone_sign_means_first_is_more_lenient():
    judge = {"a": {"tone": 5}, "b": {"tone": 4}, "c": {"tone": 3}, "d": {"tone": 3}}
    human = {"a": {"tone": 3}, "b": {"tone": 4}, "c": {"tone": 3}, "d": {"tone": 3}}
    r = v.compare_tone(judge, human)
    assert (r["n"], r["exact_pct"], r["within1_pct"], r["mean_diff"]) == (4, 75.0, 75.0, 0.5)
    assert v.compare_tone(human, judge)["mean_diff"] == -0.5


def test_sample_is_deterministic_stratified_and_capped(tmp_path):
    path, _ = build_db(tmp_path)
    pool = v.load_ok_calls(v.open_readonly(path))
    assert len(pool) == 8
    s1, s2 = v.sample_calls(pool, 6, seed=1), v.sample_calls(pool, 6, seed=1)
    assert [c["key"] for c in s1] == [c["key"] for c in s2]
    assert len({c["key"] for c in s1}) == 6
    assert len(v.sample_calls(pool, 20, seed=1)) == 8  # never longer than the pool
    groups = {(c["prompt_version"], c["persona"]) for c in v.sample_calls(pool, 5, seed=3)}
    assert len(groups) == 5  # 5 picks come from 5 different strata (there are 6)


def test_open_readonly_rejects_writes(tmp_path):
    path, _ = build_db(tmp_path)
    conn = v.open_readonly(path)
    with pytest.raises(Exception, match="readonly"):
        conn.execute("DELETE FROM calls")


def test_save_json_roundtrip_and_missing_default(tmp_path):
    p = tmp_path / "sub" / "x.json"
    assert v.load_json(p, {"d": 1}) == {"d": 1}
    v.save_json(p, {"a": "₹"})
    assert v.load_json(p) == {"a": "₹"} and list(p.parent.iterdir()) == [p]
