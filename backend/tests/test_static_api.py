"""The static files must be byte-for-byte what the live API returns, after a JSON round trip."""
import json

import pytest
from fastapi.testclient import TestClient

from backend import static_api
from backend.eval import export
from backend.main import create_app
from backend.tests.api_helpers import build_api_db


@pytest.fixture
def built(tmp_path):
    """Fixture DB -> export (all judges) -> static files. Returns (out dir, API client, lines)."""
    path = build_api_db(tmp_path)
    results, out = tmp_path / "results", tmp_path / "static"
    assert export.main(["--db", str(path), "--out", str(results), "--all-judges"],
                       out=lambda _: None) == 0
    lines: list[str] = []
    assert static_api.main(["--results", str(results), "--out", str(out)], out=lines.append) == 0
    return out, TestClient(create_app(path, tmp_path / "no_dist")), lines


def read(out, rel):
    return json.loads((out / rel).read_text(encoding="utf-8"))


def test_every_static_file_equals_the_api_response(built):
    out, client, _ = built
    api_runs = [r for r in client.get("/api/runs").json() if r["headline"]]  # exported runs only
    assert read(out, "runs.json") == api_runs
    assert [r["id"] for r in api_runs] == [2, 1]  # newest first, as the API orders them
    for run in api_runs:
        rid = run["id"]
        assert read(out, f"runs/{rid}.json") == client.get(f"/api/runs/{rid}").json()
        calls = client.get(f"/api/runs/{rid}/calls").json()
        assert read(out, f"runs/{rid}/calls.json") == calls
        for c in calls:
            assert (read(out, f"calls/{rid}/{c['idx']}.json")
                    == client.get(f"/api/calls/{rid}/{c['idx']}").json())


def test_failed_call_and_partial_run_survive(built):
    out, _, lines = built
    run = read(out, "runs/2.json")
    assert run["status"] == "partial" and run["n_failed"] == 1 and run["n"] == 6
    assert read(out, "calls/2/2.json")["error"] == "agent_error: boom"
    assert "2 runs, 7 calls" in lines[0]


def test_meta_has_latest_run_date(built):
    out, _, _ = built
    dates = [r["updated_at"] for r in read(out, "runs.json")]
    assert read(out, "meta.json") == {"snapshot_date": max(dates)}


def test_rebuild_removes_stale_files_but_never_a_foreign_folder(built, tmp_path):
    out, _, _ = built
    (out / "runs" / "999.json").write_text("{}", encoding="utf-8")
    results = tmp_path / "results"
    static_api.main(["--results", str(results), "--out", str(out)], out=lambda _: None)
    assert not (out / "runs" / "999.json").exists()
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "keep.txt").write_text("x", encoding="utf-8")
    static_api.main(["--results", str(results), "--out", str(foreign)], out=lambda _: None)
    assert (foreign / "keep.txt").exists()


def test_no_results_fails(tmp_path):
    lines: list[str] = []
    assert static_api.main(["--results", str(tmp_path), "--out", str(tmp_path / "o")],
                           out=lines.append) == 1
    assert "No exported runs" in lines[0]
