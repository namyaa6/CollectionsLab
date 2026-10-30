import sqlite3

import pytest

from backend import db


def spec(key="k1"):
    return {"run_key": key, "prompt_version": "v1", "prompt_hash": "p", "judge_version": "j1",
            "judge_prompt_hash": "j", "seed": 42, "models": {"agent": "a", "sim": "s", "judge": "j"},
            "scenarios": [{"scenario_id": 0, "persona": "angry"}], "pool_hash": "h"}


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "sub" / "t.db")  # parent folder is created
    yield c
    c.close()


def test_run_is_found_again_by_key(conn):
    run_id, created = db.find_or_create_run(conn, spec())
    assert created
    assert db.find_or_create_run(conn, spec()) == (run_id, False)
    assert db.find_or_create_run(conn, spec("k2"))[0] != run_id
    run = db.get_run(conn, run_id)
    assert run["models"]["judge"] == "j" and run["scenarios"][0]["persona"] == "angry"
    assert run["n"] == 0 and run["metrics"] is None


def test_calls_round_trip_ordered_and_filtered(conn):
    run_id, _ = db.find_or_create_run(conn, spec())
    for idx in (2, 0, 1):
        db.save_call(conn, run_id, idx, {"status": "ok", "scenario": {"persona": "x"},
                                         "transcript": {"turns": []}, "judge": {"v": "₹ ok"},
                                         "latency_ms": 5, "tokens": 9})
    calls = db.get_calls(conn, run_id)
    assert [c["idx"] for c in calls] == [0, 1, 2]
    assert calls[0]["judge"] == {"v": "₹ ok"} and calls[0]["summary"] is None
    assert [c["idx"] for c in db.get_calls(conn, run_id, max_idx=2)] == [0, 1]
    assert db.call_statuses(conn, run_id) == {0: "ok", 1: "ok", 2: "ok"}


def test_save_call_replaces_a_failed_row(conn):
    run_id, _ = db.find_or_create_run(conn, spec())
    db.save_call(conn, run_id, 0, {"status": "failed", "error": "boom", "scenario": {}})
    db.save_call(conn, run_id, 0, {"status": "ok", "scenario": {}, "transcript": {"turns": []}})
    calls = db.get_calls(conn, run_id)
    assert len(calls) == 1 and calls[0]["status"] == "ok" and calls[0]["error"] is None


def test_unique_run_idx_and_status_constraint(conn):
    run_id, _ = db.find_or_create_run(conn, spec())
    db.save_call(conn, run_id, 0, {"status": "ok", "scenario": {}})
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO calls (run_id, idx, status, scenario, created_at) "
                     "VALUES (?, 0, 'ok', '{}', 'now')", (run_id,))
    with pytest.raises(sqlite3.IntegrityError):
        db.save_call(conn, run_id, 1, {"status": "weird", "scenario": {}})


def test_update_run_n_only_grows(conn):
    run_id, _ = db.find_or_create_run(conn, spec())
    db.update_run(conn, run_id, 4, {"overall": 1})
    db.update_run(conn, run_id, 2, {"overall": 2})
    run = db.get_run(conn, run_id)
    assert run["n"] == 4 and run["metrics"] == {"overall": 2}
