import copy

from backend.eval import agreement
from backend.eval.validation import flatten_verdict, save_json
from backend.tests.validation_helpers import build_db, verdict

KEYS = [f"{rk}:{i}" for rk in ("runkeyAAAAAAAA", "runkeyBBBBBBBB") for i in range(4)]


def judge_flat(key):
    return flatten_verdict(verdict(int(key.rsplit(":", 1)[1])))


def write_labels(path, tweak):
    labels = {k: judge_flat(k) for k in KEYS}
    tweak(labels)
    save_json(path, {"seed": 42, "sample": KEYS, "labels": labels})


def run(tmp_path, tweak, *extra):
    db_path, _ = build_db(tmp_path)
    labels = tmp_path / "labels.json"
    write_labels(labels, tweak)
    out = []
    code = agreement.main(["--db", str(db_path), "--labels", str(labels), *extra], out=out.append)
    return code, "\n".join(out)


def test_hand_vs_judge_numbers_and_disagreements(tmp_path):
    def tweak(labels):
        labels[KEYS[0]]["task_success"] = not labels[KEYS[0]]["task_success"]
        labels[KEYS[1]]["tone"] -= 1  # judge higher by 1
        labels[KEYS[2]]["tone"] -= 1
    code, text = run(tmp_path, tweak)
    assert code == 0
    assert "task_success" in text and "87.5%" in text
    assert "tone (n=8): exact 75.0%, within-1 100.0%, mean diff 0.25 (main judge minus hand)" in text
    assert "task_success [vTESTA/cooperative] True vs False" in text
    assert "hallucination" in text and "undefined" in text  # constant ratings: kappa undefined


def test_perfect_agreement_lists_no_disagreements(tmp_path):
    _, text = run(tmp_path, lambda labels: None)
    assert "none" in text and "100.0%" in text


def test_second_judge_sections(tmp_path):
    cross_path = tmp_path / "cross.json"
    results = {}
    for k in KEYS[:4]:
        v = copy.deepcopy(verdict(int(k.rsplit(":", 1)[1])))
        v["tone"]["score"] = 1
        results[k] = {"verdict": v, "error": None}
    results["gone"] = {"verdict": None, "error": "unusable"}
    save_json(cross_path, {"judge_model": "second-m", "results": results})
    _, text = run(tmp_path, lambda labels: None, "--cross", str(cross_path))
    assert "Second judge: second-m (4 verdicts)" in text
    assert "== second judge vs hand ==" in text and "== second judge vs main judge ==" in text
    assert "(second judge minus hand)" in text


def test_missing_labels_and_cross_file(tmp_path):
    db_path, _ = build_db(tmp_path)
    out = []
    assert agreement.main(["--db", str(db_path), "--labels", str(tmp_path / "none.json")],
                          out=out.append) == 1
    save_json(tmp_path / "l.json", {"sample": KEYS, "labels": {KEYS[0]: judge_flat(KEYS[0])}})
    assert agreement.main(["--db", str(db_path), "--labels", str(tmp_path / "l.json"),
                           "--cross", str(tmp_path / "nope.json")], out=out.append) == 1
    assert "Cross-judge file not found" in out[-1]


def test_label_for_a_call_missing_from_db_is_ignored(tmp_path):
    def tweak(labels):
        labels["runkeyZZZZ:0"] = judge_flat(KEYS[0])
    code, text = run(tmp_path, tweak)
    assert code == 0 and "Hand labels: 9; judged calls found in the DB: 8" in text
