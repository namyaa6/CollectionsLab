import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from backend.eval.validation import open_readonly
from backend.main import create_app
from backend.tests.api_helpers import build_api_db


@pytest.fixture
def db_path(tmp_path):
    return build_api_db(tmp_path)


@pytest.fixture
def client(db_path, tmp_path):
    return TestClient(create_app(db_path, tmp_path / "no_dist"))


def test_health_and_missing_db(tmp_path):
    c = TestClient(create_app(tmp_path / "nope.db", tmp_path / "no_dist"))
    assert c.get("/api/health").json() == {"status": "ok", "db": False}
    assert c.get("/api/runs").status_code == 503


def test_runs_repeatedly_without_thread_errors(client, db_path):
    # The dependency and the endpoint can run on different threads; this used to 500 at random.
    assert all(client.get("/api/runs").status_code == 200 for _ in range(50))
    conn = open_readonly(db_path)  # deterministic version: use the connection on another thread
    with ThreadPoolExecutor(1) as pool:
        assert pool.submit(lambda: conn.execute("SELECT 1").fetchone()[0]).result() == 1
    conn.close()


def test_health_ok(client):
    assert client.get("/api/health").json() == {"status": "ok", "db": True}


def test_runs_list(client):
    runs = client.get("/api/runs").json()
    by_id = {r["id"]: r for r in runs}
    assert sorted(by_id) == [1, 2, 3]
    assert by_id[1]["judge_version"] == "j1" and by_id[1]["status"] == "complete"
    assert by_id[1]["complete"] and by_id[1]["n_ok"] == 4 and by_id[1]["n_failed"] == 0
    assert by_id[2]["judge_version"] == "j2" and by_id[2]["status"] == "partial"
    assert not by_id[2]["complete"] and by_id[2]["n_ok"] == 2 and by_id[2]["n_failed"] == 1
    assert by_id[3]["status"] == "no_metrics" and by_id[3]["headline"] is None  # no calls stored
    assert by_id[1]["headline"]["hallucination"]["rate"] == 0.5
    assert by_id[1]["headline"]["lint_total_per_call"] == 1.5
    assert "scenarios" not in by_id[1]


def test_headline_includes_identity_pressure_policy(client):
    from backend.api_shapes import HEADLINE_RATES
    for name in ("identity_verified", "pressure_or_threat", "policy_violation"):
        assert name in HEADLINE_RATES
    h = client.get("/api/runs/1").json()["headline"]
    assert h["identity_verified"] == {"k": 2, "n": 4, "rate": 0.5, "ci_low": 0.2, "ci_high": 0.8}
    assert h["pressure_or_threat"]["ci_high"] == 0.9 and h["policy_violation"]["rate"] == 0.5


def test_interrupted_run_with_calls_is_partial(db_path, tmp_path):
    from backend import db
    conn = db.connect(db_path)
    db.set_requested_n(conn, 3, 5)
    c = TestClient(create_app(db_path, tmp_path / "no_dist"))
    r = c.get("/api/runs/3").json()
    assert r["status"] == "no_metrics" and r["n"] == 5
    from backend.tests.validation_helpers import call_record
    db.save_call(conn, 3, 0, call_record("vTESTA", 0, "cooperative"))
    conn.close()
    r = c.get("/api/runs/3").json()
    assert r["status"] == "partial" and not r["complete"] and r["n_ok"] == 1
    assert r["headline"] is None and r["metrics"] is None


def test_runs_sorted_newest_first(client, db_path):
    import time
    from backend import db
    time.sleep(1.1)  # updated_at has one-second resolution
    conn = db.connect(db_path)
    db.update_run(conn, 1, 4, {"overall": {"n_calls": 4, "n_failed": 0, "rates": {},
                                           "lint_per_call": {}}, "per_persona": {}})
    conn.close()
    assert client.get("/api/runs").json()[0]["id"] == 1


def test_run_detail(client):
    run = client.get("/api/runs/1").json()
    assert "cooperative" in run["metrics"]["per_persona"]
    assert run["prompt_hash"] == "h" and run["judge_prompt_hash"] == "jh"
    assert client.get("/api/runs/99").status_code == 404


def test_calls_list(client):
    calls = client.get("/api/runs/2/calls").json()
    assert [c["idx"] for c in calls] == [0, 1, 2]
    ok, failed = calls[0], calls[2]
    assert ok["persona"] == "cooperative" and ok["passed"] is True and ok["lint_total"] == 0
    assert ok["outcome"] == "promise_to_pay"
    assert ok["judge_flags"]["hallucination"] is False and ok["tone"] == 3
    assert failed["status"] == "failed" and failed["error"] == "agent_error: boom"
    assert failed["judge_flags"] is None and failed["lint_total"] is None
    assert all("transcript" not in c for c in calls)
    assert client.get("/api/runs/1/calls").json()[3]["lint_total"] == 4
    assert client.get("/api/runs/99/calls").status_code == 404


def test_call_detail(client):
    call = client.get("/api/calls/1/0").json()
    assert call["transcript"]["turns"][0]["self_check"]["draft"] == "Hi draft"
    assert call["transcript"]["turns"][2]["self_check"] is None
    assert call["judge"]["verdict"]["task_success"]["evidence"]
    assert "evidence_found" in call["judge"]
    assert call["prompt_version"] == "v-a" and call["judge_version"] == "j1"
    assert call["summary"] and call["checks"]
    assert client.get("/api/calls/99/0").status_code == 404
    assert client.get("/api/calls/1/99").status_code == 404


def test_compare(client):
    body = client.get("/api/compare?run_ids=2,1,2").json()
    assert [r["id"] for r in body["runs"]] == [2, 1]
    assert body["runs"][0]["metrics"] and body["runs"][1]["judge_version"] == "j1"
    text = " ".join(body["warnings"])
    assert "different judge versions" in text and "Run 2 is partial" in text
    clean = client.get("/api/compare?run_ids=1").json()
    assert clean["warnings"] == []


@pytest.mark.parametrize("q,code", [("run_ids=a,b", 400), ("run_ids=,", 400),
                                    ("run_ids=1,2,3,4,5,6,7,8,9,10,11", 400),
                                    ("run_ids=1,99", 404), ("", 422)])
def test_compare_errors(client, q, code):
    assert client.get(f"/api/compare?{q}").status_code == code


def test_api_is_read_only(db_path, tmp_path):
    before = hashlib.sha256(db_path.read_bytes()).hexdigest()
    c = TestClient(create_app(db_path, tmp_path / "no_dist"))
    for url in ("/api/runs", "/api/runs/1", "/api/runs/1/calls", "/api/calls/1/0",
                "/api/compare?run_ids=1,2"):
        assert c.get(url).status_code == 200
    assert hashlib.sha256(db_path.read_bytes()).hexdigest() == before
    conn = open_readonly(db_path)
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("DELETE FROM runs")
    conn.close()


def test_cors_for_vite(client):
    r = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_static_frontend_and_unknown_api(db_path, tmp_path):
    assert TestClient(create_app(db_path, tmp_path / "no_dist")).get("/").status_code == 404
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>dash</html>", encoding="utf-8")
    c = TestClient(create_app(db_path, dist))
    assert "dash" in c.get("/").text
    assert c.get("/api/health").json()["status"] == "ok"
    assert c.get("/api/nope").status_code == 404
    assert c.get("/api/nope").headers["content-type"].startswith("application/json")
