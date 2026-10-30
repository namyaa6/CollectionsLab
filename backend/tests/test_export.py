import json

from backend import db
from backend.eval import export
from backend.tests.validation_helpers import VERSIONS, build_db, call_record, run_spec


def run_export(path, out_dir, *extra):
    out = []
    code = export.main(["--db", str(path), "--out", str(out_dir), *extra], out=out.append)
    return code, "\n".join(out)


def test_exports_latest_run_per_prompt_with_stored_metrics(tmp_path):
    path, _ = build_db(tmp_path)
    out_dir = tmp_path / "results"
    code, _ = run_export(path, out_dir)
    assert code == 0
    index = json.loads((out_dir / "index.json").read_text(encoding="utf-8"))
    assert [i["prompt_version"] for i in index] == ["vTESTA", "vTESTB"]
    data = json.loads((out_dir / index[0]["file"]).read_text(encoding="utf-8"))
    assert data["metrics"] == {"overall": {"n_calls": 4, "n_failed": 0}}  # copied, not recomputed
    assert data["complete"] is True and data["n_calls_stored"] == 4
    assert data["run_key"] == VERSIONS["vTESTA"] and data["models"]["judge"] == "judge-m"


def test_examples_are_from_distinct_personas_and_seeded(tmp_path):
    path, _ = build_db(tmp_path)
    run_export(path, tmp_path / "a", "--examples", "3")
    run_export(path, tmp_path / "b", "--examples", "3")
    name = next(p.name for p in (tmp_path / "a").iterdir() if p.name.startswith("vTESTA"))
    a = json.loads((tmp_path / "a" / name).read_text(encoding="utf-8"))
    b = json.loads((tmp_path / "b" / name).read_text(encoding="utf-8"))
    assert a["examples"] == b["examples"]
    personas = [e["persona"] for e in a["examples"]]
    assert len(personas) == 3 and len(set(personas)) == 3  # 3 personas exist in the fixture
    assert a["examples"][0]["transcript"]["turns"] and a["examples"][0]["judge"]["verdict"]


def test_run_without_metrics_is_skipped_and_stale_metrics_flagged(tmp_path):
    path, _ = build_db(tmp_path)
    conn = db.connect(path)
    run_id, _ = db.find_or_create_run(conn, run_spec("vTESTC", "runkeyCCCCCCCC"))
    db.save_call(conn, run_id, 0, call_record("vTESTC", 0, "cooperative"))  # no update_run yet
    a_id, _ = db.find_or_create_run(conn, run_spec("vTESTA", VERSIONS["vTESTA"]))
    db.save_call(conn, a_id, 4, call_record("vTESTA", 4, "stalling"))  # stored after the metrics
    conn.close()
    out_dir = tmp_path / "results"
    _, text = run_export(path, out_dir)
    index = json.loads((out_dir / "index.json").read_text(encoding="utf-8"))
    assert [i["prompt_version"] for i in index] == ["vTESTA", "vTESTB"]  # vTESTC has no metrics
    assert [i["complete"] for i in index] == [False, True] and "INCOMPLETE" in text


def test_run_key_prefix_selects_runs_and_empty_db_fails(tmp_path):
    path, _ = build_db(tmp_path)
    out_dir = tmp_path / "results"
    run_export(path, out_dir, "--run-key", "runkeyB")
    assert [p.name for p in out_dir.iterdir() if p.name != "index.json"] == ["vTESTB_runkeyBB.json"]
    empty = tmp_path / "empty.db"
    db.connect(empty).close()
    code, text = run_export(empty, tmp_path / "x")
    assert code == 1 and "No runs" in text
